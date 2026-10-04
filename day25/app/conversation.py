"""Bounded conversation context; retrieval remains a fresh source of evidence."""
import copy
import re
from common import SYSTEM, packed
from retrieval import explicit_days
from temporal import date_mentions, RANGE, RECENT, context_record
from search import PUBLIC_DOCUMENTS
from task_contract import answer_requirements
from structured_evidence import model_contract

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
# AICODE-NOTE: goal/choice references need current memory even without demonstrative pronouns; explicit filters still win below.
TASK_REFERENCE = (r'\b(?:мо(?:ей|ю|я)|наше(?:й|го)|нашу|наша)\s+(?:(?:нов(?:ой|ую|ая)|текущ(?:ей|ую|ая))\s+)?цел(?:и|ь|ью)\b'
                  r'|\b(?:помни|сохрани|соблюдая|соблюдай)\b.*\b(?:выбор|формат|ограничени\w*)\b'
                  r'|\bнаш(?:его|ему|им|ем|и|у|а)?\s+(?:выбор|план|формат)\w*\b'
                  r'|\b(?:действующ\w*|последн\w*)\s+(?:формат|ограничени\w*)\b')
DEPENDENT = re.compile(r'\b(?:это|этот|эта|эти|этого|этому|этим|этом|его|её|их|такой|такие|выше|подробнее|продолжи)\b|^(?:а|значит)\b|^и\s+что\b.*\bему\b|\bсменим\s+цель\b|' + TASK_REFERENCE, re.I)


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
        pair = [{'role':'user', 'content':clipped(item['question'], 700), 'request_id':item['id']}]
        if item.get('answer'):
            pair.append({'role':'assistant', 'content':clipped(item['answer']['answer'], 700), 'request_id':item['id']})
        if len(packed(pair + recent)) <= HISTORY_BYTES: recent = pair + recent
    explicit = has_explicit_filter(question)
    # AICODE-NOTE: a locally named discussion topic must not inherit old task days from deictic prose.
    named_discussion_topic=bool(re.search(r'\b(?:найди|найдите|покажи|покажите)\s+обсуждени\w*(?:\s+курса)?\s+(?:о|про)\s+\w+',question,re.I))
    task_reference=bool(re.search(TASK_REFERENCE,question,re.I))
    dependent = task_reference or (bool(DEPENDENT.search(question)) and not named_discussion_topic)
    query = question
    rule = 'current_question_only'
    anchor = None
    if explicit:
        rule = 'explicit_current_day_or_period'
    elif dependent:
        # AICODE-NOTE: assistant text is never used as a retrieval query or documentary evidence.
        anchors = [item for item in permitted
                   if item.get('task_state_version', 0) == state['version']
                   and (not DEPENDENT.search(item['question']) or has_explicit_filter(item['question']))]
        anchor = anchors[-1] if anchors else None
        parts = ([anchor['question']] if anchor else []) + [state['goal']] + state['clarifications'] + state['constraints']
        prefix = '\nТема продолжения: '
        extra = clipped('\n'.join(p for p in parts if p), min(SEARCH_ADDITION_BYTES, SEARCH_BYTES - len(question.encode()) - len(prefix.encode())))
        if extra:
            query = question + prefix + extra
            rule = 'task_state_and_substantive_user_question'
    referent=None
    if dependent and re.search(r'\b(?:это|этот|эта|эти|этого|этому|этим|этом|его|её|их)\b',question,re.I) and not explicit and turns and turns[-1].get('task_state_version')==state['version'] and re.search(r'цитат',turns[-1]['question'],re.I):
        last=turns[-1]
        referent={'request_id':last['id'],'user_question':clipped(last['question'],700),
                  'interpretation':'Nearest user request concerns a quotation; explain its impact on the current plan before older choices. Ask clarification if uncertain. History is not evidence: verify any claim against fresh_rag_context.'}
    return {'original_question':question, 'search_query':query, 'search_rule':rule,
            'search_anchor_request_id':anchor['id'] if anchor else None,
            'history':recent, 'continuation_reference':referent, 'task_state':state, 'task_state_truncated':state_truncated,
            'limits':{'max_turns':MAX_TURNS,'history_bytes':HISTORY_BYTES,'task_bytes':TASK_BYTES,
                      'search_bytes':SEARCH_BYTES,'messages_bytes':MESSAGES_BYTES}, 'search_performed':False}


def generation_messages(question, conversation, chunks):
    context = '\n\n'.join(packed(context_record(c)).decode() for c in chunks)
    envelope = {'current_question':question, 'task_state':conversation['task_state'],
                'recent_messages':conversation['history'], 'continuation_reference':conversation.get('continuation_reference'), 'fresh_rag_context':context,
                'answer_requirements':answer_requirements(question,conversation['task_state']),
                'evidence_contract':model_contract(question,conversation['task_state'],chunks)}
    return [{'role':'system', 'content':SYSTEM + '\n' + ROLE + '\nДля typed-evidence-v1 используй evidence_contract из envelope: допустимы дополнительные attributions/comparison. Machine IDs выводи только typed refs, не в свободном тексте; прежнее требование ID в prose заменено typed refs.'},
            {'role':'user', 'content':packed(envelope).decode()}], context


def prepare_generation(question, conversation, trace):
    selected = trace['selected']
    while True:
        msgs, context = generation_messages(question, conversation, selected)
        if len(packed(msgs)) <= MESSAGES_BYTES: break
        if conversation['history']:
            conversation['history'] = conversation['history'][2:]
            conversation['history_truncated_for_generation'] = True
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
