"""Read-only MCP stdio: JSON-RPC, initialize и tools/list/call."""
import json
import sys
from domain import load_crm, string

TOOLS = [{'name': 'read_support_context', 'description': 'Читает только тикет текущего demo-пользователя', 'inputSchema': {'type':'object','properties':{'ticket_id':{'type':'string'}},'required':['ticket_id'],'additionalProperties':False}}]

def handle(request: dict, user_id: str) -> dict | None:
    request_id = request.get('id')
    if 'id' not in request: return None
    try:
        if request.get('jsonrpc') != '2.0': raise ValueError('Требуется JSON-RPC 2.0')
        method = request.get('method')
        if method == 'initialize':
            result = {'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'teamdesk-readonly','version':'1.0'}}
        elif method == 'tools/list': result = {'tools':TOOLS}
        elif method == 'tools/call':
            params = request.get('params', {})
            if params.get('name') != 'read_support_context': raise ValueError('Неизвестный инструмент')
            args = params.get('arguments', {})
            if set(args) != {'ticket_id'}: raise ValueError('Некорректные аргументы')
            ticket_id = string(args['ticket_id'], 'ticket_id', 50)
            crm = load_crm()
            ticket = next((t for t in crm['tickets'] if t['id'] == ticket_id and t['user_id'] == user_id), None)
            if ticket is None: raise PermissionError('Тикет недоступен текущему пользователю')
            user = next(u for u in crm['users'] if u['id'] == user_id)
            result = {'content':[{'type':'text','text':json.dumps({'user':user,'ticket':ticket},ensure_ascii=False)}], 'isError':False}
        else:
            return {'jsonrpc':'2.0','id':request_id,'error':{'code':-32601,'message':'Метод не найден'}}
        return {'jsonrpc':'2.0','id':request_id,'result':result}
    except (ValueError, KeyError, TypeError, PermissionError) as exc:
        return {'jsonrpc':'2.0','id':request_id,'error':{'code':-32602,'message':str(exc)}}

if __name__ == '__main__':
    user_id = sys.argv[1]
    if user_id not in {u['id'] for u in load_crm()['users']}: raise SystemExit('Неизвестный scope')
    for line in sys.stdin:
        try: response = handle(json.loads(line), user_id)
        except (ValueError, AttributeError): response = {'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Некорректный JSON'}}
        if response is not None: print(json.dumps(response,ensure_ascii=False),flush=True)
