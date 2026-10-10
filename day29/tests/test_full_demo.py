"""Delivery gate и сценарий, только синтетические receipts; сеть/Chromium не нужны."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
import core
import full_chat_core as chat
spec=importlib.util.spec_from_file_location('full_demo',BASE/'video/run_full_demo.py');demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)

CID='a'*32;RID='b'*32;QUESTION='Что нужно сделать в задании дня 11?'

def full_receipts():
    selected=[{'source':'assignment','chunk_id':'c1','document_id':'assignment:11','text':'Выдуманный публичный источник.'},
              {'source':'discussion','chunk_id':'hidden','document_id':'invented-private','text':'Синтетический скрытый selected, не показывает UI.'}]
    answer={'answer':'Ответ из публичного задания.','source_refs':['S1'],'sources':[{**selected[0],'request_id':RID,'source_ref':'S1'}]}
    turn={'request_id':RID,'run_id':'f'*32,'conversation_id':CID,'question':QUESTION,'status':'done','citations_valid':True,'answer':answer,
          'model':core.MODEL,'options':chat.OPTIONS,'started_at':'2026-01-01T00:00:04+00:00','finished_at':'2026-01-01T00:00:05+00:00'}
    messages=[{'role':'system','content':chat.SYSTEM},{'role':'user','content':'Синтетический envelope'}]
    receipt={**turn,'scope':'all','generation_called':True,'selected':selected,'digest':core.GEN_DIGEST,
             'embedding_model':core.EMBED_MODEL,'embedding_digest':core.EMBED_DIGEST,
             'index':{'generation':core.GENERATION,'db_sha256':core.DB_SHA},'messages':messages,'payload':core.profile_payload(chat.PROFILE,messages),
             'model_identity':{'generator_digest':core.GEN_DIGEST,'embedding_digest':core.EMBED_DIGEST}}
    return turn,receipt


def benchmark_receipt(profile='baseline',rid='d'*32):
    step=demo.actions()[0 if profile=='baseline' else 1]
    selected=[{'source':'assignment','chunk_id':'bench'+str(day),'document_id':'assignment:'+str(day),'text':'Выдуманный public текст.'} for day in (19,20)]
    p=core.load_profiles()[profile]
    return {'request_id':rid,'run_id':'e'*32,'profile_id':profile,'profile_sha256':core.sha(p),'generation_options':p['options'],
        'model':core.MODEL,'digest':core.GEN_DIGEST,'generation_called':True,'index':{'generation':core.GENERATION,'db_sha256':core.DB_SHA},
        'model_identity':{'generator_digest':core.GEN_DIGEST,'embedding_digest':core.EMBED_DIGEST},
        'started_at':'2026-01-01T00:00:02+00:00','finished_at':'2026-01-01T00:00:03+00:00',
        'status':'done','question':step['question'],'scope':'public','citations_valid':True,'selected':selected,
        'answer':{'answer':'Выдуманный ответ.','sources':[{'source':c['document_id'],'chunk_id':c['chunk_id']} for c in selected],
                  'quotes':[{'chunk_id':c['chunk_id'],'text':c['text']} for c in selected]}}

def benchmark_state():
    # Frozen public API projection: no system/digest in /api/state.
    return {'run_id':'e'*32,'model':core.MODEL,'embedding_model':core.EMBED_MODEL,'scope':'public',
        'profiles':{k:{'options':p['options'],'quantization':p['quantization'],'model':p['model']} for k,p in core.load_profiles().items()},
        'selected_profile':'candidate','index':{'generation':core.GENERATION,'db_sha256':core.DB_SHA}}


def dry_fixture(root,quality=None):
    root=Path(root);turn,receipt=full_receipts();storage=root/'storage';dest=storage/'receipts'/CID;dest.mkdir(parents=True)
    (dest/(RID+'.json')).write_text(json.dumps(receipt));check=demo.validate_full(turn,receipt,CID,QUESTION)
    bench=[benchmark_receipt('baseline','1'*32),benchmark_receipt('candidate','2'*32)]
    state=benchmark_state()
    fullstate={'run_id':'f'*32,'model':core.MODEL,'options':chat.OPTIONS,'scope':'all','index':{**receipt['index'],'chunk_count':724,'document_count':663}}
    value={'mode':'dry-run','status':'completed','run_id':'d'*32,'actions':demo.actions(),'script_sha256':demo.file_sha(demo.__file__),
        'requests':[{'app':'benchmark','profile_id':p,'request_id':a['request_id'],'status':'done','actual':a,'ui_answer_matches_receipt':True} for p,a in zip(['baseline','candidate'],bench)],
        'quality_summary':quality,'benchmark_state':state,'full_state':fullstate,'page_errors':[],'privacy_gate_errors':[],
        'privacy_gate_checks':{RID:check},'live_pair_same_input':True,'started_at':'2026-01-01T00:00:01+00:00','finished_at':'2026-01-01T00:00:06+00:00',
        'submission_attempts':[{'app':'benchmark','profile_id':'baseline'},{'app':'benchmark','profile_id':'candidate'},{'app':'full_chat'}],'frames':[]}
    value['requests'].append({'app':'full_chat','request_id':RID,'conversation_id':CID,'status':'done','actual':turn,
        'receipt_sha256':core.sha(receipt),'qualification':check,'ui_answer_matches_receipt':True})
    names=['baseline-candidate-identity','parameter-temperature','parameter-max-output','parameter-context','live-baseline','live-candidate','historical-table',
           'full-index-own-empty-history','live-full-public-question','durable-own-history-after-reload','own-history-reset','own-new-conversation']
    if quality is not None:names.append('saved-five-new-questions')
    for name in names:
        path=root/(name+'.png');path.write_bytes(b'synthetic artifact, no real screenshot')
        value['frames'].append({'name':name,'file':path.name,'sha256':demo.file_sha(path)})
    path=root/'results.json';path.write_text(json.dumps(value));return path,value,storage


class DeliveryTests(unittest.TestCase):
    def test_canonical_benchmark_materialized_sources_and_exact_quotes(self):
        actual=benchmark_receipt();step=demo.actions()[0]
        self.assertEqual({s['source'] for s in actual['answer']['sources']},{'assignment:19','assignment:20'})
        demo.validate_benchmark(actual,step,actual['request_id'])
        for wrong in ('assignment19','assignment:18','personal_note:19'):
            bad=copy.deepcopy(actual);bad['answer']['sources'][0]['source']=wrong
            with self.subTest(source=wrong),self.assertRaises(ValueError):demo.validate_benchmark(bad,step,bad['request_id'])
        for kind in ('missing_source','wrong_chunk','missing_quote','changed_quote'):
            bad=copy.deepcopy(actual)
            if kind=='missing_source':bad['answer']['sources'].pop()
            elif kind=='wrong_chunk':bad['answer']['sources'][0]['chunk_id']='unknown'
            elif kind=='missing_quote':bad['answer']['quotes'].pop()
            else:bad['answer']['quotes'][0]['text']='Текст вне источника.'
            with self.subTest(kind=kind),self.assertRaises(ValueError):demo.validate_benchmark(bad,step,bad['request_id'])

    def test_benchmark_public_state_projection_matches_served_contract(self):
        state=benchmark_state()
        self.assertEqual(set(state['profiles']['baseline']),{'options','model','quantization'})
        demo.validate_state('benchmark',state)

    def test_benchmark_public_state_rejects_changed_options_model_quantization_and_ids(self):
        for mutation in ('options','model','quantization','missing_id','extra_id'):
            state=benchmark_state()
            if mutation=='options':state['profiles']['baseline']['options']={**state['profiles']['baseline']['options'],'num_ctx':4096}
            elif mutation in ('model','quantization'):state['profiles']['baseline'][mutation]='wrong'
            elif mutation=='missing_id':state['profiles'].pop('prompt')
            else:state['profiles']['unexpected']=copy.deepcopy(state['profiles']['baseline'])
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):demo.validate_state('benchmark',state)

    def test_canonical_full_assignment_document_id_metadata_shape(self):
        turn,receipt=full_receipts()
        for c in receipt['selected']:
            if c['source']=='assignment':c['document_id']='assignment:11'
        turn['answer']['sources'][0]['document_id']='assignment:11';receipt['answer']=turn['answer']
        self.assertEqual(demo.validate_full(turn,receipt,CID,QUESTION)['cited_public_count'],1)
        for docid in ('assignment11','assignment:12','personal_note:11'):
            badturn,badreceipt=full_receipts();badturn['answer']['sources'][0]['document_id']=docid
            badreceipt['selected'][0]['document_id']=docid;badreceipt['answer']=badturn['answer']
            with self.subTest(docid=docid),self.assertRaises(ValueError):demo.validate_full(badturn,badreceipt,CID,QUESTION)

    def test_wrong_benchmark_model_profile_options_index_rejected(self):
        base=benchmark_receipt()
        for patch in ({'model':'wrong'},{'digest':'wrong'},{'profile_sha256':'wrong'},
                      {'generation_options':{**base['generation_options'],'temperature':.8}},
                      {'index':{'generation':'wrong','db_sha256':core.DB_SHA}},
                      {'index':{'generation':core.GENERATION,'db_sha256':'wrong'}}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):demo.validate_benchmark({**base,**patch},demo.actions()[0],base['request_id'])

    def test_wrong_full_model_digest_options_index_rejected(self):
        turn,receipt=full_receipts()
        receipt.update(model=core.MODEL,digest=core.GEN_DIGEST,options=chat.OPTIONS,index={'generation':core.GENERATION,'db_sha256':core.DB_SHA})
        for patch in ({'model':'wrong'},{'digest':'wrong'},{'options':{**chat.OPTIONS,'num_ctx':4096}},
                      {'index':{'generation':'wrong','db_sha256':core.DB_SHA}},
                      {'index':{'generation':core.GENERATION,'db_sha256':'wrong'}}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):demo.validate_full(turn,{**receipt,**patch},CID,QUESTION)

    def test_empty_three_records_cannot_qualify_as_live_dry(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'results.json';value={'mode':'dry-run','status':'completed','run_id':'d'*32,'actions':demo.actions(),
                'script_sha256':demo.file_sha(demo.__file__),'requests':[{}, {}, {}]};path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):demo.qualify(path,demo.actions())

    def test_qualification_rejects_partial_error_duplicate_replay_and_frame_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            path,original,storage=dry_fixture(temp)
            def duplicate(value):value['requests'][1]['request_id']=value['requests'][0]['request_id']
            def stale(value):value['requests'][0]['actual']['started_at']='2020-01-01T00:00:00+00:00'
            def wrong_context(value):value['requests'][1]['actual']['selected'][0]['text']='Другой synthetic текст.'
            def changed_frame(value):value['frames'][0]['sha256']='wrong'
            def wrong_options(value):value['full_state']['options']={'temperature':.7}
            changes=[lambda v:v['requests'].pop(),lambda v:v['requests'][0].update(status='error'),duplicate,stale,wrong_context,changed_frame,wrong_options,
                     lambda v:v['page_errors'].append('synthetic'),lambda v:v['privacy_gate_errors'].append('synthetic'),
                     lambda v:v['requests'][2].update(qualification={})]
            for change in changes:
                value=copy.deepcopy(original);change(value);path.write_text(json.dumps(value))
                with self.subTest(change=change.__name__),self.assertRaises(ValueError):demo.qualify(path,demo.actions(),storage=storage)

    def test_state_wrong_scope_profile_index_and_model_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            _,value,_=dry_fixture(temp)
            for kind,key in [('benchmark','benchmark_state'),('full_chat','full_state')]:
                for patch in ({'model':'wrong'},{'scope':'wrong'},{'index':{'generation':'wrong','db_sha256':core.DB_SHA}}):
                    with self.subTest(kind=kind,patch=patch),self.assertRaises(ValueError):demo.validate_state(kind,{**value[key],**patch})

    def test_exact_three_public_actions(self):
        steps=demo.actions();self.assertEqual(len(steps),3)
        self.assertEqual([s.get('profile_id') for s in steps[:2]],['baseline','candidate'])
        self.assertEqual(steps[-1]['question'],QUESTION)
        with self.assertRaises(ValueError):demo.actions(18)

    def test_hidden_private_selected_allowed_cited_private_rejected(self):
        turn,receipt=full_receipts();check=demo.validate_full(turn,receipt,CID,QUESTION)
        self.assertEqual(check['hidden_private_selected_count'],1)
        turn=copy.deepcopy(turn);turn['answer']['sources'][0]['source']='discussion';receipt['answer']=turn['answer']
        with self.assertRaisesRegex(ValueError,'private_cited'):demo.validate_full(turn,receipt,CID,QUESTION)

    def test_original_and_request_scope_are_checked(self):
        for key,value in [('text','Похожий, но неверный текст.'),('request_id','c'*32)]:
            turn,receipt=full_receipts();turn=copy.deepcopy(turn);turn['answer']['sources'][0][key]=value;receipt['answer']=turn['answer']
            with self.assertRaisesRegex(ValueError,'original_mismatch'):demo.validate_full(turn,receipt,CID,QUESTION)

    def test_existing_private_history_hidden_without_mutating_backend(self):
        gate=demo.CaptureGate(Path('/not-used'),QUESTION)
        original={'conversations':[{'conversation_id':'c'*32,'turn_count':5},{'conversation_id':CID,'turn_count':1}]}
        gate.owned.add(CID);filtered=gate.filter_response('/api/conversations','GET',original)
        self.assertEqual(filtered['conversations'],[original['conversations'][1]]);self.assertEqual(len(original['conversations']),2)
        with self.assertRaisesRegex(ValueError,'private_conversation'):gate.filter_response('/api/conversations/'+'c'*32,'GET',{'conversation_id':'c'*32,'turns':[]})

    def test_private_terminal_answer_blocked_before_dom(self):
        with tempfile.TemporaryDirectory() as temp:
            gate=demo.CaptureGate(temp,QUESTION);gate.owned.add(CID);gate.requests.add(RID)
            turn,receipt=full_receipts();turn['answer']['sources'][0]['source']='personal_note';receipt['answer']=turn['answer']
            target=Path(temp)/'receipts'/CID;target.mkdir(parents=True);(target/(RID+'.json')).write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'private_cited'):gate.filter_response('/api/requests/'+RID,'GET',turn)

    def test_unowned_reset_rejected_before_forwarding(self):
        class Request:
            url=demo.FULL+'/api/reset';method='POST';post_data_json={'conversation_id':'c'*32}
        class Response:
            status=200
            def json(self):return {'conversation_id':'c'*32,'turns':[]}
        class Route:
            request=Request();calls=0
            def fetch(self):self.calls+=1;return Response()
            def fulfill(self,**kwargs):self.fulfilled=kwargs
        route=Route();gate=demo.CaptureGate('/not-used',QUESTION);gate.route(route)
        self.assertEqual(route.calls,0);self.assertEqual(route.fulfilled['status'],409)

    def test_record_requires_matching_successful_dry(self):
        with tempfile.TemporaryDirectory() as temp:
            path,value,storage=dry_fixture(temp)
            self.assertEqual(demo.qualify(path,demo.actions(),storage=storage)['run_id'],value['run_id'])
            with self.assertRaises(ValueError):demo.qualify(path,demo.actions(16),storage=storage)
            value['fixture_only']=True;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):demo.qualify(path,demo.actions(),storage=storage)
            value.pop('fixture_only')
            value['status']='error';path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):demo.qualify(path,demo.actions(),storage=storage)

    def test_gate_error_aborts_wait_without_timeout_or_retry(self):
        gate=demo.CaptureGate('/not-used',QUESTION);gate.errors.append('synthetic privacy gate')
        with self.assertRaisesRegex(ValueError,'before_dom'):demo.wait_terminal(None,None,gate)

    def test_optional_quality_html_must_be_public_path(self):
        self.assertIsNone(demo.quality_snapshot(None))
        with self.assertRaisesRegex(ValueError,'public_quality'):demo.quality_snapshot(BASE/'private/full-chat/not-public.html')

    def test_quality_summary_hash_is_frozen_across_dry_record(self):
        with tempfile.TemporaryDirectory() as temp:
            quality={'file':'five.html','sha256':'original'};path,value,storage=dry_fixture(temp,quality)
            demo.qualify(path,demo.actions(),quality,storage)
            with self.assertRaises(ValueError):demo.qualify(path,demo.actions(),{**quality,'sha256':'changed'},storage)


if __name__=='__main__':unittest.main()
