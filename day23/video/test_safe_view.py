"""Офлайн: отображение не раскрывает приватные тексты и идентификаторы."""
import importlib.util
import json
from pathlib import Path
spec=importlib.util.spec_from_file_location('serve_live',Path(__file__).parent/'serve_live.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def main():
    def c(cid,source,text):
        return {'chunk_id':cid,'document_id':cid,'source':source,'text':text,'cosine':.4,'mixed_score':.5,'selection_reason':'cosine'}
    private=c('discussion:secret','discussion','НЕ ПУБЛИКОВАТЬ')
    public=c('assignment:21','assignment','Условие Day21')
    trace={'search_question':module.QUESTION,'config':{},'candidates':[{k:v for k,v in x.items() if k!='selection_reason'} for x in [private,public]],'selected':[private,public],'removed':[]}
    output=module.safe_search({'cases':[{'traces':{'A':trace,'E':trace}}]})
    encoded=json.dumps(output,ensure_ascii=False)
    assert 'НЕ ПУБЛИКОВАТЬ' not in encoded and 'discussion:secret' not in encoded
    assert output['assignment']=='Условие Day21' and output['modes']['A']['private_selected']
    assert module.safe_answer('секрет',True).startswith('Ответ скрыт')
    assert 'секрет' not in module.safe_answer('секрет [discussion:x]',False)
    assert module.safe_answer('публичный ответ',False)=='публичный ответ'
    assert not module.OPERATE and not module.PRIVATE_PREVIEW
    print('ok video safe view: private text/IDs hidden, assignments shown, operations disabled by default')

if __name__=='__main__':main()
