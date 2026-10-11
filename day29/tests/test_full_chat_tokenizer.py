"""Независимые синтетические scanner/BPE/budget границы, без Ollama inference."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from full_chat_tokenizer import Qwen2Tokenizer,pieces,check_budget

def tokenizer(merges=None):
    visible=list(range(33,127))+list(range(161,173))+list(range(174,256))
    alphabet=[chr(b) if b in visible else chr(256+sum(x not in visible for x in range(b))) for b in range(256)]
    merges=merges or ['a b','ab c']
    tokens=alphabet+[m.replace(' ','') for m in merges]
    return Qwen2Tokenizer({'tokenizer.ggml.model':'gpt2','tokenizer.ggml.pre':'qwen2','tokenizer.ggml.tokens':tokens,'tokenizer.ggml.merges':merges})

class Tokenizer(unittest.TestCase):
    def test_unicode_and_ordered_scanner_alternatives(self):
        cases={"Привет 123, café!\n":["Привет"," ","1","2","3",","," café","!\n"],
               "a   b\n\n c  ":["a","  "," b","\n\n"," c","  "],
               "we'RE Á 😺\r\n":["we","'RE"," A","́"," 😺\r\n"],
               'a\t b':['a','\t',' b'],'a \n  b':['a',' \n',' ',' b']}
        for text,expected in cases.items():
            with self.subTest(text=text):self.assertEqual(list(pieces(text)),expected)
    def test_merge_rank_and_leftmost_ties(self):
        t=tokenizer();self.assertEqual(t.count('abc'),1);self.assertEqual(t.count('abc abc'),3)
        self.assertEqual(tokenizer(['a b','b c']).count('abc'),2)
        self.assertEqual(tokenizer(['a a','aa a']).count('aaaa'),2)
    def test_unicode_bytes_and_special_spellings_are_not_ignored(self):
        t=tokenizer();self.assertEqual(t.count('Ж'),2);self.assertEqual(t.count('😺'),4)
        self.assertGreater(t.count('<|im_start|>'),1)
    def test_actual_json_escaping_schema_template_and_output_counted(self):
        t=tokenizer();m=[{'role':'user','content':'Ж\\"\n😺'}]
        b=check_budget(m,{'num_ctx':8192,'num_predict':1024},{'type':'object'},t)
        self.assertGreater(b['serialized_messages_tokens'],t.count(m[0]['content']))
        self.assertEqual(b['input_upper_bound'],b['bounded_messages_tokens']+b['schema_tokens']+512)
        with self.assertRaisesRegex(ValueError,'input_exceeds'):check_budget(m,{'num_ctx':b['input_upper_bound']+1023,'num_predict':1024},{'type':'object'},t)
    def test_metadata_fails_closed(self):
        with self.assertRaises(ValueError):Qwen2Tokenizer({})
if __name__=='__main__':unittest.main()
