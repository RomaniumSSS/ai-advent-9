"""Bounded conversation context; retrieval remains a fresh source of evidence."""
import copy
import re
from common import SYSTEM, packed
from retrieval import explicit_days
from temporal import date_mentions, RANGE, RECENT, context_record
from search import PUBLIC_DOCUMENTS
from task_contract import answer_requirements
from structured_evidence import model_contract
from user_facts import user_fact_catalog, user_fact_contract

HISTORY_BYTES = 4000
TASK_BYTES = 4000
SEARCH_ADDITION_BYTES = 2000
SEARCH_BYTES = 18000
MESSAGES_BYTES = 24000
MAX_TURNS = 3
ROLE = ('Ты учебный помощник по материалам курса. Отвечай ясно, без лишнего оформления. '
        'Объясняй термины при необходимости. Память задачи — явно заданные пользователем цель, '
        'уточнения и действующие ограничения. Предложение ассистента не является решением пользователя. '
        'История разговора помогает понять вопрос, но не является документальным источником. '
        'Если query_analysis.clarification_needed=true, уточни, к чему относится продолжение; не придумывай тему. '
        'Сведения корпуса подтверждай только свежими фрагментами RAG. '
        'Явный день, дата и область текущего вопроса имеют приоритет перед историей. '
        'Действующее состояние задачи имеет приоритет перед устаревшими целями и ограничениями в истории. '
        'Сохраняй явно выбранные пользователем решения из task_state.clarifications, даже если текущий вопрос их не повторяет. '
        'Выбранное хранилище или пример — пользовательский выбор, а не обязательное требование задания; '
        'не заменяй его другим вариантом и не объявляй подтверждённым корпусом без источника. '
        'Различай ответ инструмента пользователю и формат сдачи задания: видео/код относятся к сдаче, '
        'а не автоматически к результату работы инструмента. '
        'Сопоставляя условие конкретного дня с обсуждениями, не требуй совпадения их дат или номера дня, '
        'если пользователь явно не ограничил период обсуждений. Используй только найденные обсуждения, '
        'атрибутируй их по метаданным и не выдумывай отсутствующие позиции. '
        'Структура каждого элемента sources строго {"source": "значение source переданного фрагмента", '
        '"chunk_id": "chunk_id этого фрагмента"}; поле source_key недопустимо.')
TASK_REFERENCE = (r'\b(?:мо(?:ей|ю|я)|наше(?:й|го)|нашу|наша)\s+(?:(?:нов(?:ой|ую|ая)|текущ(?:ей|ую|ая))\s+)?цел(?:и|ь|ью)\b'
                  r'|\b(?:помни|сохрани|соблюдая|соблюдай)\b.*\b(?:выбор|формат|ограничени\w*)\b'
                  r'|\bнаш(?:его|ему|им|ем|и|у|а)?\s+(?:выбор|план|формат)\w*\b'
                  r'|\b(?:действующ\w*|последн\w*)\s+(?:формат|ограничени\w*)\b'
                  r'|\bмы\s+(?:сами\s+)?выбрали\b')
DEMONSTRATIVE = re.compile(r'\b(?:это|этот|эта|эти|этого|этому|этим|этом|его|её|их|такой|такие|выше)\b', re.I)
FOLLOWUP = re.compile(r'\b(?:подробнее|продолжи)\b|^(?:а|значит)\b|^и\s+что\b.*\bему\b|\bсменим\s+цель\b', re.I)
# Compatibility for callers: classification itself has one ordered path below.
DEPENDENT = re.compile(DEMONSTRATIVE.pattern+'|'+FOLLOWUP.pattern+'|'+TASK_REFERENCE, re.I)
NAMED_TOPIC = re.compile(r'\b(?:найди|найдите|покажи|покажите)\s+обсуждени\w*(?:\s+курса)?\s+(?:о|про)\s+\w+|^(?:что\s+такое|расскажи\s+о|составь\s+(?:итоговый\s+)?план\s+(?:изучения|переезда))\b',re.I)
EXPLICIT_SCOPE = re.compile(r'\bтолько\s+(?:публичн\w*|обсуждени\w*|услови\w*|задани\w*)',re.I)


def filter_signature(text):
    signature = {}
    days = explicit_days(text)
    dates = date_mentions(text)
    if days: signature['days'] = sorted(set(days))
    if dates: signature['dates'] = sorted((d['year'] or 0,d['month'],d['day']) for d in dates)
    for name,pattern in (('range',RANGE),('recent',RECENT),('source_terms',EXPLICIT_SCOPE)):
        match=pattern.search(text)
        if match: signature[name]=match.group().casefold()
    return signature


def analyze_question(question):
    """One ordered decision; a task reference is a request, never a user fact."""
    if has_explicit_filter(question) or EXPLICIT_SCOPE.search(question):
        return {'mode':'explicit_filter','reason':'current_day_date_period_or_scope'}
    if re.search(TASK_REFERENCE,question,re.I):
        return {'mode':'continuation','reason':'explicit_task_reference'}
    if NAMED_TOPIC.search(question):
        return {'mode':'new_topic','reason':'independently_named_topic'}
    if FOLLOWUP.search(question) or DEMONSTRATIVE.search(question):
        return {'mode':'continuation','reason':'followup_or_demonstrative'}
    return {'mode':'new_topic','reason':'self_contained_question'}


def clipped(text, limit):
    return text.encode()[:max(0, limit)].decode('utf-8', errors='ignore')


def allowed_history(item, scope):
    if item.get('scope') != scope or item.get('historical'):
        return False
    if item.get('status') not in ('verified', 'model_refusal', 'no_context'):
        return False
    if scope == 'public':
        trace = item.get('search', {}).get('trace', {})
        materials = trace.get('candidates', []) + trace.get('selected', []) + trace.get('removed', []) + item.get('generation',{}).get('transmitted_chunks',[])
        if any(c.get('document_id') not in PUBLIC_DOCUMENTS for c in materials): return False
    return True


def bounded_state(state):
    effective = {'version':state['version'], 'goal':clipped(state['goal'], 1000),
                 'clarifications':[], 'constraints':[]}
    while len(packed(effective)) > TASK_BYTES:
        effective['goal'] = effective['goal'][:-1]
    for field in ('constraints', 'clarifications'):
        for value in state[field]:
            proposed = copy.deepcopy(effective)
            proposed[field].append(clipped(value, 1000))
            if len(packed(proposed)) > TASK_BYTES: break
            effective = proposed
    return effective, effective != state


def has_explicit_filter(question):
    return bool(explicit_days(question) or date_mentions(question) or RANGE.search(question) or RECENT.search(question))


def build_context(question, task_state, history, scope):
    state, state_truncated = bounded_state(task_state)
    permitted = [item for item in history if allowed_history(item, scope)]
    turns = permitted[-MAX_TURNS:]
    recent = []
    for item in reversed(turns):
        pair = [{'role':'user', 'content':clipped(item['question'], 700), 'request_id':item['id'], 'task_state_version':item.get('task_state_version')}]
        if item.get('answer'):
            pair.append({'role':'assistant', 'content':clipped(item['answer']['answer'], 700), 'request_id':item['id'], 'task_state_version':item.get('task_state_version')})
        if len(packed(pair + recent)) <= HISTORY_BYTES: recent = pair + recent
    analysis = analyze_question(question)
    explicit = analysis['mode'] == 'explicit_filter'
    dependent = analysis['mode'] == 'continuation'
    query = question
    rule = 'explicit_current_day_or_period' if explicit else 'current_question_only'
    anchor = None
    used_fields = []
    if dependent:
        anchors = [item for item in permitted
                   if item.get('task_state_version', 0) == state['version']
                   and analyze_question(item['question'])['mode'] in ('new_topic','explicit_filter')]
        anchor = anchors[-1] if anchors else None
        parts = []
        task_reference = analysis['reason']=='explicit_task_reference'
        independent_anchor = False
        if anchor:
            anchor_mode = analyze_question(anchor['question'])['mode']
            anchor_filters = filter_signature(anchor['question'])
            state_filters = filter_signature('\n'.join([state['goal']]+state['clarifications']+state['constraints']))
            conflict = bool(anchor_filters and state_filters and anchor_filters!=state_filters)
            independent_anchor = anchor_mode=='new_topic' or conflict

        if independent_anchor and task_reference: anchor = None
        use_state = not independent_anchor or task_reference
        analysis['state_policy'] = 'explicit_task_reference' if task_reference else ('independent_user_anchor_only' if independent_anchor else 'current_task_context')
        if anchor:
            parts.append(anchor['question'])
            used_fields.append('user_anchor.question')
        if use_state and state['goal']:
            parts.append(state['goal'])
            used_fields.append('task_state.goal')
        for field in ('clarifications','constraints'):
            for index,value in enumerate(state[field] if use_state else []):
                if value:
                    parts.append(value)
                    used_fields.append(f'task_state.{field}[{index}]')
        if not anchor and not state['goal']:
            parts = []
            used_fields = []
        prefix = '\nТема продолжения: '
        allowance = min(SEARCH_ADDITION_BYTES, SEARCH_BYTES-len(question.encode())-len(prefix.encode()))
        # Record only fields whose text was actually included, without partially cut filters.
        included = []
        actual_fields = []
        for field,part in zip(used_fields,parts):
            if len('\n'.join(included+[part]).encode()) <= allowance:
                included.append(part)
                actual_fields.append(field)
        used_fields = actual_fields
        if 'user_anchor.question' not in used_fields: anchor = None
        if included:
            query = question+prefix+'\n'.join(included)
            rule = 'task_state_and_substantive_user_question'
        else:
            analysis = {'mode':'ambiguous','reason':'continuation_without_current_user_context'}
            anchor = None
    analysis.update(used_fields=used_fields,task_state_version=state['version'],
                    anchor_request_id=anchor['id'] if anchor else None,
                    clarification_needed=analysis['mode']=='ambiguous',
                    scope_policy='chat_scope_unchanged; source words are query terms, not a source filter')
    referent=None
    if dependent and re.search(r'\b(?:это|этот|эта|эти|этого|этому|этим|этом|его|её|их)\b',question,re.I) and not explicit and turns and turns[-1].get('task_state_version')==state['version'] and re.search(r'цитат',turns[-1]['question'],re.I):
        last=turns[-1]
        referent={'request_id':last['id'],'user_question':clipped(last['question'],700),
                  'interpretation':'Nearest user request concerns a quotation; explain its impact on the current plan before older choices. Ask clarification if uncertain. History is not evidence: verify any claim against fresh_rag_context.'}
    return {'original_question':question, 'search_query':query, 'search_rule':rule, 'query_analysis':analysis,
            'search_anchor_request_id':anchor['id'] if anchor else None,
            'history':recent, 'user_facts':user_fact_catalog(state,recent,question), 'continuation_reference':referent, 'task_state':state, 'task_state_truncated':state_truncated,
            'limits':{'max_turns':MAX_TURNS,'history_bytes':HISTORY_BYTES,'task_bytes':TASK_BYTES,
                      'search_bytes':SEARCH_BYTES,'messages_bytes':MESSAGES_BYTES}, 'search_performed':False}


def generation_messages(question, conversation, chunks):
    context = '\n\n'.join(packed(context_record(c)).decode() for c in chunks)
    envelope = {'current_question':question, 'task_state':conversation['task_state'],
                'query_analysis':conversation.get('query_analysis'), 'recent_messages':conversation['history'], 'continuation_reference':conversation.get('continuation_reference'), 'fresh_rag_context':context,
                'user_fact_contract':user_fact_contract(conversation['user_facts']),
                'answer_requirements':answer_requirements(question,conversation['task_state']),
                'evidence_contract':model_contract(question,conversation['task_state'],chunks)}
    envelope['evidence_contract']['response_fields']['user_fact_refs'] = 'optional array of {fact_id,version} from user_fact_contract; never corpus evidence'
    return [{'role':'system', 'content':SYSTEM + '\n' + ROLE + '\nДля typed-evidence-v1 используй evidence_contract из envelope: допустимы дополнительные attributions/comparison. Дополнительно допустимо user_fact_refs по отдельному user_fact_contract; это ссылки на пользователя, не источники корпуса. Machine IDs выводи только typed refs, не в свободном тексте; прежнее требование ID в prose заменено typed refs.'},
            {'role':'user', 'content':packed(envelope).decode()}], context


def prepare_generation(question, conversation, trace):
    selected = trace['selected']
    while True:
        msgs, context = generation_messages(question, conversation, selected)
        if len(packed(msgs)) <= MESSAGES_BYTES: break
        if conversation['history']:
            conversation['history'] = conversation['history'][2:]
            conversation['history_truncated_for_generation'] = True
            conversation['user_facts'] = user_fact_catalog(conversation['task_state'],conversation['history'],question)
        elif selected:
            removed = selected.pop()
            trace.setdefault('removed', []).append(dict(removed, removal_reason='conversation_messages_bytes'))
        else:
            raise ValueError('conversation_exceeds_messages_budget')
    trace.update(messages=msgs, context=context, context_bytes=len(context.encode()), empty=not selected)
    if 'counts' in trace: trace['counts']['selected'] = len(selected)
    trace['conversation'] = copy.deepcopy(conversation)
    trace['original_question'] = question
    trace['search_query'] = conversation['search_query']
