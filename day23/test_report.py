"""Синтетическая проверка HTML: escape, старый/new формат, отсутствие оценок."""
import json
from pathlib import Path
import tempfile
from report import load_answers,private_output,render,response_content

def response():return {'model':'model','provider':'provider','choices':[{'message':{'content':'<script>secret</script>'}}],'usage':{'cost':.001}}

def main():
    raw=response()
    assert response_content({'response':raw})['text']==raw['choices'][0]['message']['content']
    assert response_content({'http_status':200,'body':json.dumps(raw)})['text']==raw['choices'][0]['message']['content']
    b={'cases':[{'id':'Q01','question':'<img src=x>','split':'development','category':'concept','expected_facts':['<fact>']}],'answer_case_ids':['Q01']}
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp)/'private';directory.mkdir();base=Path(tmp)/'baseline';base.mkdir()
        (base/'Q01-rag.json').write_text(json.dumps({'response':raw}))
        (directory/'e.json').write_text(json.dumps({'http_status':200,'body':json.dumps(raw)}))
        (directory/'ledger.json').write_text(json.dumps({'budget':1,'entries':[{'id':'Q01','mode':'E','status':'completed','response_file':'e.json','charged':.001}]}))
        ledger,answers=load_answers(directory,base,['Q01'])
        document=render(b,{'results':{}},{'results':{}},ledger,answers)
        assessed=render(b,{'results':{'E035':{'summary':{'all':{'questions':40,'answerable':35,'all_anchors':31,'all_documents':32,'candidate_all_anchors':33,'empty':0,'context_bytes':12345}}}}},{'results':{'A':{'summary':{'all':{'questions':60,'answerable':55,'all_anchors':42,'all_documents':43,'candidate_all_anchors':44,'empty':1,'context_bytes':54321}}}}},ledger,answers,{'cases':[{'id':'Q01','E':{'facts':['contradicted'],'error':True,'notes':'<note>'}}]})
        assert 'противоречит' in assessed and '&lt;note&gt;' in assessed
        assert '<td>40</td><td>35</td><td>33</td><td>31</td><td>32</td><td>0</td><td>12345</td>' in assessed
        assert '<td>60</td><td>55</td><td>44</td><td>42</td><td>43</td><td>1</td><td>54321</td>' in assessed
        assert '<script>' not in document and '<img src=x>' not in document
        assert '&lt;script&gt;' in document and 'Ручная оценка не внесена' in document
        assert 'Сохранённый Day22 baseline' in document and 'Трасса поиска для этого режима отсутствует' in document
        assert private_output(directory/'comparison.html',directory).parent.stat().st_mode&0o777==0o700
        try:private_output(Path(tmp)/'public.html',directory)
        except ValueError:pass
        else:raise AssertionError('public output accepted')
    print('ok report: fake old/new response schemas, HTML escaping, missing manual assessment, private destination')

if __name__=='__main__':main()
