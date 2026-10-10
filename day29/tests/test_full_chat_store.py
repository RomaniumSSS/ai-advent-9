import copy,json,stat,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,full_chat_core as chat
class Store(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'chat';self.store=chat.ConversationStore(self.root)
    def tearDown(self):self.tmp.cleanup()
    def result(self,cid,rid):return {'conversation_id':cid,'request_id':rid,'status':'done','question':'synthetic question','answer':{'answer':'synthetic answer','sources':[],'source_refs':[]},'query':{'intent':'new_topic','search_query':'synthetic question'}}
    def test_atomic_failed_submission_does_not_leave_ghost_turn(self):
        cid=self.store.create()['conversation_id'];before=self.store.get(cid)
        with patch('core.save_private',side_effect=OSError('synthetic storage failure')):
            with self.assertRaises(OSError):self.store.begin(cid,'synthetic question','b'*32)
        self.assertEqual(self.store.get(cid),before)
    def test_atomic_failed_reset_keeps_previous_conversation(self):
        cid=self.store.create()['conversation_id'];self.store.begin(cid,'synthetic question','b'*32);before=self.store.get(cid)
        with patch('core.save_private',side_effect=OSError('synthetic storage failure')):
            with self.assertRaises(OSError):self.store.reset(cid)
        self.assertEqual(self.store.get(cid),before)
    def test_permissions_persistence_and_recovery_no_repeat(self):
        cid=self.store.create()['conversation_id'];epoch,_,_=self.store.begin(cid,'synthetic question','b'*32);self.store.finish(cid,epoch,self.result(cid,'b'*32));self.store.begin(cid,'unfinished synthetic','c'*32)
        again=chat.ConversationStore(self.root);turns=again.get(cid)['turns'];self.assertEqual(turns[0]['status'],'done');self.assertEqual(turns[1]['status'],'interrupted');self.assertEqual(turns[1]['error']['message'],'request_interrupted_no_retry')
        for path in self.root.rglob('*'):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o700 if path.is_dir() else 0o600)
    def test_reset_discards_late_result_and_new_chat_is_separate(self):
        cid=self.store.create()['conversation_id'];epoch,_,_=self.store.begin(cid,'synthetic question','b'*32);new=self.store.create()
        self.store.reset(cid);self.assertFalse(self.store.finish(cid,epoch,self.result(cid,'b'*32)));self.assertEqual(self.store.get(cid)['turns'],[]);self.assertEqual(self.store.get(new['conversation_id'])['turns'],[])
        with self.assertRaisesRegex(ValueError,'request_not_found'):self.store.request('b'*32)
        receipt=json.loads((self.root/'receipts'/cid/('b'*32+'.json')).read_text());self.assertFalse(receipt['attached_to_history'])
    def test_new_and_reset_have_no_followup_anchor(self):
        c=self.store.create();self.assertEqual(chat.resolve_query('Расскажи подробнее',self.store.get(c['conversation_id'])['turns'])['intent'],'clarification')
        with self.assertRaises(ValueError):self.store.get('../outside')
if __name__=='__main__':unittest.main()
