"""Явный legacy/evidence контракт без угадывания клиента/ответа и без fallback."""
from contextlib import nullcontext,redirect_stdout
import io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,full_chat_core as chat,full_chat
from test_full_chat_contract import chunk
from test_full_chat_runtime import Client

class ProtocolCompatibility(unittest.TestCase):
 def ask(self,engine,client):
  with patch('core.generation_lock',return_value=nullcontext()):return engine([chunk('d')],{},client).ask('Что описано в макете?',[],'a'*32)
 def test_legacy_engine_preserves_source_schema_and_four_body_fields(self):
  client=Client({'answer':'Макет описан в источнике.','source_refs':['S1']})
  result=self.ask(chat.ChatEngine,client);self.assertEqual(result['status'],'done')
  self.assertEqual(result['payload']['format'],core.SOURCE_SCHEMA)
  body=json.loads(result['messages'][1]['content'])
  self.assertEqual(set(body),{'current_question','resolved_query','history_for_dialogue_only','sources'})
  self.assertIn('parts',body['sources'][0]);self.assertNotIn('units',body['sources'][0])
  self.assertEqual(sum(p=='/api/chat' for p,_ in client.calls),1)
 def test_evidence_engine_is_explicit_and_rejects_legacy_response_without_retry(self):
  self.assertTrue(hasattr(chat,'EvidenceChatEngine'))
  client=Client();result=self.ask(chat.EvidenceChatEngine,client);self.assertEqual(result['status'],'done')
  self.assertIn('evidence',result['payload']['format']['properties']);self.assertIn('units',json.loads(result['messages'][1]['content'])['sources'][0])
  legacy=Client({'answer':'Legacy response','source_refs':['S1']});result=self.ask(chat.EvidenceChatEngine,legacy)
  self.assertEqual(result['status'],'error');self.assertEqual(sum(p=='/api/chat' for p,_ in legacy.calls),1)
 def test_http_entrypoint_constructs_only_evidence_engine(self):
  self.assertTrue(hasattr(chat,'EvidenceChatEngine'));captured=[]
  with patch.object(full_chat,'load_full_index',return_value=({},[chunk('d')])),patch.object(full_chat,'ConversationStore'),patch.object(full_chat,'handler_for',side_effect=lambda app:captured.append(app) or object()),patch.object(full_chat,'ThreadingHTTPServer') as server,redirect_stdout(io.StringIO()):
   server.return_value.serve_forever.side_effect=KeyboardInterrupt
   self.assertEqual(full_chat.main(['--index-root','/synthetic-unused-index']),0)
  self.assertIsInstance(captured[0].engine,chat.EvidenceChatEngine)
if __name__=='__main__':unittest.main()
