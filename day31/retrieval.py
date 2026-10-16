"""Небольшой локальный FTS5: только README и Markdown в docs."""
from __future__ import annotations
import hashlib
import re
import sqlite3
import threading
from pathlib import Path
from day31.contracts import SourceChunk

STOP = set('как какой какая какие что это и в на с по для о из ли мне сейчас устроен устроена работает пожалуйста расскажи объясни'.split())
ALIASES = {'архитектура': 'устройство', 'устроен': 'устройство', 'устроена': 'устройство', 'запустить': 'запуск', 'запускается': 'запуск', 'ограничен': 'ограничения', 'ветка': 'ветк', 'ветке': 'ветк', 'ветку': 'ветк', 'текущая': 'текущ'}


ORIGINAL_TERM_LIMIT = 24
ADDED_TERM_LIMIT = 16
ACTION_FORMS = {'действие','действия','действий','действию'}
TOOL_TERMS = ('tool','инструмент','discovery','list_tools')
PARAMETER_TERMS = ('parameters','arguments','input_schema')


def tokens(query: str) -> list[str]:
    words = re.findall(r'[\w]+', query.lower(), flags=re.UNICODE)
    original = list(dict.fromkeys(w for w in words if (w not in STOP or w in ALIASES) and len(w)>1))[:ORIGINAL_TERM_LIMIT]
    technical = any(w in {'mcp','day17'} or w.startswith(('сервер','инструмент','tool')) for w in original)
    expanded = []
    for word in original:
        if word in ALIASES:
            expanded.append(ALIASES[word])
        # AICODE-NOTE: широкое слово «действие» не должно само добавлять MCP-контекст.
        if word.startswith('инструмент') or (word in ACTION_FORMS and technical):
            expanded.extend(TOOL_TERMS)
        if word.startswith('каталог'):
            expanded.extend(('discovery','list_tools'))
        if word.startswith(('параметр','аргумент')):
            expanded.extend(PARAMETER_TERMS)
        if word.startswith('схем'):
            expanded.extend(('schema','input_schema'))
    additions = [w for w in dict.fromkeys(expanded) if w not in original][:ADDED_TERM_LIMIT]
    return [*original,*additions]


class RetrievalIndex:
    def __init__(self, corpus_root: Path, db_path: Path):
        self.root = corpus_root.resolve(strict=True)
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _snapshot(self):
        result = []
        for path in [self.root / 'README.md', *sorted((self.root / 'docs').rglob('*.md'))]:
            relative = path.relative_to(self.root)
            if not path.is_file() or any((self.root / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts)+1)):
                continue
            raw = path.read_bytes()
            if len(raw) > 256_000:
                raise ValueError('Файл корпуса слишком велик')
            result.append((relative.as_posix(), raw.decode('utf-8')))
        return result

    @staticmethod
    def _chunks(path, content):
        lines = content.splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r'^#{1,6}\s', line)]
        if not starts or starts[0] != 0:
            starts.insert(0, 0)
        starts.append(len(lines))
        for a, b in zip(starts, starts[1:]):
            section = lines[a].lstrip('# ').strip() if a < len(lines) else ''
            for start in range(a, b, 45):
                end = min(start+45, b)
                text = '\n'.join(lines[start:end])
                if not text.strip():
                    continue
                digest = hashlib.sha256(text.encode()).hexdigest()
                ident = hashlib.sha256(f'{path}:{start+1}:{end}:{digest}'.encode()).hexdigest()[:20]
                yield SourceChunk(ident, path, start+1, end, section, text, digest)

    def search(self, query: str, limit: int = 5) -> list[SourceChunk]:
        if type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError('limit должен быть от 1 до 8')
        if not isinstance(query, str) or len(query) > 4000:
            raise ValueError('Запрос должен быть строкой до 4000 символов')
        words = tokens(query)
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (fingerprint TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY,path TEXT,start_line INT,end_line INT,section TEXT,text TEXT,sha256 TEXT)')
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED,section,text, tokenize='unicode61')")
            snapshot = self._snapshot()
            fingerprint = hashlib.sha256(repr(snapshot).encode()).hexdigest()
            old = db.execute('SELECT fingerprint FROM metadata').fetchone()
            if old != (fingerprint,):
                db.execute('DELETE FROM search')
                db.execute('DELETE FROM chunks')
                for path, content in snapshot:
                    for chunk in self._chunks(path, content):
                        db.execute('INSERT INTO chunks VALUES (?,?,?,?,?,?,?)', (chunk.id,chunk.path,chunk.start_line,chunk.end_line,chunk.section,chunk.text,chunk.sha256))
                        db.execute('INSERT INTO search VALUES (?,?,?)', (chunk.id,chunk.section,chunk.text))
                db.execute('DELETE FROM metadata')
                db.execute('INSERT INTO metadata VALUES (?)', (fingerprint,))
            if not words:
                return []
            match = ' OR '.join('"'+word+'"*' for word in words)
            rows = db.execute('SELECT chunks.*, -bm25(search,0,3,1) AS score FROM search JOIN chunks ON chunks.id=search.id WHERE search MATCH ? ORDER BY bm25(search,0,3,1),chunks.id LIMIT ?', (match, limit)).fetchall()
            return [SourceChunk(*row) for row in rows]
