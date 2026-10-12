"""Клиент HTTPS с проверкой CA. Токен читается из файла и не попадает в argv."""
from limits import POLL_TIMEOUT_SECONDS
import argparse
import json
import ssl
import sys
import time
import urllib.request
from server import load_env

def request(base,path,token,cafile,payload=None):
    context=ssl.create_default_context(cafile=cafile)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
    req=urllib.request.Request(base+path,data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with opener.open(req,timeout=30) as response:return json.load(response)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--env',required=True);parser.add_argument('--base-url',required=True)
    parser.add_argument('--cafile',required=True);parser.add_argument('--question');parser.add_argument('--conversation-id')
    parser.add_argument('--request-id');parser.add_argument('--wait',action='store_true');parser.add_argument('--output')
    args=parser.parse_args();token=load_env(args.env)['DAY30_TOKEN']
    if args.question:
        payload={'question':args.question}
        if args.conversation_id:payload['conversation_id']=args.conversation_id
        result=request(args.base_url,'/api/chat',token,args.cafile,payload)
    else:result=request(args.base_url,'/api/requests/'+args.request_id if args.request_id else '/api/state',token,args.cafile)
    start=time.monotonic()
    while args.wait and result.get('status') in ('running','accepted'):
        if time.monotonic()-start>POLL_TIMEOUT_SECONDS:raise TimeoutError('request_polling_timeout')
        time.sleep(1);result=request(args.base_url,'/api/requests/'+result['request_id'],token,args.cafile)
    if args.output:
        from local import save_private
        save_private(args.output,result)
        print(json.dumps({'request_id':result.get('request_id'),'status':result.get('status'),'metrics':result.get('metrics',{})}))
    else:print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
