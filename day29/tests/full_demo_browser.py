"""Synthetic3 delivery dry: ephemeral UI apps, Mock engines, no Ollama."""
import argparse,json,sys,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'video'))
import core,app,full_chat,full_chat_core as chat,run_full_demo as demo

class PublicEngine:
    identity={'generation':core.GENERATION,'db_sha256':core.DB_SHA}
    def __init__(self):self.calls=[]
    def ask(self,question,profile_id,run_id,request_id):
        self.calls.append((question,profile_id));selected=[{'source':'assignment','document_id':f'assignment:{day}','chunk_id':f'fake{day}','text':f'Синтетический публичный источник {day}.'} for day in (19,20)]
        return {'scope':'public','model':core.MODEL,'index':self.identity,'run_id':run_id,'request_id':request_id,
            'digest':core.GEN_DIGEST,'profile_sha256':core.sha(core.load_profiles()[profile_id]),'generation_options':core.load_profiles()[profile_id]['options'],
            'model_identity':{'generator_digest':core.GEN_DIGEST,'embedding_digest':core.EMBED_DIGEST},'generation_called':True,'started_at':chat.now(),'finished_at':chat.now(),
            'question':question,'profile_id':profile_id,'status':'done','selected':selected,'citations_valid':True,
            'answer':{'answer':'Синтетическое сравнение, не модельный ответ.','sources':[{'source':c['document_id'],'chunk_id':c['chunk_id']} for c in selected],
                      'quotes':[{'chunk_id':c['chunk_id'],'text':c['text']} for c in selected]},'times':{'generation':.001,'total':.002},'metrics':{},'resources':{}}

class FullEngine:
    identity={'generation':core.GENERATION,'db_sha256':core.DB_SHA,'chunk_count':724,'document_count':663,'source_counts':{'assignment':24,'discussion':694,'personal_note':6}}
    def __init__(self):self.calls=[]
    def ask(self,question,turns,cid,request_id,run_id):
        self.calls.append(question);text='Синтетический публичный текст Day11, не архив.'
        selected=[{'source':'assignment','document_id':'assignment:11','chunk_id':'fake11','text':text}]
        messages=[{'role':'system','content':chat.SYSTEM},{'role':'user','content':'Synthetic fixture context'}]
        return {'conversation_id':cid,'request_id':request_id,'run_id':run_id,'question':question,'scope':'all',
            'model':core.MODEL,'digest':core.GEN_DIGEST,'options':chat.OPTIONS,'embedding_model':core.EMBED_MODEL,'embedding_digest':core.EMBED_DIGEST,
            'model_identity':{'generator_digest':core.GEN_DIGEST,'embedding_digest':core.EMBED_DIGEST},'index':self.identity,
            'messages':messages,'payload':core.profile_payload(chat.PROFILE,messages),'started_at':chat.now(),'finished_at':chat.now(),
            'status':'done','citations_valid':True,'generation_called':True,'selected':selected,'times':{'generation':.001,'total':.002},
            'answer':{'answer':'Синтетический public ответ, Ollama не вызвана.','source_refs':['S1'],
            'sources':[{**selected[0],'source_ref':'S1','request_id':request_id,'excerpts':[{'text':text,'author':None,'date':None,'start_char':0,'end_char':len(text)}]}]}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        public=PublicEngine();full=FullEngine();store=chat.ConversationStore(Path(temp)/'full')
        old=store.create();old['turns']=[{'request_id':'c'*32,'conversation_id':old['conversation_id'],'question':'PRIVATE_FIXTURE_DO_NOT_CAPTURE','answer':{'answer':'PRIVATE_FIXTURE_DO_NOT_CAPTURE'},'status':'done'}];store.data[old['conversation_id']]=old;store._save(old)
        apps=[app.Application(public,Path(temp)/'bench'),full_chat.Application(full,store)]
        servers=[]
        try:
            for application,handler in zip(apps,[app.handler_for,full_chat.handler_for]):
                server=ThreadingHTTPServer(('127.0.0.1',0),handler(application));application.port=server.server_port;servers.append(server)
                threading.Thread(target=server.serve_forever,daemon=True).start()
            demo.BENCH=f'http://127.0.0.1:{servers[0].server_port}';demo.FULL=f'http://127.0.0.1:{servers[1].server_port}'
            demo.run(argparse.Namespace(full_day=11,record=False,qualified_dry=None,output=args.output,full_storage=store.root))
            result=json.loads((args.output/'results.json').read_text())
            assert len(public.calls)==2 and len(full.calls)==1
            assert result['status']=='completed' and len(result['requests'])==3 and not result['page_errors']
            assert store.get(old['conversation_id'])['turns']==old['turns']
            assert 'PRIVATE_FIXTURE_DO_NOT_CAPTURE' not in json.dumps(result)
            result.update(fixture_only=True,real_generation_calls=0,real_embedding_calls=0,mocked_engine_calls=3)
            core.save_private(args.output/'results.json',result)
            print(json.dumps({'status':'PASS','fixture_only':True,'mock_engine_calls':3,'real_generation_calls':0,'real_embedding_calls':0}))
        finally:
            for server in servers:server.shutdown();server.server_close()

if __name__=='__main__':main()
