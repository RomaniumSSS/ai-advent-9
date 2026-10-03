"""Период архива и атрибуция к пересекающимся частям исходного чанка."""
from datetime import date, datetime, timedelta
import re

MONTHS={'январ':1,'феврал':2,'март':3,'апрел':4,'мая':5,'май':5,'июн':6,'июл':7,'август':8,'сентябр':9,'октябр':10,'ноябр':11,'декабр':12}
ISO=re.compile(r'(?<!\w)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)')
RANGE=re.compile(r'\bс\s+\d{1,2}\s+(?:январ\w*|феврал\w*|март\w*|апрел\w*|мая|май|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)(?:\s+\d{4})?\s+(?:по|до)\s+\d{1,2}|\bс\s+\d{1,2}(?:[./]\d{1,2})?(?:[./]\d{4})?\s+(?:по|до)\s+\d{1,2}|(?<![\d-])\d{1,2}\s*[-–—]\s*\d{1,2}\s+[а-я]+|\d{4}-\d{2}-\d{2}\s*(?:[-–—]|по|до)\s*\d{4}-\d{2}-\d{2}',re.I)
NUMERIC=re.compile(r'(?<![\w.])(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?(?![\d.])')
NAMED=re.compile(r'(?<!\w)(\d{1,2})\s+(январ\w*|феврал\w*|март\w*|апрел\w*|мая|май|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)(?:\s+(\d{4})(?:\s*г(?:ода|од|\.)?)?)?',re.I)
RECENT=re.compile(r'последн(?:ие|их)\s+(?:(\d+)\s+)?дн(?:и|ей|я)|последн(?:юю|ей)\s+недел[юи]|\bсейчас\b',re.I)

def iso_day(value):
    try:return datetime.fromisoformat(value).date() if isinstance(value,str) else None
    except ValueError:return None

def date_mentions(question):
    result=[]
    for match in ISO.finditer(question):
        result.append({'day':int(match[3]),'month':int(match[2]),'year':int(match[1]),'span':match.span()})
    for match in NUMERIC.finditer(question):
        result.append({'day':int(match[1]),'month':int(match[2]),'year':int(match[3]) if match[3] else None,'span':match.span()})
    for match in NAMED.finditer(question):
        month=next(v for k,v in MONTHS.items() if match[2].lower().startswith(k))
        result.append({'day':int(match[1]),'month':month,'year':int(match[3]) if match[3] else None,'span':match.span()})
    return sorted(result,key=lambda x:x['span'])

def without_dates(question):
    chars=list(question)
    for mention in date_mentions(question):
        a,b=mention['span'];chars[a:b]=' '*(b-a)
    return ''.join(chars)

def message_parts(chunk):
    """Offsets остаются относительно оригинального snapshot, а не разметки для модели."""
    parts=[]
    members=chunk.get('members') or []
    start=chunk.get('start_char',0)
    end=chunk.get('end_char',start+len(chunk['text']))
    for section in chunk.get('source_sections') or []:
        a=max(start,section.get('text_start_char',section['start_char']))
        b=min(end,section['end_char'])
        if a>=b:continue
        matched=[m for m in members if m.get('id') in section.get('member_ids',[]) or m.get('source_key') in section.get('source_keys',[])]
        # Несколько участников секции не означают, что каждый написал весь её текст.
        member=matched[0] if len(matched)==1 else {}
        parts.append({'start':a-start,'end':b-start,'text':chunk['text'][a-start:b-start],
                      'author':member.get('author'),'date':member.get('date'),
                      'message_id':member.get('message_id',section.get('message_id')),'member_id':member.get('id'),
                      'source_key':member.get('source_key'),'attribution':'single_member' if member else 'ambiguous_or_missing',
                      'candidate_member_ids':[m.get('id') for m in matched]})
    return parts

def interpret(question,chunks):
    dates=sorted({d for c in chunks for m in c.get('members') or [] if (d:=iso_day(m.get('date')))})
    mentions=date_mentions(question);recent=RECENT.search(question);range_match=RANGE.search(question)
    info={'enabled':bool(mentions or recent or range_match),'archive_start':dates[0].isoformat() if dates else None,'archive_end':dates[-1].isoformat() if dates else None,'requested':mentions,'resolved_dates':[],'interpretation':None,'error':None}
    if not info['enabled']:return info
    if range_match:
        info['error']='Диапазон дат пока не поддерживается. Укажи одну календарную дату или последние дни архива.';return info
    if not dates:
        info['error']='В архиве нет дат для интерпретации периода.';return info
    if mentions and recent:
        info['error']='Указаны и календарная дата, и относительный период. Уточни один период.';return info
    if recent:
        count=int(recent[1] or 7)
        if not 1<=count<=31:
            info['error']='Уточни период от 1 до 31 дня.';return info
        last=dates[-1];first=last-timedelta(days=count-1)
        info.update(start=first.isoformat(),end=last.isoformat(),interpretation=f'Последние {count} дней доступного архива: {first.isoformat()} — {last.isoformat()}. Это не live-данные и не сегодняшние новости.')
        return info
    resolved=[];inferred=[]
    for m in mentions:
        year=m['year']
        if year is None:
            matches={d.year for d in dates if d.month==m['month'] and d.day==m['day']}
            if not matches:
                archive_years={d.year for d in dates}
                if len(archive_years)==1:matches=archive_years
            if len(matches)!=1:
                info['error']='Год указанной даты нельзя однозначно определить по архиву. Уточни год.';return info
            year=next(iter(matches));inferred.append(year)
        try:target=date(year,m['month'],m['day'])
        except ValueError:
            info['error']='Некорректная календарная дата. Уточни дату.';return info
        resolved.append(target.isoformat())
    info['resolved_dates']=sorted(set(resolved))
    info['interpretation']='Поиск только по датам: '+', '.join(info['resolved_dates'])+'.'+(' Год определён по датам архива.' if inferred else '')
    return info

def prepare_chunks(chunks,question):
    info=interpret(question,chunks);output=[];excluded=0
    for original in chunks:
        chunk=dict(original);parts=message_parts(chunk)
        if info['enabled']:
            if info['error']:excluded+=1;continue
            def in_scope(part):
                d=iso_day(part['date'])
                if d is None:return False
                stamp=d.isoformat()
                return stamp in info['resolved_dates'] if info['resolved_dates'] else info['start']<=stamp<=info['end']
            parts=[p for p in parts if in_scope(p)]
            if not parts:excluded+=1;continue
            chunk['temporal_restricted']=True
            chunk['search_text']='\n'.join(p['text'] for p in parts)
        chunk['message_parts']=parts
        output.append(chunk)
    return output,dict(info,excluded_chunks=excluded,eligible_chunks=len(output))

def context_record(chunk):
    record={'source':chunk['source'],'chunk_id':chunk['chunk_id'],'section':chunk.get('section')}
    if chunk.get('message_parts'):
        record['messages']=[{k:p[k] for k in ('author','date','message_id','member_id','source_key','text','attribution')} for p in chunk['message_parts']]
    else:record['text']=chunk['text']
    return record
