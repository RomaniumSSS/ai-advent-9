"""Модель выбирает короткие ссылки, доказательство копируется из переданных данных."""
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
from app import public_result
from test_core import Fake, chunk

class ReferenceContract(unittest.TestCase):
    def test_projection_exact_full_original_text(self):
        text='👉 Первая строка.\n  Вторая строка — взаимодействия!\r\n'
        selected=[chunk(text=text)]
        result=core.materialize_references({'answer':'Пересказ.','source_refs':['S1']},selected)
        self.assertEqual(result['quotes'],[{'chunk_id':'a','text':text}])
        self.assertEqual(result['quotes'][0]['text'].encode(),text.encode())
        self.assertEqual(result['sources'],[{'source':'assignment:18','chunk_id':'a'}])
        self.assertTrue(core.validate_answer(result,selected))
    def test_unknown_and_invalid_refs(self):
        selected=[chunk()]
        unknown=core.materialize_references({'answer':'Не знаю по переданному контексту.','source_refs':[]},selected)
        self.assertEqual(unknown['sources'],[]);self.assertEqual(unknown['quotes'],[])
        for refs in (['S1','S1'],['S2'],['s1'],[1],'S1'):
            with self.subTest(refs=refs),self.assertRaises(ValueError):
                core.materialize_references({'answer':'Факт.','source_refs':refs},selected)
        with self.assertRaises(ValueError):core.materialize_references({'answer':'Придуманный факт','source_refs':[]},selected)
    def test_only_model_selected_sources(self):
        selected=[chunk(),chunk('b',day=19,text='Другой оригинал.')]
        result=core.materialize_references({'answer':'Другой факт.','source_refs':['S2']},selected)
        self.assertEqual(result['sources'],[{'source':'assignment:19','chunk_id':'b'}])
        self.assertEqual(result['quotes'][0]['text'],'Другой оригинал.')
    def test_context_references_preserve_text(self):
        text='👉 A\n  B';messages=core.context_messages('Вопрос',[chunk('x'*64,text=text)])
        record=json.loads(messages[1]['content'].split('Контекст:\n')[1])
        self.assertEqual(record['source_ref'],'S1');self.assertEqual(record['text'],text)
        self.assertNotIn('chunk_id',record)
    def test_engine_records_raw_and_projection(self):
        f=Fake();raw={'answer':'Поиск.','source_refs':['S1']};formats=[]
        def chat(messages,schema):
            formats.append(schema);f.response['message']['content']=json.dumps(raw);return f.response
        f.chat=chat
        with patch.object(core,'generation_lock',return_value=nullcontext()):
            result=core.Engine([chunk()],{},f).ask('Задание дня 18')
        self.assertEqual(result['status'],'done');self.assertEqual(formats,[core.SOURCE_SCHEMA])
        self.assertEqual(result['raw_model_answer'],raw)
        self.assertEqual(result['source_reference_map']['S1']['chunk_id'],'a')
        self.assertEqual(result['citation_mode'],'source_references_original_text')
        self.assertEqual(public_result(result)['citation_mode'],'source_references_original_text')
        self.assertNotIn('raw_model_answer',public_result(result))

if __name__=='__main__':unittest.main()
