"""Q1–Q5: синтетические регрессии и новые отрицательные формы, без сети."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from answers import check_answer
from common import packed, save
from retrieval import Config, explicit_days, retrieve
from service import Service
from temporal import prepare_chunks, context_record
from test_mentor import VALID, CHUNK, auth, synthetic

def discussion():
    first='Мнение A: нужен явный индекс.'
    second='Мнение B: даты нужно сохранять.'
    text=first+'\n\n'+second
    return {'chunk_id':'mixed','document_id':'discussion:synthetic','source':'discussion','text':text,'vector':[1.0,0.0],'start_char':100,'end_char':100+len(text),
            'members':[{'id':'m1','message_id':1,'source_key':'k1','author':'Автор A','date':'2025-12-31T23:00:00+01:00'},{'id':'m2','message_id':2,'source_key':'k2','author':'Автор B','date':'2026-01-01T11:00:00+01:00'}],
            'source_sections':[{'start_char':100,'text_start_char':100,'end_char':100+len(first),'member_ids':['m1'],'source_keys':['k1']},{'start_char':100+len(first),'text_start_char':102+len(first),'end_char':100+len(text),'member_ids':['m2'],'source_keys':['k2']}]}

def main():
    for q in ('дай условие дня 18','в условии 18','условие18','day18: какое задание?','условия лня 18'):
        assert explicit_days(q)==[18],(q,explicit_days(q))
    for q in ('что обсуждали 18.09','дай условие 18 сентября','18 сообщений','цена 18 рублей','в 2026 году','условие 18.09.2026','day18.09','18'):
        assert not explicit_days(q),(q,explicit_days(q))
    assignment=dict(CHUNK,day=18,vector=[0.0,1.0])
    exact=retrieve([assignment],'дай условие дня 18',[1.0,0.0],Config())
    assert retrieve([assignment],'day18',[1.0,0.0],Config())['selected']
    assert len(exact['selected'])==1 and exact['selected'][0]['score']<.35
    assert not retrieve([assignment],'про другое',[1.0,0.0],Config())['selected']
    assert not retrieve([assignment],'дай условие дня 18',[1.0,0.0],Config(context_bytes=0))['selected']
    assert not retrieve([],'дай условие дня 18',[1.0,0.0],Config())['selected']
    mixed=discussion()
    prepared,t=prepare_chunks([mixed],'что обсуждали 31 декабря?')
    assert t['resolved_dates']==['2025-12-31'] and len(prepared)==1
    parts=prepared[0]['message_parts'];assert len(parts)==1 and parts[0]['author']=='Автор A' and parts[0]['message_id']==1
    assert parts[0]['text'] in mixed['text'] and 'Автор B' not in json.dumps(context_record(prepared[0]),ensure_ascii=False)
    assert parts[0]['text']==mixed['text'][parts[0]['start']:parts[0]['end']]
    iso,iso_info=prepare_chunks([mixed],'обсуждение 2025-12-31');assert iso_info['enabled'] and iso_info['resolved_dates']==['2025-12-31']
    for q in ('2025-12-31 что обсуждали','обсуждение 2025-12-31'):
        selected,period=prepare_chunks([mixed],q);assert selected and period['error'] is None
    for q in ('с 28 сентября по 30 сентября 2026','с 28 по 30 сентября 2026','28–30 сентября 2026','с 28.09 по 30.09','2025-12-31—2026-01-01'):
        blocked,period=prepare_chunks([mixed],q);assert not blocked and period['enabled'] and period['error']
    header=dict(CHUNK,text='HIDDEN_HEADER\nVISIBLE_MESSAGE',start_char=0,end_char=29,members=CHUNK['members'],source_sections=[dict(CHUNK['source_sections'][0],text_start_char=14,end_char=29)])
    sent,_=prepare_chunks([header],'тест')
    hidden={'answer':'тест','sources':[{'source':'assignment','chunk_id':'c1'}],'quotes':[{'chunk_id':'c1','text':'HIDDEN_HEADER'}]}
    assert 'quote_not_in_transmitted_text' in check_answer(json.dumps(hidden),sent)['errors']
    recent,t=prepare_chunks([mixed],'что говорили за последние дни?')
    assert t['start']=='2025-12-26' and t['end']=='2026-01-01' and len(recent[0]['message_parts'])==2
    clone=dict(mixed,chunk_id='newyear',members=[dict(mixed['members'][0],date='2026-12-31T13:00:00+01:00')])
    ambiguous,t=prepare_chunks([mixed,clone],'31 декабря')
    assert not ambiguous and t['error']
    nonmatching=dict(mixed,chunk_id='wrongdate',members=[dict(m,date='2026-01-02T11:00:00+01:00') for m in mixed['members']])
    trace=retrieve([nonmatching,mixed],'обсуждение 31.12.2025',[1.0,0.0],Config(before=1,threshold=0))
    assert [c['chunk_id'] for c in trace['candidates']]==['mixed'] and trace['temporal']['excluded_chunks']==1
    valid={'answer':'Тест','sources':[{'source':'discussion','chunk_id':'mixed'}],'quotes':[{'chunk_id':'mixed','text':parts[0]['text']}]}
    assert check_answer(json.dumps(valid),prepared)['valid']
    invalid=dict(valid,quotes=[{'chunk_id':'mixed','text':'Мнение B: даты нужно сохранять.'}])
    assert 'quote_outside_temporal_scope' in check_answer(json.dumps(invalid),prepared)['errors']
    assert check_answer('```json\n'+VALID+'\n```',[CHUNK])['valid']
    assert check_answer('```\n'+VALID+'\n```',[CHUNK])['normalization']=='single_outer_json_fence'
    for content in ('Ответ:\n```json\n'+VALID+'\n```','```json\n'+VALID+'\n```\nещё текст','```json\n'+VALID+'\n```\n```json\n{}\n```'):
        assert not check_answer(content,[CHUNK])['valid']
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);auth(root);save(root/'ledger.json',{'entries':[{'status':'unknown','charged':.001}]})
        s=Service(root,synthetic,pricing_fn=lambda: (_ for _ in ()).throw(AssertionError('pricing must not run')))
        assert s.ask('blocked','тест','public')['error']=='explicit_recovery_required'
    print('PASS Q1–Q5: exact days/budgets, date negatives, per-message offsets/authors, year ambiguity/archive edge, pre-topK filter, original quotes, single fence, ledger before pricing; no network')

if __name__=='__main__':
    with patch('requests.Session.request',side_effect=AssertionError('offline network forbidden')):main()
