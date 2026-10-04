"""Clearly labelled offline UI fixture; never connects to index/provider."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from common import MODEL, packed, save
from retrieval import Config, retrieve
from service import Service, read
from web import make_server

CHUNK={'chunk_id':'synthetic18','document_id':'assignment:18','source':'assignment','day':18,
       'title':'Синтетический учебный документ',
       'text':'СИНТЕТИЧЕСКИЙ ТЕСТ: RAG ищет источники перед ответом. <script>window.pwned=1</script>',
       'vector':[1.0,0.0]}
IDENTITY={'synthetic_ui':True}


def fixture(directory, private_all=False, preserve_authorization=False):
    directory=Path(directory)
    metrics_path=directory/'fixture-metrics.json'
    def metrics():return read(metrics_path,{'searches':0,'generations':0})
    def count(key):
        value=metrics();value[key]+=1;save(metrics_path,value)
    def search(question,scope):
        count('searches');time.sleep(.3)
        chunk=dict(CHUNK,chunk_id='synthetic-private',document_id='private:synthetic',source='chat',day=None,title='ALL_ONLY_SYNTHETIC_MARKER',text='ALL_ONLY_SYNTHETIC_MARKER: RAG ищет источники перед ответом.') if private_all and scope=='all' else CHUNK
        chunks=[] if 'нет сведений' in question.lower() else [chunk]
        return {'identity':IDENTITY,'backend':'SYNTHETIC OFFLINE FIXTURE',
                'trace':retrieve(chunks,question,[1.0,0.0],Config(threshold=0))}
    def generate(body,key):
        count('generations');time.sleep(.3)
        envelope=json.loads(body['messages'][1]['content'])
        question=envelope['current_question']
        chunk=json.loads(envelope['fresh_rag_context'].split('\n\n')[0])
        quote='Выдуманная цитата.' if 'неверная цитата' in question.lower() else 'RAG ищет источники перед ответом.'
        answer={'answer':'Синтетический ответ: RAG ищет источники перед ответом.',
                'sources':[{'source':chunk['source'],'chunk_id':chunk['chunk_id']}],
                'quotes':[{'chunk_id':chunk['chunk_id'],'text':quote}]}
        return {'model':MODEL,'provider':'DeepInfra','usage':{'cost':.00001},
                'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer,ensure_ascii=False)}}]}
    if not preserve_authorization or not (directory/'authorization.json').exists():save(directory/'authorization.json',{'approved':True,'authorization_id':'synthetic-ui',
         'model':MODEL,'provider':'deepinfra/fp8','retries':0,'scopes':['all','public'],
         'question_policy':'arbitrary','identity_sha256':hashlib.sha256(packed(IDENTITY)).hexdigest(),
         'document_ids':['assignment:18','private:synthetic'] if private_all else ['assignment:18'],'budget':.1})
    service=Service(directory,search,generate,lambda _:'synthetic-key',
                    pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
    return service,metrics


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8053)
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--public-only',action='store_true')
    parser.add_argument('--preserve-authorization',action='store_true',help='Keep staged synthetic authorization/cap across restart')
    parser.add_argument('--private-all',action='store_true',help='Synthetic all-only marker for privacy checks')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='day25-ui-') as temporary:
        service,metrics=fixture(args.data_dir or temporary,args.private_all,args.preserve_authorization)
        server=make_server(args.port,service=service,public_only=args.public_only)
        server.test_fixture=True;server.test_metrics=metrics
        print('СИНТЕТИЧЕСКАЯ ОФЛАЙН ПРОВЕРКА http://'+server.address+'; provider/SSH=0',flush=True)
        with patch('requests.Session.request',side_effect=AssertionError('real network forbidden')), patch('subprocess.run',side_effect=AssertionError('SSH forbidden')):
            try:server.serve_forever()
            except KeyboardInterrupt:pass
            finally:server.server_close()


if __name__=='__main__':main()
