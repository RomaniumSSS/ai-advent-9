"""Review08 P2: positive final shape before real Application/Store persistence."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local,service,server
from test_service import chunk,context_body
from test_profile08 import ThinkingFake,REASON

class PrivacyShape08Tests(unittest.TestCase):
    def run_app(self,model):
        with tempfile.TemporaryDirectory() as d:
            app=server.Application(service.Engine([chunk()],model),service.Store(Path(d)/'state'),'fixture-token')
            output=io.StringIO()
            with patch('service.generation_lock',side_effect=contextlib.nullcontext),contextlib.redirect_stdout(output):
                accepted=app.submit({'question':'Какие условия дня 30?'});app.wait_workers()
            receipt=app.store.receipt(accepted['request_id'],'all')
            self.assertTrue(REASON not in json.dumps(receipt),'reasoning leaked into receipt')
            self.assertTrue(REASON not in json.dumps(service.public_receipt(receipt)),'reasoning leaked into API')
            self.assertTrue(REASON not in output.getvalue(),'reasoning logged')
            files=list(Path(d).rglob('*.json'));self.assertEqual(len(files),2)
            for p in files:self.assertTrue(REASON not in p.read_text(),'reasoning leaked into private file')
            return receipt
    def test_analysis_root_extra_and_nested_unknown_payloads_opaque_in_actual_store(self):
        for variant in ('analysis_only','extra_analysis','point_extra','point_wrong_text','conclusion_extra','nested_doubts'):
            class Bad(ThinkingFake):
                def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                    response=super().chat(m,s,options,think,native_format,deadline_seconds)
                    if 'originals' in context_body(m[-1]['content']):
                        value=json.loads(response['message']['content'])
                        if variant=='analysis_only':value={'analysis':REASON}
                        elif variant=='extra_analysis':value['analysis']=REASON
                        elif variant=='point_extra':value['a_points'][0]['internal']={'analysis':REASON}
                        elif variant=='point_wrong_text':value['a_points'][0]['text']={'analysis':REASON}
                        elif variant=='conclusion_extra':value['c_conclusion']['internal']=[{'analysis':REASON}]
                        else:value['b_doubtful_aspect_ids']=[{'analysis':REASON}]
                        response['message']['content']=json.dumps(value)
                    return response
            with self.subTest(variant=variant):
                receipt=self.run_app(Bad());self.assertEqual(receipt['status'],'error')
                saved=receipt['trace']['synthesis_raw_response']['message']
                self.assertNotIn('content',saved);self.assertGreater(saved['content_metadata']['bytecount'],0)
                self.assertEqual(len(saved['content_metadata']['sha256']),64)
                self.assertEqual(receipt['metrics']['generation_calls'],2)
    def test_nested_selection_arbitrary_fields_and_wrong_types_are_opaque(self):
        for variant in ('root_extra','nested_evidence','nested_coverage'):
            class Bad(ThinkingFake):
                def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                    response=super().chat(m,s,options,think,native_format,deadline_seconds)
                    if 'sources' in context_body(m[-1]['content']):
                        value=json.loads(response['message']['content'])
                        if variant=='root_extra':value['analysis']=REASON
                        elif variant=='nested_evidence':value['a_evidence']['S1.U1']=[{'analysis':REASON}]
                        else:value['b_coverage']['Q1']={'analysis':REASON}
                        response['message']['content']=json.dumps(value)
                    return response
            with self.subTest(variant=variant):
                receipt=self.run_app(Bad());self.assertEqual(receipt['status'],'error')
                self.assertEqual(receipt['metrics']['generation_calls'],1)
                self.assertNotIn('content',receipt['trace']['selection_raw_response']['message'])
                self.assertNotIn('synthesis_raw_response',receipt['trace'])
    def test_safely_shaped_invalid_reference_keeps_exact_final_diagnostics(self):
        class Capture(ThinkingFake):
            def chat(self,*args,**kwargs):
                response=super().chat(*args,**kwargs)
                if 'originals' in context_body(args[0][-1]['content']):self.final=response['message']['content']
                return response
        model=Capture('refs');receipt=self.run_app(model)
        self.assertEqual(receipt['status'],'error');self.assertEqual(receipt['trace']['validation_code'],'invalid_point_reference')
        saved=receipt['trace']['synthesis_raw_response']['message']
        self.assertEqual(saved['content'],model.final);self.assertNotIn('thinking',saved)
        self.assertEqual(receipt['metrics']['generation_calls'],2)
    def test_error_response_data_unknown_shape_opaque_before_snapshot(self):
        class Error(ThinkingFake):
            def chat(self,*args,**kwargs):
                exc=ValueError('ollama_response_error');exc.transport_stage='body'
                exc.response_data={'message':{'content':json.dumps({'analysis':REASON})}}
                raise exc
        receipt=self.run_app(Error());self.assertEqual(receipt['status'],'error')
        self.assertEqual(receipt['trace']['validation_code'],'ollama_response_error')
        self.assertNotIn('content',receipt['trace']['selection_raw_response']['message'])

if __name__=='__main__':unittest.main()
