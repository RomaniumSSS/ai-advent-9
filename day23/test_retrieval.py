"""Офлайн-проверки математики, явных дней и границ отбора."""
import math
from retrieval import Config, MODES, explicit_days, retrieve, rewrite, query_input

def chunk(cid,cos,text='текст',day=None,source='discussion'):
    return {'chunk_id':cid,'document_id':cid,'text':text,'vector':[cos,math.sqrt(1-cos*cos)],'day':day,'source':source}

def main():
    assert explicit_days('Day21, Day 22, 19-й день, день20 и дни 17 и 18') == [21,22,19,20,17,18]
    assert explicit_days('day123 Day21abc') == []
    assert explicit_days('Чем задания 19 и 20 отличаются?') == [19,20]
    assert explicit_days('Требования к дню рождения: 21 страница') == []
    assert explicit_days('В задании 17 и дне 18') == [17,18]
    assert explicit_days('21-го и 22-го дня') == [21,22]
    assert rewrite('21-го и 22-го дня')['after'] == 'День 21 и День 22'
    assert explicit_days('21 страница, 20 долларов, 19 секунд') == []
    assert explicit_days('Нужно ждать 21 день или 14 дней?') == []
    assert rewrite('Сравни дни 19 и 20')['after']=='Сравни День 19 и День 20'
    assert rewrite('Почему нужен реранкер?')['applied'] is False
    assert query_input('q').endswith('\nQuery:q')
    chunks=[chunk('z',.6,'альфа'),chunk('a',.6,'бета'),chunk('x',.1,'альфа',21,'assignment')]
    a=retrieve(chunks,'альфа',[1,0],MODES['A'])
    assert [c['chunk_id'] for c in a['selected']]==['a','z','x']
    c=retrieve(chunks,'альфа',[1,0],Config(mixed=True,threshold=.5))
    assert [x['chunk_id'] for x in c['selected']]==['z']
    assert abs(c['selected'][0]['score']-.68)<1e-12
    d=retrieve(chunks,'Что нужно сдать Day21?',[1,0],Config(metadata=True,before=1,threshold=.99,mixed=True))
    assert d['selected'][0]['chunk_id']=='x' and d['counts']['metadata_added']==1
    assert retrieve(chunks,'Что сдаётся в Day21?',[1,0],Config(metadata=True,before=1))['counts']['metadata_added']==1
    generic=retrieve(chunks,'Объясни cosine day21',[1,0],Config(metadata=True,before=1))
    assert generic['counts']['metadata_added']==0
    nums=retrieve(chunks,'Нужно 21 страниц?',[1,0],Config(metadata=True,before=1))
    assert nums['counts']['metadata_added']==0
    multi=retrieve(chunks+[chunk('y',0,day=22,source='assignment')],'Сравни требования дни21 и 22',[1,0],Config(metadata=True,before=1))
    assert {x['day'] for x in multi['selected'] if x['exact_reason']}=={21,22}
    small=retrieve(chunks,'альфа',[1,0],Config(context_bytes=1))
    assert small['empty'] and all(x['removal_reason']=='context_bytes' for x in small['removed'])
    empty=retrieve([], 'q',[1,0],Config())
    assert empty['empty']
    print('ok retrieval: explicit days, rewrite, cosine ties, mixed threshold, metadata, byte budget, empty')

if __name__=='__main__':main()
