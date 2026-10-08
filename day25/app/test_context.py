"""T2: synthetic search/generation path, prohibited real network."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import MODEL, packed, save
from conversation import build_context, prepare_generation, HISTORY_BYTES, TASK_BYTES, SEARCH_BYTES, MESSAGES_BYTES, ROLE, bounded_state
from retrieval import retrieve, Config, explicit_days
from service import Service

CHUNK={'chunk_id':'c1','document_id':'assignment:18','source':'assignment','day':18,
       'text':'Факт: RAG использует поиск.', 'vector':[1.0,0.0]}
IDENTITY={'synthetic':True}


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.search_calls=[]
        self.generate_calls=[]
        self.network=patch('requests.Session.request', side_effect=AssertionError('network forbidden'))
        self.network.start()
        def search(question,scope):
            self.search_calls.append((question,scope))
            return {'identity':IDENTITY,'trace':retrieve([CHUNK],question,[1.0,0.0],Config(threshold=0))}
        def generate(body,key):
            self.generate_calls.append(copy.deepcopy(body))
            return {'model':MODEL,'provider':'DeepInfra','usage':{'cost':.00001},
                    'choices':[{'finish_reason':'stop','message':{'content':json.dumps({
                        'answer':'SYNTHETIC_ASSISTANT_ONLY: факт о RAG.',
                        'sources':[{'source':'assignment','chunk_id':'c1'}],
                        'quotes':[{'chunk_id':'c1','text':CHUNK['text']}]},ensure_ascii=False)}}]}
        self.service=Service(self.root,search,generate,lambda _:'synthetic-key',
                             pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        save(self.root/'authorization.json',{'approved':True,'model':MODEL,'provider':'deepinfra/fp8',
             'retries':0,'scopes':['public','all'],'question_policy':'arbitrary',
             'identity_sha256':hashlib.sha256(packed(IDENTITY)).hexdigest(),
             'document_ids':['assignment:18'],'budget':.1})
        self.a=self.service.create_chat('A','public')['chat_id']
        self.b=self.service.create_chat('B','public')['chat_id']

    def tearDown(self):
        self.network.stop()
        self.tmp.cleanup()

    def test_followup_fresh_rag_and_generation_context(self):
        state={'goal':'Изучить RAG', 'clarifications':['На Python'], 'constraints':['Кратко']}
        self.service.update_task_state(self.a,state,0)
        first=self.service.ask(self.a,'one','Какие требования задания дня 18?','public')
        self.assertEqual(first['status'],'verified')
        second=self.service.ask(self.a,'two','а это?','public')
        self.assertEqual(second['status'],'verified')
        self.assertEqual(len(self.search_calls),2)
        query=self.search_calls[-1][0]
        for value in ('а это?', 'Изучить RAG', 'На Python', 'Кратко', 'дня 18'): self.assertIn(value,query)
        self.assertNotIn('SYNTHETIC_ASSISTANT_ONLY',query)
        trace=second['search']['trace']
        self.assertEqual(trace['original_question'],'а это?')
        self.assertEqual(trace['search_query'],query)
        self.assertTrue(trace['conversation']['search_performed'])
        envelope=json.loads(self.generate_calls[-1]['messages'][1]['content'])
        self.assertEqual(envelope['current_question'],'а это?')
        self.assertEqual(envelope['task_state']['constraints'],['Кратко'])
        self.assertEqual([m['request_id'] for m in envelope['recent_messages']],['one','one'])
        self.assertIn('SYNTHETIC_ASSISTANT_ONLY',envelope['recent_messages'][1]['content'])
        self.assertIn(CHUNK['text'],envelope['fresh_rag_context'])
        self.assertIn(ROLE,self.generate_calls[-1]['messages'][0]['content'])
        self.assertEqual(second['generation']['transmitted_chunk_ids'],['c1'])
        self.service.ask(self.a,'three','а это?','public')
        self.assertEqual(len(self.search_calls),3)
        self.service.ask(self.a,'three','а это?','public')
        self.service.get(self.a,'two')
        self.assertEqual(len(self.search_calls),3)
        self.assertEqual(len(self.generate_calls),3)

    def test_memory_change_clear_and_chat_isolation(self):
        self.service.update_task_state(self.b,{'goal':'FOREIGN_SECRET','clarifications':[],'constraints':[]},0)
        self.service.ask(self.b,'foreign','FOREIGN_QUESTION','public')
        self.service.update_task_state(self.a,{'goal':'RAG','clarifications':[],'constraints':['Без кода']},0)
        self.service.ask(self.a,'one','Объясни RAG','public')
        self.service.update_task_state(self.a,{'goal':'MCP','clarifications':['Новичку'],'constraints':['С примером']},1)
        second=self.service.ask(self.a,'two','а это?','public')
        diag=second['conversation']
        self.assertEqual(diag['task_state']['goal'],'MCP')
        self.assertEqual(diag['task_state']['constraints'],['С примером'])
        self.assertNotIn('Без кода',diag['search_query'])
        self.assertNotIn('FOREIGN_',json.dumps(second))
        self.service.clear_task_state(self.a,2)
        third=self.service.ask(self.a,'three','подробнее','public')
        self.assertEqual(third['conversation']['task_state']['goal'],'')
        self.assertEqual(third['conversation']['task_state']['constraints'],[])
        self.assertEqual(self.service.get(self.a,'two')['task_state_version'],2)

    def test_current_explicit_date_day_and_period_do_not_inherit(self):
        self.service.update_task_state(self.a,{'goal':'задание дня 18','clarifications':['29.09.2026'],'constraints':[]},0)
        self.service.ask(self.a,'base','Какие требования задания дня 18?','public')
        for index,question in enumerate(('А требования дня 19?', 'а это 30.09.2026?',
                                         'а за последние дни?', 'а с 28 по 30 сентября 2026?')):
            item=self.service.ask(self.a,'explicit'+str(index),question,'public')
            self.assertEqual(self.search_calls[-1][0],question)
            self.assertEqual(item['conversation']['search_rule'],'explicit_current_day_or_period')
            self.assertNotIn('29.09.2026',item['conversation']['search_query'])
        self.assertEqual(explicit_days(self.search_calls[-4][0]),[19])

    def test_multiple_followups_keep_user_anchor_and_replace_on_topic_change(self):
        first=self.service.ask(self.a,'anchor','Какие требования задания дня 18?','public')
        self.assertEqual(first['status'],'verified')
        for index,question in enumerate(('а это?', 'подробнее', 'продолжи', 'а это?', 'подробнее')):
            item=self.service.ask(self.a,'chain'+str(index),question,'public')
            self.assertEqual(item['status'],'verified')
            self.assertEqual(explicit_days(item['conversation']['search_query']),[18])
            self.assertEqual(item['conversation']['search_anchor_request_id'],'anchor')
            self.assertNotIn('SYNTHETIC_ASSISTANT_ONLY',item['conversation']['search_query'])
            self.assertLessEqual(len(item['conversation']['history']),6)
        self.assertEqual(len(self.search_calls),6)
        self.service.ask(self.a,'new-topic','А требования дня 19?','public')
        item=self.service.ask(self.a,'new-followup','подробнее','public')
        self.assertEqual(explicit_days(item['conversation']['search_query']),[19])
        self.assertEqual(item['conversation']['search_anchor_request_id'],'new-topic')
        self.service.update_task_state(self.a,{'goal':'Изучить MCP','constraints':[], 'clarifications':[]},0)
        item=self.service.ask(self.a,'new-state','подробнее','public')
        self.assertEqual(explicit_days(item['conversation']['search_query']),[])
        self.assertIn('MCP',item['conversation']['search_query'])
        self.assertIsNone(item['conversation']['search_anchor_request_id'])

    def test_live_task_reference_questions_expand_current_state(self):
        scenarios=json.loads((Path(__file__).parents[1]/'validation/scenarios.json').read_text())['scenarios']
        for scenario in scenarios:
            state=dict(scenario['initial_state'],version=1)
            for number,turn in enumerate(scenario['turns'],1):
                if 'state_before' in turn:state=dict(turn['state_before'],version=state['version']+1)
                if (scenario['scope'],number) not in (('public',5),('all',5),('all',12)):continue
                stale={'id':'stale','scope':scenario['scope'],'status':'verified','task_state_version':0,
                       'question':'OLD_GOAL 29.09.2026','answer':{'answer':'ASSISTANT_ONLY'},'search':{'trace':{}}}
                ctx=build_context(turn['question'],state,[stale],scenario['scope'])
                self.assertEqual(ctx['search_rule'],'task_state_and_substantive_user_question')
                self.assertIn(state['goal'],ctx['search_query'])
                self.assertNotIn('OLD_GOAL',ctx['search_query'])
                self.assertNotIn('29.09.2026',ctx['search_query'])
                self.assertNotIn('ASSISTANT_ONLY',ctx['search_query'])
                self.assertIsNone(ctx['search_anchor_request_id'])
        for question in ('Для моей новой цели составь план', 'Для нашей текущей цели выбери проверки',
                         'Дай итоговый план для нашей текущей цели', 'Собери окончательный план для моей цели', 'Помни наш выбор',
                         'Сохрани последний формат', 'Соблюдай действующие ограничения'):
            ctx=build_context(question,dict(state,goal='CURRENT_TASK'),[],'all')
            self.assertIn('CURRENT_TASK',ctx['search_query'])
        for question in ('Для моей текущей цели объясни день 24', 'Помни наш выбор: за 30.09.2026',
                         'Итоговый план за последние дни'):
            ctx=build_context(question,dict(state,goal='OLD_DAY 18 29.09.2026'),[],'all')
            self.assertEqual(ctx['search_query'],question)
        old={'id':'old','scope':'public','status':'verified','task_state_version':3,
             'question':'Какие требования задания дня 18?', 'answer':{'answer':'SQLite'},
             'search':{'trace':{'selected':[CHUNK]}}}
        old_state={'version':3,'goal':'Напоминалка дня 18','clarifications':['SQLite'], 'constraints':[]}
        for question in ('Составь итоговый план изучения PostgreSQL с нуля',
                         'Составь окончательный план переезда в Берлин',
                         'Составь итоговый план переезда в Берлин'):
            independent=build_context(question,old_state,[old],'public')
            self.assertEqual(independent['search_query'],question)
            self.assertEqual(independent['search_rule'],'current_question_only')
            self.assertIsNone(independent['search_anchor_request_id'])
        independent=build_context('Что означает слово цель?',dict(state,goal='UNRELATED_TASK'),[],'all')
        self.assertEqual(independent['search_query'],'Что означает слово цель?')

    def test_actual_generation_contract_keeps_choices_and_source_schema(self):
        state={'version':3,'goal':'Напоминалка','constraints':['Без кода'],
               'clarifications':['Пользователь выбрал SQLite; это пример, не требование']}
        ctx=build_context('Подытожь для моей текущей цели, помни наш выбор',state,[],'public')
        trace=retrieve([CHUNK],ctx['search_query'],[1.,0.],Config(threshold=0))
        prepare_generation(ctx['original_question'],ctx,trace)
        envelope=json.loads(trace['messages'][1]['content'])
        self.assertEqual(envelope['task_state'],state)
        contract=trace['messages'][0]['content']
        for text in ('task_state.clarifications','не заменяй его другим вариантом',
                     'ответ инструмента пользователю и формат сдачи', 'не требуй совпадения их дат',
                     '{"source": "значение source переданного фрагмента", "chunk_id": "chunk_id этого фрагмента"}',
                     'поле source_key недопустимо'):
            self.assertIn(text,contract)
        from answers import check_answer
        bad=json.dumps({'answer':'Факт','sources':[{'source_key':'assignment','chunk_id':'c1'}],
                        'quotes':[{'chunk_id':'c1','text':CHUNK['text']}]})
        self.assertFalse(check_answer(bad,trace['selected'])['valid'])

    def test_format_invariant_blocks_valid_citations_and_recounts_terminal(self):
        self.service.update_task_state(self.a,{'goal':'RAG','constraints':['Не более двух предложений'], 'clarifications':[]},0)
        def generate(body,key):
            return {'model':MODEL,'provider':'DeepInfra','usage':{'cost':.00001},'choices':[{'finish_reason':'stop','message':{'content':json.dumps({
                'answer':'Первый факт. Второй факт. Третий факт.',
                'sources':[{'source':'assignment','chunk_id':'c1'}], 'quotes':[{'chunk_id':'c1','text':CHUNK['text']}]})}}]}
        self.service.generate_fn=generate
        item=self.service.ask(self.a,'format','Объясни RAG','public')
        self.assertEqual(item['status'],'unverified')
        self.assertIn('task_sentence_limit_exceeded',item['validation']['errors'])
        self.assertNotIn('answer',item)
        item.update(stage='validating',status='verified',answer=item['validation']['answer'],validation={'valid':True})
        with self.assertRaisesRegex(ValueError,'verified_invariant_failed'):
            self.service.advance(item,self.service.path('format'),'terminal')
        from task_contract import sentence_count,format_errors
        self.assertEqual(sentence_count('1. Значение 3.14 допустимо.\n2. Второй факт!'),2)
        self.assertEqual(format_errors({'answer':'Первый. Второй.'},item['task_state']),[])
        self.assertEqual(format_errors({'answer':'Первый. Второй. Третий.'},{'constraints':[]}),[])

    def test_saved_public10_blocked_public12_prompt_preserves_selected_return_target(self):
        directory=Path(__file__).parents[1]/'private/live-run-02'
        if not directory.exists():self.skipTest('private live evidence unavailable')
        bad=json.loads((directory/'learn-scheduler-10.json').read_text())
        from task_contract import format_errors
        self.assertEqual(format_errors(bad['answer'],bad['task_state']),['task_sentence_limit_exceeded'])
        self.service.search_fn=lambda *_:copy.deepcopy(bad['search'])
        self.service.generate_fn=lambda *_:copy.deepcopy(bad['raw_response'])
        self.service.update_task_state(self.a,{k:bad['task_state'][k] for k in ('goal','clarifications','constraints')},0)
        # Fixture authorization covers actual public document, but remains synthetic identity/key/cost.
        self.service.search_fn=lambda *_:dict(copy.deepcopy(bad['search']),identity=IDENTITY)
        replay=self.service.ask(self.a,'saved-format',bad['question'],'public')
        self.assertEqual(replay['status'],'unverified')
        self.assertIn('task_sentence_limit_exceeded',replay['validation']['errors'])
        last=json.loads((directory/'learn-scheduler-12.json').read_text())
        original=copy.deepcopy(last)
        ctx=build_context(last['question'],last['task_state'],[],'public')
        trace=copy.deepcopy(last['search']['trace']);prepare_generation(last['question'],ctx,trace)
        requirements=json.loads(trace['messages'][1]['content'])['answer_requirements']
        self.assertEqual(requirements['max_sentences'],2)
        self.assertTrue(requirements['requested_tool_return'])
        self.assertTrue(any('SQLite' in text for text in requirements['selected_user_choices']))
        self.assertIn('а не список альтернатив',requirements['guidance'])
        self.assertIn('возвращаемый инструментом результат',requirements['guidance'])
        self.assertEqual(last,original)

    def test_format_guidance_uses_only_current_explicit_limit(self):
        from task_contract import answer_requirements,format_errors
        base={'version':1,'goal':'RAG','clarifications':[],'constraints':[]}
        unlimited=answer_requirements('Подытожь',base)
        self.assertIsNone(unlimited['max_sentences'])
        self.assertNotIn('предложени',unlimited['guidance'])
        five=dict(base,constraints=['Не более 5 предложений'])
        requirements=answer_requirements('Подытожь',five)
        self.assertEqual(requirements['max_sentences'],5)
        self.assertIn('не более 5 предложений',requirements['guidance'])
        self.assertNotIn('третье',requirements['guidance'])
        self.assertEqual(format_errors({'answer':'Первое. Второе. Третье. Четвёртое. Пятое.'},five),[])
        self.assertEqual(format_errors({'answer':'Первое. Второе. Третье. Четвёртое. Пятое. Шестое.'},five),['task_sentence_limit_exceeded'])

    def test_saved_all10_comparison_contract_uses_given_materials_without_day_label_requirement(self):
        directory=Path(__file__).parents[1]/'private/live-run-03'
        if not directory.exists():self.skipTest('private live evidence unavailable')
        item=json.loads((directory/'rag-course-review-10.json').read_text())
        original=copy.deepcopy(item)
        ctx=build_context(item['question'],item['task_state'],[],'all')
        self.assertEqual(ctx['search_query'],item['question'])
        self.assertEqual(ctx['search_rule'],'explicit_current_day_or_period')
        trace=copy.deepcopy(item['search']['trace']);prepare_generation(item['question'],ctx,trace)
        envelope=json.loads(trace['messages'][1]['content'])
        self.assertTrue(any(c['document_id']=='assignment:22' for c in trace['selected']))
        self.assertTrue(envelope['answer_requirements']['comparison_requested'])
        guidance=envelope['answer_requirements']['comparison_guidance']
        for text in ('Сравнение выполняешь ты','буквальное упоминание номера дня',
                     'связь обоснуй содержанием','не отказывайся от всего сравнения',
                     'текущем вопросе сохраняет приоритет'):
            self.assertIn(text,guidance)
        self.assertIn('источниками',guidance)
        self.assertEqual(envelope['task_state'],item['task_state'])
        self.assertEqual(item,original)
        from task_contract import answer_requirements
        self.assertEqual(answer_requirements('Что такое RAG?',item['task_state'])['comparison_guidance'],'')
        for question in ('Сравни требования за 30.09.2026','Сопоставь условия дня 23',
                         'Сравни обсуждения за последние дни'):
            explicit=build_context(question,item['task_state'],[],'all')
            self.assertEqual(explicit['search_query'],question)

    def test_serialized_memory_budget_includes_json_escaping(self):
        state={'version':0,'goal':'\x00'*1000,'constraints':['\x00'*1000], 'clarifications':[]}
        effective,truncated=bounded_state(state)
        self.assertLessEqual(len(packed(effective)),TASK_BYTES)
        self.assertTrue(truncated)
        context=build_context('а это?',state,[],'public')
        self.assertLessEqual(len(packed(context['task_state'])),TASK_BYTES)

    def test_revoked_corpus_history_does_not_enter_generation(self):
        first=self.service.ask(self.a,'first','Объясни RAG','public')
        self.assertEqual(first['status'],'verified')
        stale=self.service.get(self.a,'first')
        stale['question']='REVOKED_QUESTION'
        stale['answer']['answer']='REVOKED_ANSWER'
        stale['search']['trace']['selected']=[dict(CHUNK,document_id='private:revoked')]
        save(self.service.path('first'),stale)
        second=self.service.ask(self.a,'second','а это?','public')
        self.assertEqual(second['status'],'verified')
        self.assertNotIn('REVOKED_',json.dumps(self.generate_calls[-1]))
        self.assertEqual(second['conversation']['history'],[])
        self.assertEqual(second['conversation']['search_query'],'а это?')

    def test_limits_exclude_failed_and_public_contamination(self):
        state={'version':5,'goal':'я'*4000,'constraints':['ю'*4000]*50,'clarifications':['x'*4000]*50}
        history=[{'id':str(i),'question':'вопрос '*1000,'scope':'public','status':'verified',
                  'answer':{'answer':'ответ '*1000},'search':{'trace':{'selected':[CHUNK]}}} for i in range(10)]
        failed=dict(history[0],id='failed',status='error',question='FAILED_SECRET')
        contaminated=copy.deepcopy(history[0]);contaminated.update(id='bad',question='PRIVATE_SECRET')
        contaminated['search']['trace']['selected']=[dict(CHUNK,document_id='private:note')]
        ctx=build_context('а это?',state,history+[failed,contaminated],'public')
        self.assertLessEqual(len(packed(ctx['history'])),HISTORY_BYTES)
        self.assertLessEqual(len(packed(ctx['task_state'])),TASK_BYTES)
        self.assertLessEqual(len(ctx['history']),6)
        self.assertLessEqual(len(ctx['search_query'].encode()),SEARCH_BYTES)
        self.assertNotIn('SECRET',json.dumps(ctx))
        self.assertTrue(ctx['task_state_truncated'])
        self.assertEqual(set(m['request_id'] for m in ctx['history']),{'8','9'})
        trace={'selected':[dict(CHUNK,chunk_id='large',text='x'*17500)],'removed':[],'counts':{'selected':1}}
        prepare_generation('а это?',ctx,trace)
        self.assertLessEqual(len(packed(trace['messages'])),MESSAGES_BYTES)
        self.assertEqual(trace['counts']['selected'],len(trace['selected']))
        large_question='Что известно? '+('x'*7000)
        large_context=build_context(large_question,state,[], 'public')
        oversized={'selected':[dict(CHUNK,chunk_id='large',text='x'*17500)],'removed':[],'counts':{'selected':1}}
        prepare_generation(large_question,large_context,oversized)
        self.assertTrue(oversized['empty'])
        self.assertEqual(oversized['removed'][0]['removal_reason'],'conversation_messages_bytes')
        self.assertLessEqual(len(packed(oversized['messages'])),MESSAGES_BYTES)
        huge=build_context('а '+('я'*8998),state,history,'public')
        self.assertLessEqual(len(huge['search_query'].encode()),SEARCH_BYTES)


if __name__=='__main__':unittest.main()
