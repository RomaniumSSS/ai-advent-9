"""Offline typed runtime gates on saved failures; original private records are read only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import MODEL,packed,save
from service import Service
from structured_evidence import check_response,metadata_for_reference,model_contract

IDENTITY={'offline_typed_runtime':True}
PRIVATE=Path(__file__).parents[1]/'private/live-run-04'


class StructuredRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.directory=Path(self.tmp.name)
        self.network=patch('requests.Session.request',side_effect=AssertionError('provider forbidden'));self.network.start()
        self.ssh=patch('subprocess.run',side_effect=AssertionError('SSH forbidden'));self.ssh.start()

    def tearDown(self):self.ssh.stop();self.network.stop();self.tmp.cleanup()

    def saved(self,turn):
        if not PRIVATE.exists():self.skipTest('private evidence unavailable')
        return json.loads((PRIVATE/('rag-course-review-'+str(turn).zfill(2)+'.json')).read_text())

    def quoted(self,c):
        part=next(m for m in c['message_parts'] if m.get('attribution')=='single_member')
        return {'chunk_id':c['chunk_id'],'message_id':part['message_id'],'day':c.get('day'),'quote':part['text']}

    def body(self,chunks,comparison=False):
        requirement=next(c for c in chunks if c['document_id']==('assignment:24' if comparison else 'assignment:22'))
        req=self.quoted(requirement)
        data={'answer':'1. SYNTHETIC STRUCTURE TEST: no semantic claim.',
              'sources':[{'source':requirement['source'],'chunk_id':requirement['chunk_id']}],
              'quotes':[{'chunk_id':req['chunk_id'],'text':req['quote']}],
              'attributions':[{k:req[k] for k in ('chunk_id','message_id','day')}]}
        if comparison:
            discussion=next(c for c in chunks if c['source']=='discussion' and c.get('day')==22);right=self.quoted(discussion)
            data['sources'].append({'source':'discussion','chunk_id':discussion['chunk_id']})
            data['quotes'].append({'chunk_id':right['chunk_id'],'text':right['quote']})
            data['comparison']=[{'aspect':'Synthetic comparison','requirement':req,'discussion':right,
                                 'relationship':'supplements','analysis':'SYNTHETIC NOT A SEMANTIC CLAIM'}]
        return data

    def service(self,item,data):
        def search(*_):return {'identity':IDENTITY,'trace':copy.deepcopy(item['search']['trace'])}
        def generate(*_):return {'model':MODEL,'provider':'DeepInfra','usage':{'cost':.00001},
                                'choices':[{'finish_reason':'stop','message':{'content':json.dumps(data,ensure_ascii=False)}}]}
        service=Service(self.directory,search,generate,lambda _:'FAKE',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        save(self.directory/'authorization.json',{'approved':True,'model':MODEL,'provider':'deepinfra/fp8','retries':0,
             'scopes':['all'],'question_policy':'arbitrary','identity_sha256':hashlib.sha256(packed(IDENTITY)).hexdigest(),
             'document_ids':[c['document_id'] for c in item['generation']['transmitted_chunks']],'budget':.1})
        chat=service.create_chat('Offline typed','all')['chat_id']
        service.update_task_state(chat,{k:item['task_state'][k] for k in ('goal','constraints','clarifications')},0)
        return service,chat

    def test_saved_all7_negative_and_exact_positive_binding(self):
        old=self.saved(7);original=copy.deepcopy(old);chunks=old['generation']['transmitted_chunks']
        checked=check_response(old['raw_answer'],chunks,old['question'],old['task_state'])
        self.assertIn('unstructured_message_id',checked['errors']);self.assertFalse(checked['valid'])
        data=self.body(chunks);service,chat=self.service(old,data)
        result=service.ask(chat,'typed7',old['question'],'all')
        self.assertEqual(result['status'],'verified')
        metadata=result['structured_evidence']['attributions'][0]
        self.assertEqual((metadata['day'],metadata['message_id']),(22,4154))
        bad=copy.deepcopy(data);bad['attributions'][0]['message_id']=4082
        checked=check_response(json.dumps(bad),chunks,old['question'],old['task_state'])
        self.assertIn('reference_message_not_in_chunk',checked['errors'])
        self.assertEqual(old,original)

    def test_saved_all10_rows_required_valid_pair_and_terminal_guard(self):
        old=self.saved(10);chunks=old['generation']['transmitted_chunks']
        old_checked=check_response(old['raw_answer'],chunks,old['question'],old['task_state'])
        self.assertIn('comparison_rows_required',old_checked['errors'])
        data=self.body(chunks,True);service,chat=self.service(old,data)
        result=service.ask(chat,'typed10',old['question'],'all')
        self.assertEqual(result['status'],'verified');self.assertIsNone(result['validation']['semantic_match'])
        pair=result['structured_evidence']['comparison'][0]
        self.assertEqual((pair['requirement']['metadata']['day'],pair['discussion']['metadata']['day']),(24,22))
        fake=copy.deepcopy(result);fake['stage']='validating';fake['structured_evidence']['comparison'][0]['discussion']['metadata']['message_id']=999
        with self.assertRaisesRegex(ValueError,'verified_invariant_failed'):service.advance(fake,service.path('typed10'),'terminal')
        bad=copy.deepcopy(data);bad['comparison'][0]['aspect']='message_id 999'
        self.assertIn('unstructured_message_id',check_response(json.dumps(bad),chunks,old['question'],old['task_state'])['errors'])
        bad=copy.deepcopy(data);bad['comparison'][0]['discussion']['quote']='ABSENT QUOTE'
        self.assertIn('reference_quote_not_in_message',check_response(json.dumps(bad),chunks,old['question'],old['task_state'])['errors'])
        bad=copy.deepcopy(data);bad['quotes']=bad['quotes'][:1]
        self.assertIn('comparison_evidence_not_cited',check_response(json.dumps(bad),chunks,old['question'],old['task_state'])['errors'])

    def test_insufficient_branch_non_success_and_no_fake_side(self):
        old=self.saved(10)
        data={'answer':'1. Недостаточно сведений для этого аспекта.','sources':[],'quotes':[],
              'comparison':[{'status':'insufficient_context','aspect':'Synthetic aspect','available_evidence':[],
                             'missing_sides':['requirement','discussion'],'reason':'Нет подтверждения в переданном контексте.'}]}
        service,chat=self.service(old,data);result=service.ask(chat,'missing10',old['question'],'all')
        self.assertEqual(result['status'],'insufficient_context')
        self.assertFalse(result['validation']['valid']);self.assertTrue(result['validation']['structure_valid'])
        fake=copy.deepcopy(result);fake.update(stage='validating',status='verified')
        with self.assertRaisesRegex(ValueError,'verified_invariant_failed'):service.advance(fake,service.path('missing10'),'terminal')
        restored=Service(self.directory,generate_fn=lambda *_:self.fail('restart generated')).get(chat,'missing10')
        self.assertEqual(restored['status'],'insufficient_context')
        self.assertEqual(restored['structured_evidence'],result['structured_evidence'])

    def test_old_records_readable_new_presentation_derived_not_trusted(self):
        old=self.saved(7);service,chat=self.service(old,self.body(old['generation']['transmitted_chunks']))
        legacy=copy.deepcopy(old);legacy.update(id='legacy',chat_id=chat,version='day25-chat-v1')
        path=service.path('legacy');save(path,legacy);before=path.read_bytes()
        self.assertEqual(service.get(chat,'legacy')['answer'],old['answer']);self.assertEqual(path.read_bytes(),before)
        current=service.ask(chat,'current',old['question'],'all');stored=copy.deepcopy(current)
        stored['structured_evidence']['attributions'][0]['message_id']=999;save(service.path('current'),stored)
        self.assertEqual(service.get(chat,'current')['structured_evidence']['attributions'][0]['message_id'],4154)
        self.assertEqual(service.path('legacy').read_bytes(),before)
        stored['generation']['transmission']='unknown';save(service.path('current'),stored)
        hidden=service.get(chat,'current');self.assertEqual(hidden['status'],'unverified');self.assertNotIn('answer',hidden)

    def test_final_member_quote_contract_saved_all5(self):
        root=PRIVATE.parent/'live-run-07'
        if not root.exists():self.skipTest('private run07 evidence unavailable')
        old=json.loads((root/'rag-course-review-05.json').read_text());original=copy.deepcopy(old)
        chunks=old['generation']['transmitted_chunks'];data=json.loads(old['raw_answer'])
        negative=check_response(old['raw_answer'],chunks,old['question'],old['task_state'])
        self.assertEqual(negative['errors'],['attribution_not_cited'])
        contract=model_contract(old['question'],old['task_state'],chunks)
        self.assertEqual(len(contract['participant_citation_examples']),2)
        for pair in contract['participant_citation_examples']:
            ref=dict(pair['attribution'],quote=pair['quote']['text'])
            from structured_evidence import reference_errors
            self.assertEqual(reference_errors(ref,chunks,True),[])
            self.assertEqual(pair['source']['chunk_id'],pair['quote']['chunk_id'])
        self.assertIn('participant B cannot cite participant A',contract['rules'])
        from conversation import build_context,prepare_generation,MESSAGES_BYTES
        context=build_context(old['question'],old['task_state'],[],'all');trace=copy.deepcopy(old['search']['trace'])
        prepare_generation(old['question'],context,trace)
        self.assertLessEqual(len(packed(trace['messages'])),MESSAGES_BYTES)
        envelope=json.loads(trace['messages'][1]['content'])
        self.assertEqual(envelope['evidence_contract']['participant_citation_examples'],contract['participant_citation_examples'])
        public=json.loads((root/'learn-scheduler-08.json').read_text())
        self.assertEqual(model_contract(public['question'],public['task_state'],public['generation']['transmitted_chunks'])['participant_citation_examples'],[])

        service,chat=self.service(old,data)
        self.assertEqual(service.ask(chat,'unchanged-all5',old['question'],'all')['status'],'unverified')
        repaired=copy.deepcopy(data)
        for pair in contract['participant_citation_examples']:repaired['quotes'].append(pair['quote'])
        checked=check_response(json.dumps(repaired),chunks,old['question'],old['task_state'])
        self.assertTrue(checked['valid']);self.assertIsNone(checked['semantic_match'])
        service,chat=self.service(old,repaired)
        self.assertEqual(service.ask(chat,'paired-all5',old['question'],'all')['status'],'verified')
        wrong=copy.deepcopy(repaired);wrong['quotes'][-1]=wrong['quotes'][-2]
        self.assertIn('attribution_not_cited',check_response(json.dumps(wrong),chunks,old['question'],old['task_state'])['errors'])
        self.assertEqual(old,original)

    def test_run06_list_refusal_exact_first_prefix_and_citation_referent(self):
        from task_contract import refusal_text
        from conversation import build_context,generation_messages
        root=PRIVATE.parent/'live-run-06'
        if not root.exists():self.skipTest('private run06 evidence unavailable')
        old=json.loads((root/'rag-course-review-11.json').read_text());original=copy.deepcopy(old)
        data=json.loads(old['raw_answer'])
        self.assertFalse(refusal_text(data))
        service,chat=self.service(old,data)
        self.assertEqual(service.ask(chat,'old-refusal',old['question'],'all')['status'],'unverified')
        good={'answer':'1. Не знаю: числовой SLA не найден в переданном контексте.\n2. Уточни документ или порог.','sources':[],'quotes':[]}
        service,chat=self.service(old,good)
        self.assertEqual(service.ask(chat,'exact-list-refusal',old['question'],'all')['status'],'model_refusal')
        sourced=copy.deepcopy(good);sourced['sources']=[{'source':'assignment','chunk_id':'invented'}]
        self.assertFalse(refusal_text(sourced))
        self.assertEqual(old,original)
        prior=json.loads((root/'learn-scheduler-08.json').read_text())
        current=json.loads((root/'learn-scheduler-09.json').read_text())
        context=build_context(current['question'],current['task_state'],[prior],'public')
        hint=context['continuation_reference'];self.assertEqual(hint['request_id'],prior['id'])
        self.assertEqual(hint['user_question'],prior['question'])
        messages,_=generation_messages(current['question'],context,current['generation']['transmitted_chunks'])
        self.assertEqual(json.loads(messages[1]['content'])['continuation_reference'],hint)
        self.assertIsNone(build_context('А это для дня 22?',current['task_state'],[prior],'public')['continuation_reference'])
        self.assertIsNone(build_context(current['question'],current['task_state'],[dict(prior,scope='all')],'public')['continuation_reference'])
        self.assertIsNone(build_context(current['question'],current['task_state'],[dict(prior,task_state_version=-1)],'public')['continuation_reference'])
        self.assertIsNone(build_context('Что делать для нашей текущей цели?',current['task_state'],[prior],'public')['continuation_reference'])

    def test_chunk_size_discussion_lexical_recall_beyond_vector_top20(self):
        from retrieval import retrieve,Config
        def chunk(ident,text,vec,source='discussion'):
            return {'chunk_id':ident,'document_id':ident,'source':source,'text':text,'vector':vec}
        index=[chunk('d'+str(n),'Unrelated discussion',[1.,0.]) for n in range(25)]
        index.append(chunk('relevant','Размер чанка: длинные чанки и короткие чанки',[.6,.8]))
        question='Найди обсуждения курса о размере чанков для RAG'
        trace=retrieve(index,question,[1.,0.],Config())
        self.assertEqual(trace['selected'][0]['chunk_id'],'relevant')
        self.assertEqual(trace['selected'][0]['selection_reason'],'explicit_chunk_size_discussion')
        self.assertEqual(trace['counts']['vector_candidates'],20)
        self.assertEqual(trace['counts']['topic_candidates'],1)
        self.assertLessEqual(len(trace['selected']),5)
        self.assertNotIn('relevant',[c['chunk_id'] for c in retrieve(index,'Поясни RAG',[1.,0.],Config())['candidates']])
        low=copy.deepcopy(index);low[-1]['vector']=[.01,1.]
        self.assertNotIn('relevant',[c['chunk_id'] for c in retrieve(low,question,[1.,0.],Config())['selected']])
        assignment=chunk('assignment','Размер чанка: длинные чанки',[.6,.8],'assignment')
        self.assertEqual(retrieve(index[:-1]+[assignment],question,[1.,0.],Config())['counts']['topic_candidates'],0)
        def dated(ident,text,day):
            c=chunk(ident,text,[.6,.8]);c['members']=[{'id':1,'date':day,'author':'Synthetic','source_key':ident}]
            c['source_sections']=[{'start_char':0,'end_char':len(text),'text_start_char':0,'member_ids':[1]}]
            return c
        dated_index=[dated('old','Размер чанка: длинные чанки','2026-10-01'),dated('current','No topic here','2026-10-02')]
        filtered=retrieve(dated_index,question+' за 02.10.2026.',[1.,0.],Config())
        self.assertEqual(filtered['counts']['topic_candidates'],0)
        self.assertNotIn('old',[c['chunk_id'] for c in filtered['candidates']])


    def test_numeric_date_terminal_period_overrides_memory_without_partial_dates(self):
        from temporal import date_mentions
        from conversation import build_context
        state={'version':1,'goal':'OLD_GOAL','constraints':[],'clarifications':[]}
        question='Найди обсуждения курса о нашей текущей цели за 01.10.2026.'
        mentions=date_mentions(question)
        self.assertEqual([(m['day'],m['month'],m['year']) for m in mentions],[(1,10,2026)])
        context=build_context(question,state,[],'all')
        self.assertEqual(context['search_rule'],'explicit_current_day_or_period')
        self.assertEqual(context['search_query'],question)
        for malformed in ('01.10.202','01.10.20267','01.10.2026.7','01.10/202','01.10.2026abc','01.10..2026'):
            with self.subTest(malformed=malformed):self.assertEqual(date_mentions('за '+malformed),[])

    def test_point_refusal_and_v2_archive_compatibility(self):
        old=self.saved(10);data={'answer':'Не знаю: нужного факта нет в переданном контексте; уточни период.','sources':[],'quotes':[]}
        service,chat=self.service(old,data)
        item=service.ask(chat,'point-refusal','Есть ли обязательный числовой SLA?','all')
        self.assertEqual(item['status'],'model_refusal')
        root=PRIVATE.parent/'live-run-05'
        record=json.loads((root/'rag-course-review-07.json').read_text())
        record.update(id='old-v2',chat_id=chat)
        path=service.path('old-v2');save(path,record);before=path.read_bytes()
        shown=service.get(chat,'old-v2')
        self.assertEqual(shown['version'],'day25-chat-v2');self.assertEqual(shown['status'],'verified')
        self.assertEqual(shown['answer'],record['answer']);self.assertNotIn('structured_evidence',shown)
        self.assertEqual(path.read_bytes(),before)

    def test_run05_length_role_and_point_repair_contract(self):
        from task_contract import format_errors,answer_requirements
        root=PRIVATE.parent/'live-run-05'
        if not root.exists():self.skipTest('run05 unavailable')
        records={key:json.loads((root/(key+'.json')).read_text()) for key in
                 ('learn-scheduler-04','learn-scheduler-12','rag-course-review-04','rag-course-review-01','rag-course-review-05','rag-course-review-07','rag-course-review-10')}
        ordinary=records['learn-scheduler-04'];contract=model_contract(ordinary['question'],ordinary['task_state'],ordinary['generation']['transmitted_chunks'])
        self.assertFalse(contract['comparison_required']);self.assertNotIn('comparison_row',contract)
        self.assertIn('omit comparison',contract['rules'])
        data=json.loads(ordinary['raw_answer']);data.pop('comparison',None)
        service,chat=self.service(ordinary,data)
        output=service.ask(chat,'ordinary-comparison',ordinary['question'],'all')
        self.assertEqual(output['status'],'verified')
        self.assertEqual(output['answer']['answer'],data['answer'])
        for key in ('rag-course-review-01','rag-course-review-05','rag-course-review-10'):
            record=records[key]
            self.assertEqual(record['raw_response']['choices'][0]['finish_reason'],'length')
            self.assertEqual(record['raw_response']['usage']['completion_tokens'],2048)
            contract=model_contract(record['question'],record['task_state'],record['generation']['transmitted_chunks'])
            self.assertIn('at most 2 comparison aspects',contract['rules'])
            self.assertIn('Do not duplicate typed sides',contract['rules'])
        record=records['rag-course-review-07']
        self.assertTrue(format_errors(record['answer'],record['task_state']))
        self.assertEqual(format_errors({'answer':'1. Индекс и поиск.\n2. Отбор.\n3. Ответ и цитаты.'},record['task_state']),[])
        self.assertEqual(format_errors({'answer':'1. Индекс.\n2. Поиск.\n3. Отбор.\n4. Ответ.'},record['task_state']),['task_point_limit_exceeded'])
        record=records['learn-scheduler-12'];guidance=answer_requirements(record['question'],record['task_state'])['guidance']
        self.assertIn('сохраняемые входные данные',guidance)
        self.assertIn('не называй готовый агент',guidance)
        from conversation import build_context,generation_messages
        record=records['rag-course-review-04']
        context=build_context(record['question'],record['task_state'],[],'all')
        self.assertEqual(context['search_query'],record['question'])
        self.assertEqual(context['search_rule'],'current_question_only')
        continuation=build_context('Найди обсуждения курса о нашей текущей цели.',record['task_state'],[],'all')
        self.assertEqual(continuation['search_rule'],'task_state_and_substantive_user_question')
        self.assertIn(record['task_state']['goal'],continuation['search_query'])
        explicit_reference=build_context('Найди обсуждения курса о нашей текущей цели. Только день 22.',record['task_state'],[],'all')
        self.assertEqual(explicit_reference['search_rule'],'explicit_current_day_or_period')
        self.assertEqual(explicit_reference['search_query'],explicit_reference['original_question'])
        explicit=build_context(record['question']+' Только день 22.',record['task_state'],[],'all')
        self.assertEqual(explicit['search_rule'],'explicit_current_day_or_period')
        record=records['rag-course-review-10']
        context=build_context(record['question'],record['task_state'],[],'all')
        messages,_=generation_messages(record['question'],context,record['generation']['transmitted_chunks'])
        envelope=json.loads(messages[1]['content'])
        self.assertEqual(envelope['answer_requirements']['max_points'],3)
        self.assertTrue(envelope['evidence_contract']['comparison_required'])
        self.assertIn('Do not duplicate typed sides',envelope['evidence_contract']['rules'])


    def test_comparison_inflections_require_rows_through_service(self):
        old=self.saved(10);chunks=old['generation']['transmitted_chunks']
        questions=['Сравните обсуждения курса с требованиями дня24',
                   'Сравнить требования дня24 и обсуждения курса',
                   'Сопоставьте требования дня24 с обсуждениями участников',
                   'Дай сравнение требований дня24 с обсуждениями курса']
        for index,question in enumerate(questions):
            with self.subTest(question=question):
                self.assertTrue(model_contract(question,old['task_state'],chunks)['comparison_required'])
                data=self.body(chunks,True);data.pop('comparison')
                data['sources']=data['sources'][:1];data['quotes']=data['quotes'][:1]
                service,chat=self.service(old,data)
                item=service.ask(chat,'missing-rows-'+str(index),question,'all')
                self.assertEqual(item['status'],'unverified')
                self.assertIn('comparison_rows_required',item['validation']['errors'])
                self.assertEqual(item['conversation']['search_query'],question)
                self.assertFalse(model_contract('Сравните задания дней 21 и 22',old['task_state'],chunks)['comparison_required'])

    def test_generator_contract_required_only_for_requirements_vs_discussion(self):
        old=self.saved(10);chunks=old['generation']['transmitted_chunks']
        self.assertTrue(model_contract(old['question'],old['task_state'],chunks)['comparison_required'])
        self.assertFalse(model_contract('Сравни задания дней 21 и 22',old['task_state'],chunks)['comparison_required'])
        self.assertFalse(model_contract('Что возвращает инструмент?',old['task_state'],chunks)['comparison_required'])
        contract=model_contract(old['question'],old['task_state'],chunks)
        self.assertTrue(any(ref['day']==22 and ref['message_id']==4154 for ref in contract['allowed_attributions']))
        self.assertIn('insufficient_row',contract)


if __name__=='__main__':unittest.main()
