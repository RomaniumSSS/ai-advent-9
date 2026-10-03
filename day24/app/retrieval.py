# Provenance: day24/retrieval.py @ be94bf73db06bdbc1ed371da031ba40e1f5d73ea
"""Два этапа поиска: векторные кандидаты и наблюдаемый отбор."""
import math
import re
from dataclasses import asdict, dataclass
from common import messages, packed, vector
from temporal import context_record, prepare_chunks, without_dates

DAY = re.compile(r'(?<!\w)(?:day\s*(\d{1,2})(?!\w)|(?:д(?:ень|ня|ни|ней|не|нях)|задани(?:е|я|и|й|ях))\s*(\d{1,2})(?!\d)(?:\s*(?:и|,|/)\s*\d{1,2}(?!\d))*|\d{1,2}\s*[-–]?\s*(?:й|ый|го|ого)(?:\s*(?:и|,|/)\s*\d{1,2}\s*[-–]?\s*(?:й|ый|го|ого))*\s*д(?:ень|ня|ней)(?!\w))', re.I)
INTENT = re.compile(r'услов|задани|требован|результат|сравн|отлич|нужно|нужен|нужна|обязател|сдать|сдач|сда[её]т|допуска|усилени|объ[её]м|сделать|реализ|какие.*(?:шаг|этап)|что.*(?:долж|надо|сдел)', re.I)

ASSIGNMENT_NUMBER = re.compile(r'(?<!\w)(?:услови(?:е|я|и|й|ях)|лня)\s*(?:дня\s*)?(\d{1,2})(?![\d./])(? !\w)'.replace('(? !','(?!'), re.I)

def explicit_days(question):
    question=without_dates(question)
    days = []
    for match in DAY.finditer(question):
        if re.match(r'[./]\d',question[match.end():]):continue
        numbers = re.findall(r'\d+', match.group())
        days.extend(int(n) for n in numbers if int(n) > 0)
    for match in ASSIGNMENT_NUMBER.finditer(question):
        if re.match(r'\s*(?:сообщен|рубл|процент|час|минут|сентябр|октябр)',question[match.end():],re.I):continue
        if int(match[1])>0:days.append(int(match[1]))
    return list(dict.fromkeys(days))

def rewrite(question):
    def replace(match):
        days = [int(n) for n in re.findall(r'\d+', match.group())]
        if any(n == 0 for n in days):
            return match.group()
        return ' и '.join('День ' + str(n) for n in days)
    after = DAY.sub(replace, question)
    return {'before': question, 'after': after, 'applied': after != question,
            'days': explicit_days(question), 'rule': 'normalize_explicit_day_only'}

def query_input(question):
    return 'Instruct: Given a question about the course, retrieve relevant passages that answer the question\nQuery:' + question

@dataclass(frozen=True)
class Config:
    rewrite: bool = False
    mixed: bool = True
    metadata: bool = True
    before: int = 20
    after: int = 5
    threshold: float = 0.35
    exact_assignment_bypass: bool = True
    context_bytes: int = 18000
    messages_bytes: int = 24000

    def validate(self):
        if type(self.before) is not int or type(self.after) is not int or self.before < 1 or not 0 <= self.after <= 5:
            raise ValueError('invalid_top_k')
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError('invalid_threshold')
        if not 0 <= self.context_bytes <= 18000 or not 0 <= self.messages_bytes <= 24000:
            raise ValueError('invalid_context_budget')

MODES = {'rag': Config()}

def words(text):
    return {w.casefold() for w in re.findall(r'[^\W_]+', text, re.UNICODE) if len(w) >= 3}

def retrieve(index, original_question, query_vector, config):
    if isinstance(config, dict):
        config = Config(**config)
    config.validate()
    chunks = index['chunks'] if isinstance(index, dict) else index
    original_count=len(chunks)
    chunks,temporal=prepare_chunks(chunks,original_question)
    dimensions = len(query_vector)
    vector(query_vector, dimensions)
    rw = rewrite(original_question)
    search = rw['after'] if config.rewrite else original_question
    query_words = words(search)
    scored = []
    seen = set()
    for chunk in chunks:
        if chunk['chunk_id'] in seen:
            raise ValueError('duplicate_index_chunk')
        seen.add(chunk['chunk_id'])
        v = vector(chunk['vector'], dimensions)
        cosine = sum(a*b for a,b in zip(query_vector,v)) / (math.sqrt(sum(x*x for x in query_vector))*math.sqrt(sum(x*x for x in v)))
        coverage = len(query_words & words(chunk.get('search_text',chunk['text']))) / len(query_words) if query_words else 0
        scored.append({k: val for k,val in chunk.items() if k != 'vector'} | {'cosine':cosine, 'lexical_coverage':coverage, 'mixed_score':.8*cosine+.2*coverage})
    ranked = sorted(scored, key=lambda c:(-c['cosine'],c['chunk_id']))
    candidates = [dict(c, vector_rank=i+1, exact_reason=None) for i,c in enumerate(ranked[:config.before])]
    days = explicit_days(original_question)
    eligible = bool(days and (INTENT.search(original_question) or re.fullmatch(r'\s*(?:day|день)\s*\d{1,2}\s*[?.!]*\s*',original_question,re.I)))
    exact_ids = set()
    if config.metadata and eligible:
        by_id = {c['chunk_id']:c for c in candidates}
        for c in scored:
            if c.get('source', c.get('source_type')) == 'assignment' and c.get('day') in days:
                exact_ids.add(c['chunk_id'])
                if c['chunk_id'] not in by_id:
                    added = dict(c, vector_rank=None, exact_reason=None)
                    candidates.append(added)
                    by_id[c['chunk_id']] = added
                by_id[c['chunk_id']]['exact_reason'] = 'explicit_assignment_intent_day_' + str(c['day'])
    score_key = 'mixed_score' if config.mixed else 'cosine'
    ordered = sorted(candidates, key=lambda c:(c['chunk_id'] not in exact_ids, -c[score_key],c['chunk_id']))
    context = ''
    selected, removed = [], []
    if len(packed(messages(original_question))) > config.messages_bytes:
        raise ValueError('question_exceeds_budget')
    for c in ordered:
        reason = None
        # AICODE-NOTE: Q1 разрешает обход только порога; scope/topK/байтовые лимиты сохраняются.
        if c[score_key] < config.threshold and not (config.exact_assignment_bypass and c['chunk_id'] in exact_ids):
            reason = 'threshold'
        elif len(selected) >= config.after:
            reason = 'top_k_after'
        piece = packed(context_record(c)).decode()
        proposed = context + ('\n\n' if context else '') + piece
        if reason is None and len(proposed.encode()) > config.context_bytes:
            reason = 'context_bytes'
        if reason is None and len(packed(messages(original_question,proposed))) > config.messages_bytes:
            reason = 'messages_bytes'
        item = dict(c, score=c[score_key], selection_reason=c['exact_reason'] or score_key)
        if reason:
            removed.append(dict(item, removal_reason=reason))
        else:
            selected.append(item)
            context = proposed
    return {'config':asdict(config), 'rewrite':dict(rw, enabled=config.rewrite), 'search_question':search,
            'metadata_rule':{'explicit_days':days,'assignment_intent':eligible,'enabled':config.metadata,
                             'reason':'explicit_assignment_intent' if eligible else 'no_explicit_day_or_assignment_intent'},
            'temporal':temporal,'counts':{'index':original_count,'eligible_after_temporal':len(chunks),'vector_candidates':min(config.before,len(chunks)),
                      'metadata_added':len(candidates)-min(config.before,len(chunks)), 'candidates':len(candidates),'selected':len(selected)},
            'candidates':ordered,'selected':selected,'removed':removed,'context':context,
            'context_bytes':len(context.encode()),'messages':messages(original_question,context),
            'empty':not selected}
