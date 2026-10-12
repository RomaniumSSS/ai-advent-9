"""Самостоятельные immutable evidence units Day29, база b3e607e."""
"""Один selector-call: immutable attributed units → проверяемые ID → исходные цитаты.

Проверка ID/текста не оценивает релевантность, полноту или смысловую поддержку.
"""
import re
from retrieval import evidence_features,matching_authors

MAX_SELECTED_UNITS=8
MAX_OUTPUT_REFS=5


def question_aspects(question):
    segments=re.split(r'[?;]+\s*|\s+(?:и|а)\s+(?=(?:что|как|какую|какой|какие|почему|зачем|кого|чем|сколько|нужна|нужно|нужен|требуется|можно|есть\s+ли|было\s+ли|удалось\s+ли)\b)',question,flags=re.I)
    segments=[s.strip() for s in segments if s.strip()]
    if len(segments)>6:segments=segments[:5]+['; '.join(segments[5:])]
    return [{'id':'Q'+str(i),'text':s} for i,s in enumerate(segments or [question],1)]


def paragraph_spans(text):
    start=0
    for match in re.finditer(r'\n[ \t]*\n',text):
        yield start,match.start();start=match.end()
    yield start,len(text)


def source_units(chunk,source_ref,parts):
    units=[];cursor=chunk.get('start_char',0)
    for part_index,part in enumerate(parts):
        text=part['text'];offset=part.get('start_char',cursor)
        # Короткая цельная реплика сохраняет и введение, и последующее
        # условие/действие. Граница original attribution part не пересекается.
        for start,end in ([(0,len(text))] if len(text)<=700 else paragraph_spans(text)):
            raw=text[start:end]
            if not raw.strip():continue
            a=start+len(raw)-len(raw.lstrip());b=end-(len(raw)-len(raw.rstrip()))
            spans=[(a,b)]
            if b-a>700:
                # Не разрезаем предложение посреди отрицания/условия.
                boundaries=[a]+[a+m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-ZА-ЯЁ\d])',text[a:b])]+[b]
                spans=list(zip(boundaries,boundaries[1:]))
            for x,y in spans:
                raw=text[x:y];left=len(raw)-len(raw.lstrip());right=len(raw)-len(raw.rstrip());x+=left;y-=right
                if x>=y:continue
                unit={'evidence_id':source_ref+'.U'+str(len(units)+1),'source_ref':source_ref,
                      'chunk_id':chunk['chunk_id'],'document_id':chunk['document_id'],'source':chunk['source'],
                      'part_index':part_index,'start_char':offset+x,'end_char':offset+y,
                      'author':part.get('author'),'date':part.get('date'),'attribution':part.get('attribution','unknown'),
                      'text':text[x:y]}
                # Короткое согласие/уточнение остаётся рядом с исходным
                # antecedent; соседний автор сохраняет собственную атрибуцию.
                unit['context_ids']=[units[-1]['evidence_id']] if units and len(unit['text'])<120 else []
                units.append(unit)
        cursor=offset+len(text)
    return units


# «Не только» включает дополнительную роль, а не исключает её.
EXCLUDED_CONDITIONS=re.compile(r'\b(?:за\s+исключением|исключая|не(?!\s+только\b)|без|кроме)\s+(?:\w+\s+){0,2}(?:услови\w*|задани\w*|требован\w*)',re.I)
EXCLUDED_NOTES=re.compile(r'\b(?:за\s+исключением|исключая|кроме|без|не(?!\s+только\b)(?:\s+из)?)\s+(?:(?:моих|моей|мою|личных|личной|личную|этих|этой|эту|своих|своей|собственных)\s+){0,2}замет(?:к\w*|ок)\b',re.I)


def conditions_requested(text):
    """Прямой запрос текста/условий, не место совершения действия."""
    text=EXCLUDED_CONDITIONS.sub('',text)
    additive=bool(re.search(r'\bне\s+только\b[^,;.!?\n]*\b(?:услови\w*|требован\w*)',text,re.I))
    text=re.sub(r'\bне\s+только\s+','',text,flags=re.I)
    subject=r'(?:услови\w*|требован\w*|задани\w*)'
    qualifier=r'(?:(?:мне|нам|про|о|само|самые|это|эти|данное|данные|основные|точные|полные|текст|содержание)\s+){0,4}'
    imperative=r'(?:объясни(?:те)?|расскажи(?:те)?|опиши(?:те)?|покажи(?:те)?|приведи(?:те)?|процитируй(?:те)?|сформулируй(?:те)?|назови(?:те)?|разбери(?:те)?|сравни(?:те)?)'
    direct=bool(re.search(r'\b'+imperative+r'\s+'+qualifier+subject,text,re.I))
    # «Позиция участника и условия…» — смешанный запрос. «Проблема
    # участника в задании…» либо «как он выполнял условия» им не является.
    conditions=r'(?:услови\w*|требован\w*)'
    interrogative=bool(re.search(r'\b(?:каков\w*|какой|какая|какое|какие|какую|каких|каким|что\s+за)\s+'+qualifier+conditions,text,re.I))
    enumerated=bool(re.search(r'(?:^|[;:,]|\s+и\s+)\s*'+conditions,text,re.I))
    return additive or direct or interrogative or enumerated


# AICODE-NOTE: речь/отчёт допускает неизвестный handle; общее действие
# требует явной роли или реального имени из полного каталога originals.
SPEECH_VERB=re.compile(r'\b(?:(?:по|под|пере|на|за|про|вы|при|от|до|об|раз|рас|с))?(?:говор|сказ|рассказ|рассужд|предлож|предлаг|рекоменд|совет|пис|пиш|опис|ответ|отвеч|сообщ|упомин|отме[тч]|объясн|жал)\w*(?:л[аи]?|[еиюяуа]т|ешь|ете|ите|ем|им)\b',re.I)
REPORT_VERB=re.compile(r'\b(?:(?:по|от))?(?:жал|подел|отчит)\w*л[аи]?(?:сь|ся)\b',re.I)


NONPERSON_SUBJECT=r'(?:программа|приложение|модель|инструмент|сервис)'
SUBJECT_BEFORE_SPEECH=re.compile(r'\b'+NONPERSON_SUBJECT+r'\b(?:\s+[\w.-]+){0,2}\s*$',re.I)
SUBJECT_AFTER_SPEECH=re.compile(r'\s+'+NONPERSON_SUBJECT+r'\b',re.I)
OBJECT_PREPOSITION=re.compile(r'\b(?:о|об|про|для|в|на|с|к|у|от|без|из)\s*$',re.I)


def person_speech(text):
    # Явный subject «приложение предлагает» отличается от человека,
    # говорящего «о приложении». Не определяем лицо по регистру названия.
    for verb in list(SPEECH_VERB.finditer(text))+list(REPORT_VERB.finditer(text)):
        before=text[:verb.start()];after=text[verb.end():]
        subject=SUBJECT_BEFORE_SPEECH.search(before)
        entity_before=bool(subject and not OBJECT_PREPOSITION.search(before[:subject.start()]))
        # В инверсии «Что предлагает приложение» роль стоит сразу за
        # глаголом. «Nebulon описал приложение» имеет отдельное подлежащее.
        entity_after=bool(SUBJECT_AFTER_SPEECH.match(after) and
                          re.search(r'(?:^|\b(?:что|как|почему|когда|где|зачем))\s*$',before,re.I))
        if not entity_before and not entity_after:return True
    return False


def participant_intent(text,authors):
    """Вопрос о лице и формы семейств глаголов, без зависимости от retrieval."""
    definition=bool(re.search(r'\b(?:кто\s+так(?:ой|ая|ое|ие)|что\s+(?:такое|означает|значит))\b',text,re.I))
    who=bool(re.search(r'\bкто\b',text,re.I)) and not definition
    advice=bool(re.search(r'\bсовет(?:ы|ов|а|ами|ах)?\b|\b(?:каки\w*|чьи|сколько|что\s+за)\s+(?:\w+\s+){0,2}рекомендаци\w*\b',text,re.I))
    if re.search(r'^\s*что\s+(?:такое|означает|значит)\b',text,re.I):advice=False
    archive_role=bool(re.search(r'участник|переписк|обсужд|реплик|позици|мнен',text,re.I))
    person_role=bool(re.search(r'\b(?:автор\w*|человек\w*|коллег\w*|собеседник\w*|он|она)\b',text,re.I))
    speech=person_speech(text) and not definition
    return bool(who or speech or advice or archive_role or person_role or matching_authors(authors,text))


def admissibility_policy(question,query,units,parts_by_chunk,author_catalog=None):
    """Роль originals ограничивает proof IDs; не проверяет смысл ответа."""
    text=query.get('search_query') or question
    authors={u['author'] for u in units if u.get('author')} if author_catalog is None else author_catalog
    actor=participant_intent(text,authors)
    # Явное текущее исключение имеет приоритет над прежним mixed scope.
    condition_scope=question if EXCLUDED_CONDITIONS.search(question) else text
    conditions=conditions_requested(condition_scope)
    note_scope=question if EXCLUDED_NOTES.search(question) else text
    notes=bool(re.search(r'\bзамет(?:к\w*|ок)\b',EXCLUDED_NOTES.sub('',note_scope),re.I))
    notes_excluded=bool(EXCLUDED_NOTES.search(note_scope)) and not notes
    participant_boundary=actor and not conditions
    actor_only=participant_boundary and not notes
    allowed=[];excluded=[]
    for u in units:
        reason=None
        if u['source']=='personal_note' and notes_excluded:reason='personal_note_explicitly_excluded'
        elif u['source']=='personal_note' and notes:
            # Запрошенная заметка имеет собственную роль/подпись. Она не
            # наследует имя участника и не открывает assignment proof IDs.
            pass
        elif participant_boundary:
            part=parts_by_chunk[u['chunk_id']][u['part_index']]
            features=evidence_features([part])
            if u['source']=='assignment':reason='assignment_is_background_for_participant_statements'
            elif features['assignment_announcement']:reason='task_announcement_is_background'
            elif features['compiled_summary']:reason='compiled_summary_is_background'
            elif features['link_only_navigation']:reason='link_only_is_navigation'
            elif u['source']=='personal_note':reason='personal_note_not_requested_as_participant_proof'
            elif not u.get('author') or u.get('attribution')!='original':reason='participant_attribution_unconfirmed'
        if reason:excluded.append({'evidence_id':u['evidence_id'],'reason':reason})
        else:allowed.append(u['evidence_id'])
    return {'actor_only':actor_only,'explicit_conditions':conditions,'explicit_personal_notes':notes,
            'participant_source_boundary':participant_boundary,'allowed_evidence_ids':allowed,
            'excluded_evidence_units':excluded,'verification':'source_role_only_not_semantic_support'}


def response_schema(aspects,units,allowed_evidence_ids=None,answer_limits=None):
    if len({u['source_ref'] for u in units})>MAX_OUTPUT_REFS:raise ValueError('invalid_evidence_context_source_limit')
    all_ids=[u['evidence_id'] for u in units]
    ids=all_ids if allowed_evidence_ids is None else list(allowed_evidence_ids)
    if len(set(ids))!=len(ids) or not set(ids)<=set(all_ids):raise ValueError('invalid_evidence_allowlist')
    questions=[a['id'] for a in aspects]
    assignment={'type':'array','minItems':1,'maxItems':len(questions),'uniqueItems':True,
                'items':{'type':'string','enum':questions}}
    schema={'type':'object','required':['evidence','coverage'],'additionalProperties':False,
        'properties':{'evidence':{'type':'object','maxProperties':MAX_SELECTED_UNITS,'additionalProperties':False,
            'properties':{eid:assignment for eid in ids}},
            'coverage':{'type':'object','required':questions,'additionalProperties':False,
                'properties':{qid:{'type':'string','enum':['full','partial','none']} for qid in questions}}}}
    if (answer_limits or {}).get('max_proof_units')==1:
        # AICODE-NOTE: pinned llama.cpp игнорирует maxProperties; exact oneOf branches
        # ограничивают grammar, а backend независимо проверяет количество proof keys.
        branches=[{'type':'object','properties':{},'additionalProperties':False}]
        branches.extend({'type':'object','required':[eid],'properties':{eid:assignment},'additionalProperties':False} for eid in ids)
        schema['properties']['evidence']={'oneOf':branches}
    return schema


def dialogue_focus(query,turns,units):
    """Указатели на заново найденные originals, не доказательство из истории."""
    empty={'evidence_ids':[],'prior_request_id':None,'reason':'no_followup_focus'}
    if query.get('intent')!='followup':return empty
    prior=next((t for t in reversed(turns) if t.get('status') in ('done','unknown') and
                (t.get('query') or {}).get('intent') not in ('clarification','acknowledgement')),None)
    if not prior:return empty
    answer=prior.get('answer') or {};old_units=answer.get('evidence_units')
    fields=('chunk_id','start_char','end_char','text','author','date','attribution')
    refs=answer.get('source_refs',[]);sources=answer.get('sources',[])
    matched=[]
    if any(isinstance(s,dict) and 'evidence_id' in s for s in sources) or any('.U' in r for r in refs if isinstance(r,str)):
        # AICODE-NOTE: Day30 refs обозначают spans, а S-номер меняется при fresh retrieval.
        # Совпадение всего immutable span не захватывает соседнюю реплику того же чанка.
        cited=[s for s in sources if isinstance(s,dict) and s.get('evidence_id') in refs]
        pointers={tuple(s.get(k) for k in fields) for s in cited}
        matched=[u['evidence_id'] for u in units if tuple(u.get(k) for k in fields) in pointers]
        reason='fresh_spans_match_previous_cited_day30_evidence'
    elif isinstance(old_units,list) and old_units:
        pointers={tuple(u.get(k) for k in fields) for u in old_units if isinstance(u,dict)}
        matched=[u['evidence_id'] for u in units if tuple(u.get(k) for k in fields) in pointers]
        reason='fresh_units_match_previous_cited_original_units'
    elif refs and all(isinstance(r,str) and re.fullmatch(r'S\d+',r) for r in refs):
        # Legacy receipts действительно ссылаются на whole chunk S1, не S1.U1.
        cited={s.get('chunk_id') for s in sources if isinstance(s,dict) and s.get('source_ref') in refs}
        matched=[u['evidence_id'] for u in units if u['chunk_id'] in cited]
        reason='fresh_units_from_legacy_cited_chunks'
    else:reason='no_previous_cited_originals'
    return {'evidence_ids':matched,'prior_request_id':prior.get('request_id'),'reason':reason,
            'role':'navigation_to_fresh_sources_not_historical_fact_evidence'}
