"""Только выдуманные источники; ни корпуса, ни Ollama."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
import full_chat_core as chat
import quality_eval as q


def draft():
    body={'current_question':'Как хранится макет?', 'resolved_query':{'intent':'new_topic','search_query':'макет'},
          'history_for_dialogue_only':[{'question':'Макет?', 'answer':'Ранее обсуждался макет.'}],
          'sources':[{'source_ref':'S1','parts':[{'text':'Макет хранится на полке.', 'author':None}]}]}
    return {'status':'done','generation_called':True,'citations_valid':True,'question':body['current_question'],
            'messages':[{'role':'system','content':chat.SYSTEM},{'role':'user','content':core.packed(body).decode()}],
            'answer':{'answer':'На полке.','source_refs':['S1'],'sources':[]},'selected':[],
            'times':{'total':2},'metrics':{'eval_count':4}}


class FakeEngine:
    def __init__(self, receipt=None):self.receipt=receipt or draft();self.calls=[]
    def ask(self,question,turns,conversation_id,**kwargs):
        self.calls.append((question,copy.deepcopy(turns)));return copy.deepcopy(self.receipt)


class FakeClient:
    def __init__(self, answers):self.answers=list(answers);self.calls=[]
    def request(self,path,payload=None):
        self.calls.append((path,copy.deepcopy(payload)))
        item=self.answers.pop(0)
        if isinstance(item,Exception):raise item
        return {'model':core.MODEL,'done':True,'done_reason':'stop','prompt_eval_count':100,
                'eval_count':7,'total_duration':1000000000,'message':{'content':json.dumps(item)}}


ACCEPT={'verdict':'accept','issues':[]}
REPAIR={'verdict':'repair','issues':[{'type':'omission','claim':'полка','reason':'Не раскрыто','source_refs':['S1']}]}


class ProtocolTests(unittest.TestCase):
    def test_shared_draft_false_accept_is_only_opinion(self):
        engine=FakeEngine();client=FakeClient([ACCEPT])
        result=q.execute_pair(engine,{'question':'Как хранится макет?','gold':'SECRET'},[],client)
        self.assertEqual(len(engine.calls),1)
        self.assertEqual(len(client.calls),1)
        self.assertEqual(result['B']['status'],'accepted_by_critic')
        self.assertEqual(result['B']['quality'],'NOT_CHECKED')
        self.assertNotIn('SECRET',json.dumps(client.calls))

    def test_invalid_refs_and_schema_rejected(self):
        for value in ({'verdict':'accept','issues':REPAIR['issues']},
                      {'verdict':'repair','issues':[]},
                      {**REPAIR,'issues':[{**REPAIR['issues'][0],'source_refs':['S9']}]},
                      {**ACCEPT,'gold_verified':True}):
            with self.subTest(value=value),self.assertRaises(ValueError):q.validate_critique(value,{'S1'})

    def test_stage_preserves_whole_context_and_checks_budget(self):
        a=draft();payload=q.critique_payload(a,a['answer'])
        body=json.loads(payload['messages'][1]['content']);original=json.loads(a['messages'][1]['content'])
        for key in original:self.assertEqual(body[key],original[key])
        a['messages'][1]['content']=core.packed({**original,'sources':[{'source_ref':'S1','text':'x'*12000}]}).decode()
        with self.assertRaises(ValueError):q.critique_payload(a,a['answer'])


if __name__=='__main__':unittest.main()
