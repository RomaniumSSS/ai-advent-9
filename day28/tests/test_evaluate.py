"""Офлайн orchestration: повторы — отдельные запросы; replay messages неизменны."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import nullcontext
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evaluate
import core
from core import Engine, sha
from test_core import Fake, chunk

class EvaluationContract(unittest.TestCase):
    def run_fixture(self,mode,repeats):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();private=root/'private';private.mkdir()
            messages=[{'role':'system','content':'Exact historical system'},{'role':'user','content':'Exact historical context'}]
            case={'case_id':'F01','question':'Задание дня 18','messages':messages,'selected':[chunk()],
                  'hashes':{'messages_sha256':sha(messages)},'historical_response':{'historical':True},
                  'historical_metrics':{'elapsed_seconds':None},'expected':{'required_document_ids':['assignment:18']}}
            suite={'suite_id':'offline','scope':'public','cases':[case]};suite_path=root/'suite.json'
            suite_path.write_text(json.dumps(suite));output=private/'runs'/'new'
            fake=Fake()
            if mode=='replay':fake.response['message']['content']=json.dumps({'answer':'Поиск.',
                'sources':[{'source':'assignment','chunk_id':'a'}],'quotes':[{'chunk_id':'a','text':'Нужно сделать поиск.'}]})
            engine=Engine([chunk()],{},fake)
            args=argparse.Namespace(suite=suite_path,output=output,index_root=root,mode=mode,repeats=repeats)
            with patch.object(core,'generation_lock',return_value=nullcontext()),patch.object(evaluate,'HERE',root),patch.object(evaluate,'load_index',return_value=({},[chunk()])),patch.object(evaluate,'Engine',return_value=engine):
                self.assertEqual(evaluate.run(args),0)
            run=json.loads((output/'run.json').read_text())
            self.assertEqual(len(run['requests']),repeats)
            self.assertEqual(len({r['request_id'] for r in run['requests']}),repeats)
            receipts=[json.loads((output/r['receipt']).read_text()) for r in run['requests']]
            if mode=='replay':
                self.assertEqual(receipts[0]['messages'],messages)
                self.assertTrue(receipts[0]['messages_identical'])
                self.assertEqual([c[0] for c in fake.calls],['chat'])
                self.assertEqual(fake.formats,[core.SCHEMA])
                self.assertEqual(receipts[0]['citation_mode'],'model_exact_quotes')
            else:self.assertEqual([c[0] for c in fake.calls],['embed','chat']*repeats)
            self.assertIsNone(receipts[0]['assessment']['groundedness_semantic'])
    def test_e2e_two_actual_mock_requests(self):self.run_fixture('e2e',2)
    def test_exact_replay_without_embedding(self):self.run_fixture('replay',1)

if __name__=='__main__':unittest.main()
