"""Stdlib synthetic invariants; fake vectors are never real model evidence."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import index_pipeline as p

class Characters:
    identity={'model':'synthetic_character_counter','revision':'synthetic'}
    def count(self,text):return len(text)
    def offsets(self,text):return [(i,i+1) for i in range(len(text))]

class FakeEmbedder:
    batch_size=8
    calls=0;inputs=0;seconds=0;prompt_eval_count=0
    def embed(self,texts):
        self.calls+=1;self.inputs+=len(texts)
        return [[1.0]+[0.0]*1023 for _ in texts]

class PipelineTest(unittest.TestCase):
    def setUp(self):self.tokenizer=Characters()
    def document(self,text='Вопрос?\n\nДа.'):return {'document_id':'synthetic','source':'discussion','title':'Synthetic','text':text,'members':[{'source_key':'telegram:1','author':'synthetic','date':'synthetic','source_file':'synthetic.html','source_line':1,'version_hash':'v'}]}
    def test_fixed_unicode_reencode_coverage(self):
        text='🧪界́abc '*150;ranges=p.fixed_ranges(text,self.tokenizer)
        self.assertTrue(all(self.tokenizer.count(text[a:b])<=400 for a,b in ranges))
        self.assertEqual(ranges[0][0],0);self.assertEqual(ranges[-1][1],len(text))
        self.assertTrue(all(a[1]-b[0]==60 for a,b in zip(ranges,ranges[1:])))
        result=p.chunks(self.document(text),ranges,'fixed',self.tokenizer,{})
        self.assertEqual(result,p.chunks(self.document(text),ranges,'fixed',self.tokenizer,{}))
        self.assertTrue(all(r['text']==text[r['start_char']:r['end_char']] for r in result))
    def test_qa_priority_over_transition(self):
        d=self.document();d['sections']=[{'start_char':0,'end_char':9,'message_id':1,'source_keys':['telegram:1']},{'start_char':9,'end_char':len(d['text']),'message_id':2,'reply_to':1,'source_keys':['telegram:2']}]
        # Opposite vectors indicate a transition, but the explicit QA fits as one chunk.
        e=FakeEmbedder();e.embed=lambda texts:[[1.0]+[0.0]*1023,[-1.0]+[0.0]*1023]
        ranges,stats=p.structure_ranges(d,self.tokenizer,e)
        self.assertEqual(ranges,[(0,len(d['text']))]);self.assertTrue(stats['whole_document_preserved']);self.assertEqual(stats['transition_inputs'],0)
    def test_long_thought_split_and_coverage(self):
        d=self.document('🧪'*1001);ranges,stats=p.structure_ranges(d,self.tokenizer,FakeEmbedder())
        self.assertGreater(stats['forced_breaks'],0)
        self.assertTrue(all(b-a<=400 for a,b in ranges));p.chunks(d,ranges,'structure',self.tokenizer,{})
    def test_sentence_and_paragraph_boundaries(self):
        d=self.document(('Пример. '*40)+'\n\n'+('Объяснение. '*40));ranges,_=p.structure_ranges(d,self.tokenizer,FakeEmbedder())
        p.chunks(d,ranges,'structure',self.tokenizer,{})
    def test_bounded_transitions_and_qa_survives_big_merge(self):
        d=self.document('X'*300+'Q'*60+'A'*60+'Z'*300)
        d['sections']=[{'start_char':0,'end_char':300,'message_id':9},{'start_char':300,'end_char':360,'message_id':1},
                       {'start_char':360,'end_char':420,'message_id':2,'reply_to':1},{'start_char':420,'end_char':720,'message_id':10}]
        e=FakeEmbedder();original=e.embed
        def bounded(texts):
            self.assertTrue(all(len(t)<=400 for t in texts));return original(texts)
        e.embed=bounded;ranges,_=p.structure_ranges(d,self.tokenizer,e)
        self.assertTrue(any(a<=300 and b>=420 for a,b in ranges));p.chunks(d,ranges,'structure',self.tokenizer,{})
    def test_missing_database_row_fails_completed_fastpath(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            report=p.build_pair([self.document()],self.tokenizer,FakeEmbedder(),directory,{'digest':'d'})
            db=Path(directory)/report['generation']/'fixed.db'
            conn=sqlite3.connect(db);conn.execute('DELETE FROM chunks');conn.commit();conn.close()
            with self.assertRaises(ValueError):p.build_pair([self.document()],self.tokenizer,FakeEmbedder(),directory,{'digest':'d'})

    def test_long_part_keeps_transition_candidates_separate(self):
        d=self.document('A'*220+'\n\n'+'B'*220+'\n\n'+'C'*220)
        e=FakeEmbedder();seen=[]
        def embed(texts):
            seen.extend(texts);return [[1.0]+[0.0]*1023 for _ in texts]
        e.embed=embed;ranges,stats=p.structure_ranges(d,self.tokenizer,e)
        self.assertEqual(len(seen),3);self.assertTrue(all(len(x)<=400 for x in seen))
        p.chunks(d,ranges,'structure',self.tokenizer,{})

    def test_seven_bullet_thoughts_are_not_sentence_fragments(self):
        text='\n'.join('- '+('Объяснение. Пример. '*5) for _ in range(7))
        d=self.document(text);e=FakeEmbedder();seen=[]
        def embed(texts):
            seen.extend(texts);return [[1.0]+[0.0]*1023 for _ in texts]
        e.embed=embed;ranges,stats=p.structure_ranges(d,self.tokenizer,e)
        self.assertEqual(len(seen),7)
        self.assertTrue(all(item.startswith('- ') and 'Объяснение. Пример.' in item for item in seen))
        p.chunks(d,ranges,'structure',self.tokenizer,{})
    def test_oversized_paragraph_uses_sentences_only_after_natural_boundary(self):
        text=('Одно предложение. '*35)+'\n\n'+'Короткий пункт. Пример.'
        e=FakeEmbedder();seen=[]
        def embed(texts):
            seen.extend(texts);return [[1.0]+[0.0]*1023 for _ in texts]
        e.embed=embed;p.structure_ranges(self.document(text),self.tokenizer,e)
        self.assertIn('Короткий пункт. Пример.',seen)
        self.assertTrue(all(len(item)<=400 for item in seen))

    def test_fitting_reviewed_discussion_skips_transition_pass(self):
        d=self.document('Вопрос?\n\nДа.\n\nКороткая оговорка.')
        e=FakeEmbedder()
        def forbidden(_):raise AssertionError('fitting reviewed group needs no transition embeddings')
        e.embed=forbidden;ranges,stats=p.structure_ranges(d,self.tokenizer,e)
        self.assertEqual(ranges,[(0,len(d['text']))]);self.assertEqual(stats['transition_inputs'],0)

    def test_bad_vectors(self):
        bad=[[],[[0.0]*1024],[[1.0]*1023],[[float('nan')]+[0.0]*1023],[[float('inf')]+[0.0]*1023],[[True]+[0.0]*1023]]
        for vectors in bad:
            with self.assertRaises(ValueError):p.validate_vectors(vectors,1)
    def test_loopback_truncate_and_model_digest(self):
        for url in ['http://example.test','https://127.0.0.1','http://10.0.0.1']:
            with self.assertRaises(ValueError):p.Ollama(url,'digest')
        e=p.Ollama('http://127.0.0.1:11434','digest')
        with patch.object(e.session,'post') as post:
            post.return_value.json.return_value={'embeddings':[[1.0]+[0.0]*1023]}
            e.embed(['synthetic']);self.assertIs(post.call_args.kwargs['json']['truncate'],False)
    def test_paired_atomic_switch_recovery_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=[self.document()];report=p.build_pair(old,self.tokenizer,FakeEmbedder(),root,{'model':'synthetic','digest':'d'})
            pointer=(root/'current.json').read_bytes();new=[self.document('Changed synthetic')]
            with self.assertRaises(RuntimeError):p.build_pair(new,self.tokenizer,FakeEmbedder(),root,{'model':'synthetic','digest':'d'},fail_before_publish=True)
            self.assertEqual((root/'current.json').read_bytes(),pointer)
            incomplete=[d for d in root.iterdir() if d.is_dir() and json.loads((d/'state.json').read_text())['status']=='incomplete'];self.assertEqual(len(incomplete),1)
            recovered=p.build_pair(new,self.tokenizer,FakeEmbedder(),root,{'model':'synthetic','digest':'d'})
            self.assertNotEqual(json.loads(pointer)['generation'],recovered['generation'])
            e=FakeEmbedder();same=p.build_pair(new,self.tokenizer,e,root,{'model':'synthetic','digest':'d'});self.assertEqual(same,recovered);self.assertEqual(e.inputs,0)
    def test_incomplete_first_build_not_current(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):p.build_pair([self.document()],self.tokenizer,FakeEmbedder(),directory,{'digest':'d'},fail_before_publish=True)
            self.assertFalse((Path(directory)/'current.json').exists())

if __name__=='__main__':unittest.main()
