"""Офлайн-проверки с настоящим stdio MCP и управляемой моделью."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from .agent import Agent, ModelResponse
from .config import PROFILE, ModelProfile, select_profile, TOOL_NAMES
from .mcp_client import McpConfig, discover, execute
from .store import Store, digest

NOW = datetime(2026,9,27,12,0,tzinfo=timezone.utc)
def iso(value):return value.isoformat(timespec="seconds").replace("+00:00","Z")
START = iso(NOW-timedelta(days=1))
END = iso(NOW)

def item(article: int, title: str, excerpt: str, when=NOW-timedelta(hours=2)) -> str:
    return ("<item><title>"+escape(title)+"</title><link>https://habr.com/ru/articles/"
            +str(article)+"/</link><description>"+escape(excerpt)+"</description><pubDate>"
            +format_datetime(when)+"</pubDate></item>")

def feed(*items: str) -> bytes:
    return ("<rss><channel>"+"".join(items)+"</channel></rss>").encode()

CASE1=item(901001,"Компания внедрила ИИ-агента", "Компания использует агента для поддержки клиентов. Пилот сократил время ответа на 20%.")
CASE2=item(901002,"Банк использует ИИ-агента", "Банк запустил агента для помощи сотрудникам.")
OLD=item(901099,"Старый материал про агентов", "Автор описал личный проект агента.",NOW-timedelta(days=2))
PROFILE_A=ModelProfile("fake-a","test/a","fake","none",12000,0.25)
PROFILE_B=ModelProfile("fake-b","test/b","fake","minimal",8000,0.25)

class FakeProvider:
    def __init__(self,mode="normal"):
        self.mode=mode
        self.turn=0
        self.catalogs=[]
    def complete(self,messages,*,tools,max_tokens,tool_choice):
        self.turn+=1
        self.catalogs.append((tuple(t["function"]["name"] for t in tools),tool_choice,max_tokens))
        user=messages[1]["content"]
        run_id=user.split("run_id=",1)[1].split(",",1)[0]
        start=user.split("period_start_utc=",1)[1].split(",",1)[0]
        end=user.split("period_end_utc=",1)[1].split(".",1)[0]
        if self.mode=="premature":
            return ModelResponse({"content":"Готово"},None,"stop")
        if self.mode=="invalid_limit":
            return self.call("unknown_tool",{"run_id":run_id})
        if self.turn==1:
            args={"run_id":run_id,"source_profile_id":PROFILE,"period_start_utc":start,"period_end_utc":end}
            if self.mode=="multiple":
                return ModelResponse({"content":None,"tool_calls":[self.raw_call("collect_habr_agent_cases",args,"a"),
                    self.raw_call("collect_habr_agent_cases",args,"b")]},None,"tool_calls")
            return self.call("collect_habr_agent_cases",args)
        if messages[-1]["role"]!="tool":
            return ModelResponse({"content":"done"},None,"stop")
        result=json.loads(messages[-1]["content"])
        if result["status"] in ("error","no_data","saved"):
            return ModelResponse({"content":"done"},None,"stop")
        if result["status"]=="data_ready":
            entries=[]
            for row in result["model_seen"]:
                metric=[]
                if "20%" in row["rss_excerpt"]:
                    metric=[{"text":"20%","attribution":"автор"}]
                entries.append({"observation_id":row["observation_id"],
                    "category":"confirmed_described_case" if ("компания" in row["title"].casefold() or "банк" in row["title"].casefold()) else "guide",
                    "evidence_refs":["title","rss_excerpt"],
                    "summary":"Компания применяет агента для поддержки клиентов." if "компания" in row["title"].casefold() else "Банк применяет агента для сотрудников." if "банк" in row["title"].casefold() else "",
                    "metric_claims":metric})
            draft={"run_id":run_id,"outcome":"cases_found" if any(e["category"]=="confirmed_described_case" for e in entries) else "no_confirmed_cases",
                   "coverage_label":"partial" if result["coverage"]["kind"]!="complete_for_profile" or result["counts"]["omitted_candidates"] else "complete_for_profile",
                   "entries":entries,"proposed_text":"Обзор найденных материалов."}
            if self.mode=="wrong_id":draft["entries"][0]["observation_id"]="00000000-0000-0000-0000-000000000000"
            if self.mode=="bad_metric":draft["entries"][0]["metric_claims"]=[{"text":"99%","attribution":"автор"}]
            if self.mode=="bad_batch":result["batch_id"]="00000000-0000-0000-0000-000000000000"
            return self.call("prepare_report_preview",{"run_id":run_id,"batch_id":result["batch_id"],"draft":draft})
        if result["status"]=="preview_ready":
            return self.call("save_report",{"run_id":run_id,"preview_id":result["preview_id"],"sha256":result["sha256"]})
        return ModelResponse({"content":"done"},None,"stop")
    def raw_call(self,name,args,ident=None):
        return {"id":ident or f"call_{self.turn}","function":{"name":name,"arguments":json.dumps(args,ensure_ascii=False)}}
    def call(self,name,args):
        return ModelResponse({"content":None,"tool_calls":[self.raw_call(name,args)]},None,"tool_calls")

class Offline(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="day19-test-")
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.rss=self.base/"rss.xml"
        self.db=self.base/"db.sqlite"
        self.out=self.base/"out"
        self.store=Store(self.db)
        self.config=McpConfig(sys.executable,("-m","day19.server","--db",str(self.db),"--output",str(self.out),
                                               "--rss-file",str(self.rss)))
    def put(self,raw):self.rss.write_bytes(raw)
    def run_agent(self,mode="normal",profile=PROFILE_A):
        run=self.store.create_run(START,END)
        provider=FakeProvider(mode)
        trace=Agent(self.store,self.config,provider,profile).run(run,"Собери и сохрани сводку")
        return run,trace,provider
    def args(self,run):return {"run_id":run,"source_profile_id":PROFILE,"period_start_utc":START,"period_end_utc":END}

    def test_catalog_and_successful_causal_chain(self):
        self.put(feed(CASE1,OLD))
        self.assertEqual({t["name"] for t in discover(self.config)},set(TOOL_NAMES))
        run,trace,provider=self.run_agent()
        self.assertEqual(trace["status"],"saved",trace.get("reason"))
        self.assertEqual([t["name"] for t in trace["tool_calls"]],list(TOOL_NAMES))
        self.assertTrue(all(set(c[0])==set(TOOL_NAMES) and c[1]=="auto" for c in provider.catalogs))
        a,b,c=trace["tool_calls"]
        self.assertEqual(b["arguments"]["batch_id"],a["result"]["batch_id"])
        self.assertEqual({x["observation_id"] for x in b["arguments"]["draft"]["entries"]},
                         {x["observation_id"] for x in a["result"]["model_seen"]})
        self.assertEqual(c["arguments"]["preview_id"],b["result"]["preview_id"])
        self.assertEqual(c["arguments"]["sha256"],b["result"]["sha256"])
        path=Path(self.store.run(run)["report_path"])
        self.assertEqual(digest(path.read_text()),c["result"]["sha256"])
        self.assertIn("https://habr.com/ru/articles/901001/",path.read_text())
        self.assertIn("20%",path.read_text())
        self.assertNotIn("901099",path.read_text())

    def test_changed_search_changes_prepare_arguments(self):
        self.put(feed(CASE1,OLD))
        _,one,_=self.run_agent()
        self.put(feed(CASE2,OLD))
        _,two,_=self.run_agent()
        self.assertEqual(one["status"],"saved")
        self.assertEqual(two["status"],"saved")
        self.assertNotEqual(one["tool_calls"][1]["arguments"]["batch_id"],
                            two["tool_calls"][1]["arguments"]["batch_id"])
        self.assertNotEqual(one["tool_calls"][1]["arguments"]["draft"]["entries"][0]["observation_id"],
                            two["tool_calls"][1]["arguments"]["draft"]["entries"][0]["observation_id"])

    def test_backlog_snapshot_current_batch_and_idempotent_save(self):
        third=item(901004,"Компания внедрила третьего агента", "Компания использует агента для клиентов.")
        self.put(feed(CASE1,CASE2,third,OLD))
        first,trace,_=self.run_agent()
        self.assertEqual(trace["status"],"saved")
        self.put(feed(CASE1,CASE2,item(901003,"Компания внедрила агента", "Компания использует агента в работе."),third,OLD))
        second=self.store.create_run(START,END)
        result=execute(self.config,"collect_habr_agent_cases",self.args(second))
        self.assertEqual(result["status"],"data_ready")
        self.assertEqual(len(result["model_seen"]),2)
        self.assertEqual([r["article_id"] for r in result["model_seen"]],["901003","901004"])
        self.assertEqual(result["model_seen"][0]["first_batch_id"],result["batch_id"])
        self.assertEqual(result["model_seen"][1]["first_batch_id"],trace["tool_calls"][0]["result"]["batch_id"])
        saved=trace["tool_calls"][2]
        duplicate=execute(self.config,"save_report",saved["arguments"])
        self.assertEqual(duplicate["status"],"saved")
        self.assertEqual(list(self.out.glob("report-*.txt")).__len__(),1)

    def test_selection_fifteen_new_five_backlog_and_immutable_snapshot(self):
        older=[item(910000+n,"Компания внедрила ИИ-агента", "Компания использует агента для поддержки клиентов.")
               for n in range(8)]
        self.put(feed(*older,OLD))
        _,first,_=self.run_agent()
        self.assertEqual(first["status"],"saved")
        newer=[item(920000+n,"Компания внедрила ИИ-агента", "Компания использует агента для поддержки клиентов.")
               for n in range(17)]
        self.put(feed(*newer,*older,OLD))
        run=self.store.create_run(START,END)
        result=execute(self.config,"collect_habr_agent_cases",self.args(run))
        self.assertEqual(result["status"],"data_ready")
        self.assertEqual(len(result["model_seen"]),20)
        self.assertEqual(result["counts"]["omitted_candidates"],3)
        self.assertEqual(sum(r["first_batch_id"]==result["batch_id"] for r in result["model_seen"]),15)
        self.assertEqual(sum(r["first_batch_id"]!=result["batch_id"] for r in result["model_seen"]),5)
        with self.store.connect() as db:
            with self.assertRaises(Exception):
                db.execute("UPDATE model_seen SET ordinal=99 WHERE batch_id=?",(result["batch_id"],))

    def test_full_empty_partial_empty_and_partial_report(self):
        self.put(feed())
        run,trace,_=self.run_agent()
        self.assertEqual(trace["status"],"no_data")
        self.assertEqual(self.store.run(run)["state"],"no_data")
        self.assertFalse(list(self.out.glob("*.txt")))
        self.put(feed(item(901050,"Рецепт пирога","Кулинария")))
        run,trace,_=self.run_agent()
        self.assertEqual(trace["status"],"failed")
        self.assertEqual(trace["tool_calls"][0]["result"]["status"],"failed")
        self.put(feed(CASE1))
        run,trace,_=self.run_agent()
        self.assertEqual(trace["status"],"saved",trace.get("reason"))
        self.assertIn("Охват неполный",Path(self.store.run(run)["report_path"]).read_text())

    def test_budget_exhausted_has_code_and_no_report(self):
        self.put(feed(CASE1,OLD))
        run=self.store.create_run(START,END,visible_budget_bytes=64)
        result=execute(self.config,"collect_habr_agent_cases",self.args(run))
        self.assertEqual(result["status"],"failed")
        self.assertEqual(result["reason_code"],"budget_exhausted")
        self.assertEqual(result["model_seen"],[])
        self.assertFalse(list(self.out.glob("*.txt")))

    def test_existing_file_recovery_and_output_symlink_rejection(self):
        self.put(feed(CASE1,OLD))
        run=self.store.create_run(START,END)
        a=execute(self.config,"collect_habr_agent_cases",self.args(run))
        draft={"run_id":run,"outcome":"cases_found","coverage_label":"complete_for_profile",
               "proposed_text":"Обзор.","entries":[{"observation_id":a["model_seen"][0]["observation_id"],
                    "category":"confirmed_described_case","evidence_refs":["title","rss_excerpt"],
                    "summary":"Компания использует агента для поддержки.","metric_claims":[]}]}
        b=execute(self.config,"prepare_report_preview",{"run_id":run,"batch_id":a["batch_id"],"draft":draft})
        self.assertEqual(b["status"],"preview_ready")
        with self.store.connect() as db:
            payload=db.execute("SELECT payload FROM previews WHERE id=?",(b["preview_id"],)).fetchone()[0]
        self.out.mkdir()
        path=self.out/f"report-{run}.txt"
        path.write_text(payload)
        self.assertEqual(self.store.run(run)["state"],"preview_ready")
        saved=execute(self.config,"save_report",{"run_id":run,"preview_id":b["preview_id"],"sha256":b["sha256"]})
        self.assertEqual(saved["status"],"saved")
        self.assertEqual(digest(path.read_text()),b["sha256"])
        second=self.store.create_run(START,END)
        self.put(feed(item(901777,"Компания внедрила агента", "Компания использует агента для клиентов."),OLD))
        a=execute(self.config,"collect_habr_agent_cases",self.args(second))
        draft["run_id"]=second
        draft["entries"][0]["observation_id"]=a["model_seen"][0]["observation_id"]
        b=execute(self.config,"prepare_report_preview",{"run_id":second,"batch_id":a["batch_id"],"draft":draft})
        self.assertEqual(b["status"],"preview_ready")
        path.unlink()
        self.out.rmdir()
        self.out.symlink_to(self.base)
        refused=execute(self.config,"save_report",{"run_id":second,"preview_id":b["preview_id"],"sha256":b["sha256"]})
        self.assertEqual(refused["code"],"write_refused")
        self.assertEqual(self.store.run(second)["state"],"preview_ready")

    def test_invalid_json_and_extra_arguments_rejected_locally(self):
        schemas={t["name"]:t["input_schema"] for t in discover(self.config)}
        with self.assertRaisesRegex(ValueError,"invalid_json"):
            Agent._validate_args("save_report","{",schemas,"x")
        with self.assertRaisesRegex(ValueError,"schema_violation"):
            Agent._validate_args("save_report",json.dumps({"run_id":"x","preview_id":"p","sha256":"h","path":"/tmp/x"}),schemas,"x")

    def test_negative_arguments_processing_and_write_refusal(self):
        self.put(feed(CASE1,OLD))
        run=self.store.create_run(START,END)
        bad=execute(self.config,"collect_habr_agent_cases",{**self.args(run),"source_profile_id":"wrong"})
        self.assertEqual(bad["code"],"context_mismatch")
        a=execute(self.config,"collect_habr_agent_cases",self.args(run))
        self.assertEqual(a["status"],"data_ready")
        draft={"run_id":run,"outcome":"cases_found","coverage_label":"complete_for_profile",
               "proposed_text":"Обзор.","entries":[{"observation_id":a["model_seen"][0]["observation_id"],
                    "category":"confirmed_described_case","evidence_refs":["title","rss_excerpt"],
                    "summary":"Компания применяет агента для поддержки клиентов.","metric_claims":[]}]}
        self.assertEqual(execute(self.config,"prepare_report_preview",{"run_id":run,"batch_id":str(__import__('uuid').uuid4()),"draft":draft})["code"],"batch_mismatch")
        wrong=json.loads(json.dumps(draft));wrong["entries"][0]["observation_id"]=str(__import__('uuid').uuid4())
        self.assertEqual(execute(self.config,"prepare_report_preview",{"run_id":run,"batch_id":a["batch_id"],"draft":wrong})["code"],"model_seen_mismatch")
        wrong=json.loads(json.dumps(draft));wrong["entries"][0]["metric_claims"]=[{"text":"99%","attribution":"автор"}]
        self.assertEqual(execute(self.config,"prepare_report_preview",{"run_id":run,"batch_id":a["batch_id"],"draft":wrong})["code"],"unsupported_metric")
        wrong=json.loads(json.dumps(draft));wrong["outcome"]="no_confirmed_cases"
        wrong["entries"][0]["category"]="possible_case"
        wrong["entries"][0]["metric_claims"]=[{"text":"20%","attribution":"автор"}]
        self.assertEqual(execute(self.config,"prepare_report_preview",{"run_id":run,"batch_id":a["batch_id"],"draft":wrong})["code"],"metric_without_confirmed_case")
        b=execute(self.config,"prepare_report_preview",{"run_id":run,"batch_id":a["batch_id"],"draft":draft})
        self.assertEqual(b["status"],"preview_ready")
        self.assertEqual(execute(self.config,"save_report",{"run_id":run,"preview_id":str(__import__('uuid').uuid4()),"sha256":b["sha256"]})["code"],"preview_mismatch")
        self.assertEqual(execute(self.config,"save_report",{"run_id":run,"preview_id":b["preview_id"],"sha256":"0"*64})["code"],"hash_mismatch")
        self.out.write_text("blocked")
        denied=execute(self.config,"save_report",{"run_id":run,"preview_id":b["preview_id"],"sha256":b["sha256"]})
        self.assertEqual(denied["code"],"write_refused")
        self.assertEqual(self.store.run(run)["state"],"preview_ready")
        self.out.unlink()
        self.assertEqual(execute(self.config,"save_report",{"run_id":run,"preview_id":b["preview_id"],"sha256":b["sha256"]})["status"],"saved")

    def test_agent_rejections_and_profiles(self):
        self.put(feed(CASE1,OLD))
        for mode in ("premature","multiple","invalid_limit","wrong_id","bad_metric","bad_batch"):
            with self.subTest(mode=mode):
                run,trace,provider=self.run_agent(mode)
                self.assertEqual(trace["status"],"failed")
                self.assertNotEqual(self.store.run(run)["state"],"saved")
                self.assertEqual(len(trace["tool_calls"]),5 if mode=="invalid_limit" else 2 if mode=="multiple" else 0 if mode=="premature" else 2)
        for index,profile in enumerate((PROFILE_A,PROFILE_B)):
            self.put(feed(item(902000+index,"Компания внедрила ИИ-агента", "Компания использует агента в поддержке клиентов."),OLD))
            run,trace,provider=self.run_agent(profile=profile)
            self.assertEqual(trace["status"],"saved",trace.get("reason"))
            self.assertEqual(provider.catalogs[0][2],profile.max_tokens)
        with self.assertRaisesRegex(ValueError,"unknown_model_profile"):
            select_profile("qwen")
