"""Приватный Telegram long poller и отдельная очередь доставки Day 20."""
from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .article import github_repo as canonical_github_repo
from .config import DATA
from .rss import canonical_link
from .store import Store, compact, now

URL = re.compile(r"https://habr\.com/ru/(?:companies/[A-Za-z0-9_-]{1,100}/)?articles/[0-9]+/?")
GITHUB_URL = re.compile(r"https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^\s]*)?")
GOAL = re.compile(r"(?:\bдля\s+(?!меня\b|моего\b|моих\b)\S+|\bхочу\s+\S+|\bу меня\s+\S+|\bмоя\s+задача\s+\S+)", re.I)
PERSONAL = re.compile(r"\b(?:мне|моему|моих|лично|у меня)\b", re.I)


class TelegramError(RuntimeError):
    pass


class BotApi:
    def __init__(self, token: str):
        if not token:
            raise ValueError("telegram_token_missing")
        self._base = f"https://api.telegram.org/bot{token}/"

    def call(self, method: str, params: dict | None = None, *, timeout: int = 35) -> dict:
        payload = urllib.parse.urlencode(params or {}).encode()
        request = urllib.request.Request(self._base + method, data=payload)
        opener = urllib.request.build_opener(urllib.request.HTTPHandler())
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(128 * 1024)
        except urllib.error.HTTPError as error:
            # Только документированный 4xx отказ до принятия сообщения — определённый исход.
            if 400 <= error.code < 500:
                raise TelegramError("telegram_rejected") from None
            raise TelegramError("telegram_unknown") from None
        except (OSError, TimeoutError) as error:
            raise TelegramError("telegram_unknown") from None
        try:
            data = json.loads(raw)
        except ValueError as error:
            raise TelegramError("telegram_unknown") from None
        if data.get("ok") is not True:
            raise TelegramError("telegram_rejected" if 400 <= data.get("error_code", 0) < 500 else "telegram_unknown")
        return data["result"]

    def identity(self) -> int:
        return int(self.call("getMe")["id"])

    def ensure_no_webhook(self) -> None:
        if self.call("getWebhookInfo").get("url"):
            raise TelegramError("webhook_active")

    def updates(self, offset: int) -> list[dict]:
        return self.call("getUpdates", {"offset": offset, "timeout": 25,
                                        "allowed_updates": '["message"]'}, timeout=35)

    def send(self, chat_id: int, text: str, reply_to_message_id: int | None = None) -> int:
        params = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
        if reply_to_message_id:
            params["reply_to_message_id"] = reply_to_message_id
            params["allow_sending_without_reply"] = "true"
        result = self.call("sendMessage", params, timeout=20)
        message_id = result.get("message_id")
        if type(message_id) is not int or message_id <= 0:
            raise TelegramError("telegram_unknown")
        return message_id


def _links(value: str) -> list[str]:
    found = []
    for raw in URL.findall(value or ""):
        try:
            _, canonical = canonical_link(raw)
        except ValueError:
            continue
        if canonical not in found:
            found.append(canonical)
    return found


def _github_links(value: str) -> list[str]:
    found=[]
    for raw in GITHUB_URL.findall(value or ""):
        canonical=canonical_github_repo(raw.rstrip(".,;:)]"))
        if canonical and canonical not in found:
            found.append(canonical)
    return found


class ChatService:
    def __init__(self, store: Store, agent, bot: BotApi, *, chat_id: int, user_id: int,
                 bot_id: int):
        self.store, self.agent, self.bot = store, agent, bot
        self.chat_id, self.user_id, self.bot_id = chat_id, user_id, bot_id

    def offset(self) -> int:
        with self.store.connect() as db:
            row = db.execute("SELECT MAX(update_id) AS latest FROM ("
                             "SELECT update_id FROM incoming_updates WHERE processed=1 UNION ALL "
                             "SELECT update_id FROM ignored_updates)").fetchone()
            return (row["latest"] or 0) + 1

    def _new_request(self, db: sqlite3.Connection, *, text: str, message_id: int,
                     article_url: str | None, github_repo: str | None, link_basis: str,
                     goal: str | None,
                     candidates: list[str], parent_id: str | None, state: str) -> str:
        ident = str(uuid.uuid4())
        stamp = now()
        db.execute("INSERT INTO requests(id,chat_id,user_id,origin_message_id,parent_request_id,"
                   "user_text,article_url,github_repo,link_basis,goal,candidates_json,state,created_utc,updated_utc) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (ident,self.chat_id,self.user_id,message_id,parent_id,text,article_url,github_repo,link_basis,goal,
                    compact(candidates),state,stamp,stamp))
        return ident

    def _queue(self, db: sqlite3.Connection, request_id: str, kind: str, text: str) -> None:
        db.execute("INSERT OR IGNORE INTO outbox(id,request_id,kind,chat_id,text,status,created_utc) "
                   "VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()),request_id,kind,self.chat_id,text,
                                        "pending",now()))

    def accept(self, update: dict) -> str | None:
        update_id = update.get("update_id")
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        message_id = message.get("message_id")
        if type(update_id) is not int:
            return None
        if (not all(type(x) is int for x in (chat.get("id"),sender.get("id"),message_id))
                or chat["id"] != self.chat_id or sender["id"] != self.user_id
                or chat.get("type") != "private"):
            with self.store.tx() as db:
                db.execute("INSERT OR IGNORE INTO ignored_updates(update_id,received_utc,reason) VALUES(?,?,?)",
                           (update_id,now(),"sender_or_chat_mismatch"))
            return None
        text = (message.get("text") or "").strip()[:3000]
        reply = message.get("reply_to_message") or {}
        reply_bot = (reply.get("from") or {}).get("id") == self.bot_id
        reply_id = reply.get("message_id") if reply_bot else None
        implicit_parent = None
        if not text.startswith("/research") and not reply_bot and not _links(text):
            with self.store.connect() as db:
                implicit_parent = db.execute(
                    "SELECT r.* FROM outbox o JOIN requests r ON r.id=o.request_id "
                    "WHERE o.chat_id=? AND o.kind IN ('answer','clarification') "
                    "AND o.status='delivered' AND r.state IN ('answer_ready','needs_clarification') "
                    "ORDER BY o.message_id DESC LIMIT 1",
                    (self.chat_id,)).fetchone()
            implicit_parent = dict(implicit_parent) if implicit_parent else None
        if not text.startswith("/research") and not reply_bot and not _links(text) and not implicit_parent:
            with self.store.tx() as db:
                db.execute("INSERT OR IGNORE INTO ignored_updates(update_id,received_utc,reason) VALUES(?,?,?)",
                           (update_id,now(),"no_research_context"))
            return None
        with self.store.tx() as db:
            old = db.execute("SELECT request_id FROM incoming_updates WHERE update_id=? OR "
                             "(chat_id=? AND message_id=?)", (update_id,self.chat_id,message_id)).fetchone()
            if old:
                return old["request_id"]
            # Запись входящего update и запроса — одна транзакция до подтверждения offset.
            db.execute("INSERT INTO incoming_updates(update_id,chat_id,message_id,payload_json,received_utc) "
                       "VALUES(?,?,?,?,?)", (update_id,self.chat_id,message_id,
                                             compact({"text":text,"reply_message_id":reply_id}),now()))
            parent = None
            if reply_bot and type(reply_id) is int:
                parent = db.execute("SELECT r.* FROM outbox o JOIN requests r ON r.id=o.request_id "
                                    "WHERE o.chat_id=? AND o.message_id=? AND o.status='delivered' "
                                    "ORDER BY o.created_utc DESC LIMIT 1", (self.chat_id,reply_id)).fetchone()
            parent = dict(parent) if parent else implicit_parent
            if parent and parent["state"] == "needs_clarification":
                child = db.execute("SELECT id FROM requests WHERE parent_request_id=? "
                                   "AND state IN ('received','running','answer_ready') "
                                   "ORDER BY created_utc DESC LIMIT 1", (parent["id"],)).fetchone()
                if child:
                    db.execute("UPDATE incoming_updates SET request_id=?,processed=1 WHERE update_id=?",
                               (child["id"],update_id))
                    return child["id"]
            summary_links = _links((reply.get("text") or "") if reply_bot else "")
            explicit = _links(text)
            explicit_github = _github_links(text)
            candidates = explicit or (json.loads(parent["candidates_json"]) if parent and
                                       parent["state"] == "needs_clarification" else summary_links)
            parent_id = parent["id"] if parent else None
            article_url = None
            github_repo = explicit_github[0] if len(explicit_github) == 1 else (parent["github_repo"] if parent else None)
            link_basis = parent["link_basis"] if parent else "unconfirmed"
            goal = text if GOAL.search(text) else (parent["goal"] if parent else None)
            original_text = text
            if parent and parent["state"] == "needs_clarification":
                if text.casefold() in ("да", "подтверждаю") and parent["article_url"] and github_repo:
                    article_url = parent["article_url"]
                    link_basis = "user_confirmed"
                    original_text = parent["user_text"] + "\nСвязь репозитория подтверждена пользователем."
                elif text in ("1", "2") and len(candidates) >= int(text):
                    article_url = candidates[int(text)-1]
                    original_text = parent["user_text"] + "\nУточнение: " + text
                elif len(explicit) == 1:
                    article_url = explicit[0]
                    original_text = parent["user_text"] + "\nУточнение: " + text
                elif parent["article_url"] and not explicit:
                    article_url = parent["article_url"]
                    original_text = parent["user_text"] + "\nЦель: " + text
                    goal = text
            elif parent and parent["state"] == "answer_ready":
                article_url = explicit[0] if explicit else parent["article_url"]
                goal = goal or parent["goal"]
            if article_url is None:
                if len(explicit) == 1:
                    article_url = explicit[0]
                elif len(candidates) == 1:
                    article_url = candidates[0]
                elif len(candidates) == 2 and text in ("1", "2"):
                    article_url = candidates[int(text)-1]
            question = None
            if len(candidates) > 1 and article_url is None:
                question = "Какую статью проверить — 1 или 2? Ответь на это сообщение номером."
            elif article_url is None and explicit_github:
                question = "Пришли ссылку на статью Хабра для этого репозитория."
            elif article_url is None and not (text.startswith("/research ") and text[10:].strip()):
                question = "Пришли ссылку на статью Хабра, которую нужно проверить."
            elif len(explicit_github) > 1:
                question = "Пришли одну ссылку на репозиторий проекта."
            elif article_url and github_repo and link_basis == "unconfirmed":
                question = ("Подтверди, что " + github_repo + " — репозиторий проекта из статьи. "
                            "Ответь «да» на это сообщение.")
            elif PERSONAL.search(original_text) and not goal:
                question = "Для какой конкретной задачи тебе нужен этот проект? Ответь на это сообщение."
            state = "needs_clarification" if question else "received"
            ident = self._new_request(db,text=original_text,message_id=message_id,
                                      article_url=article_url,github_repo=github_repo,link_basis=link_basis,
                                      goal=goal,candidates=candidates,
                                      parent_id=parent_id,state=state)
            if question:
                self._queue(db,ident,"clarification",question)
            db.execute("UPDATE incoming_updates SET request_id=?,processed=1 WHERE update_id=?",
                       (ident,update_id))
        return ident

    def process_ready(self) -> None:
        with self.store.connect() as db:
            rows = db.execute("SELECT id,origin_message_id FROM requests WHERE state='received' "
                              "AND chat_id=? ORDER BY created_utc", (self.chat_id,)).fetchall()
        for row in rows:
            try:
                result = self.agent.run(row["id"])
                text = result["answer"]
            except Exception:
                with self.store.tx() as db:
                    db.execute("UPDATE requests SET state='failed',failure_code='research_error',updated_utc=? "
                               "WHERE id=? AND state IN ('received','running')", (now(),row["id"]))
                text = "Исследование не завершилось. Отправь новый /research со ссылкой, чтобы повторить запрос."
            with self.store.tx() as db:
                self._queue(db,row["id"],"answer",text)

    def recover_interrupted(self) -> None:
        with self.store.tx() as db:
            rows = db.execute("SELECT id FROM requests WHERE state='running' AND chat_id=?",
                              (self.chat_id,)).fetchall()
            for row in rows:
                db.execute("UPDATE requests SET state='failed',failure_code='interrupted',updated_utc=? "
                           "WHERE id=?", (now(),row["id"]))
                self._queue(db,row["id"],"answer",
                            "Исследование прервалось. Отправь новый /research со ссылкой для повтора.")

    def deliver_pending(self) -> None:
        with self.store.connect() as db:
            rows = db.execute("SELECT o.*,r.origin_message_id FROM outbox o JOIN requests r "
                              "ON r.id=o.request_id WHERE o.status='pending' AND o.chat_id=? "
                              "ORDER BY o.created_utc", (self.chat_id,)).fetchall()
        for row in rows:
            with self.store.tx() as db:
                changed = db.execute("UPDATE outbox SET status='unknown',attempted_utc=? "
                                     "WHERE id=? AND status='pending'", (now(),row["id"])).rowcount
            if not changed:
                continue
            # AICODE-NOTE: unknown ставится до сети: сбой после send не создаст слепой повтор.
            try:
                message_id = self.bot.send(self.chat_id,row["text"],row["origin_message_id"])
            except TelegramError as error:
                if str(error) == "telegram_rejected":
                    with self.store.tx() as db:
                        db.execute("UPDATE outbox SET status='failed' WHERE id=? AND status='unknown'",
                                   (row["id"],))
                continue
            with self.store.tx() as db:
                db.execute("UPDATE outbox SET status='delivered',message_id=? WHERE id=? AND status='unknown'",
                           (message_id,row["id"]))


def run_poller(service: ChatService, *, lock_path: Path = DATA / "poller.lock",
               once: bool = False) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "r+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise TelegramError("another_poller_active") from error
        service.bot.ensure_no_webhook()
        service.recover_interrupted()
        while True:
            service.process_ready()
            service.deliver_pending()
            for update in service.bot.updates(service.offset()):
                service.accept(update)
                service.process_ready()
                service.deliver_pending()
            if once:
                return
            time.sleep(0.2)
