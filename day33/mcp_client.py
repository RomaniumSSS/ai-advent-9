"""Отдельный MCP-процесс получает scope от сервера, а не от модели."""
import json
import subprocess
import sys
from domain import ROOT, validate_context

def read_context(user_id: str, ticket_id: str) -> tuple[dict,list]:
    messages = [
        {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'teamdesk','version':'1.0'}}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':2,'method':'tools/list'},
        {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read_support_context','arguments':{'ticket_id':ticket_id}}}]
    completed = subprocess.run([sys.executable,str(ROOT/'mcp_server.py'),user_id],input=''.join(json.dumps(m)+'\n' for m in messages),text=True,capture_output=True,timeout=8)
    if completed.returncode: raise RuntimeError('MCP-процесс завершился с ошибкой')
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    if len(responses) != 3 or [r.get('id') for r in responses] != [1,2,3]: raise RuntimeError('Некорректный MCP-ответ')
    for response in responses:
        if 'error' in response: raise PermissionError(response['error']['message'])
    if responses[0].get('result',{}).get('protocolVersion') != '2024-11-05': raise RuntimeError('Неизвестная версия MCP')
    tools = responses[1].get('result',{}).get('tools',[])
    if not isinstance(tools,list) or [tool.get('name') for tool in tools] != ['read_support_context']: raise RuntimeError('Неизвестный MCP-контракт')
    result = responses[-1]['result']
    if result.get('isError'): raise RuntimeError('Ошибка MCP-инструмента')
    context = json.loads(result['content'][0]['text'])
    context = validate_context(context, user_id, ticket_id)
    return context, [{'method':m['method'],'id':m.get('id')} for m in messages]
