"""Самостоятельные full metadata/атрибуция/ranking/тема Day29, база b3e607e."""
from collections import Counter
from contextlib import closing
import hashlib, json, re, sqlite3
from pathlib import Path
import local as core
from retrieval import Lexical, matching_authors, multiple_examples, evidence_features, technical_anchors
TOP_K=5
MAX_OUTPUT_REFS=5
THRESHOLD=.35
def load_full_index(root):
    identity,validated=core.load_index(root)
    by_id={c['chunk_id']:c for c in validated};chunks=[]
    path=Path(root).resolve()/core.GENERATION/'structure.db'
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        for cid,metadata in db.execute('SELECT chunk_id,metadata_json FROM chunks'):
            m=json.loads(metadata);c=by_id.get(cid)
            if c is None or m.get('chunk_id',cid)!=cid or m['text']!=c['text'] or m['text_sha256']!=hashlib.sha256(m['text'].encode()).hexdigest():raise ValueError('full_metadata_mismatch')
            chunks.append({**m,'chunk_id':cid,'vector':c['vector']})
    if len(chunks)!=len(validated) or len({c['chunk_id'] for c in chunks})!=724:raise ValueError('full_chunk_count_mismatch')
    counts=dict(Counter(c['source'] for c in chunks))
    if counts!={'assignment':24,'discussion':694,'personal_note':6}:raise ValueError('full_source_count_mismatch')
    return {**identity,'scope':'all','chunk_count':724,'document_count':663,'source_counts':counts},chunks

def attribution_parts(chunk):
    text=chunk['text'];start=chunk.get('start_char',0);end=chunk.get('end_char',start+len(text))
    if type(start) is not int or type(end) is not int or end-start!=len(text):
        return [{'text':text,'author':None,'date':None,'attribution':'unknown','reason':'invalid_chunk_offsets'}]
    members={m.get('id'):m for m in chunk.get('members',[]) if m.get('id') is not None}
    sections=[];boundaries={start,end}
    for s in chunk.get('source_sections',[]):
        a=s.get('text_start_char',s.get('start_char'));b=s.get('end_char');origin=s.get('start_char')
        if any(type(v) is not int for v in (a,b,origin)) or not origin<=a<=b:continue
        a=max(a,start);b=min(b,end)
        if a<b:
            sections.append((a,b,s.get('member_ids',[])));boundaries.update((a,b))
    # AICODE-NOTE: соседние авторы одного чанка не наследуют друг друга;
    # delimiter/непокрытые или перекрывающиеся offsets сохраняют неизвестность.
    points=sorted(boundaries);parts=[]
    for a,b in zip(points,points[1:]):
        if a==b:continue
        covered=[ids for x,y,ids in sections if x<=a and b<=y]
        ids={mid for group in covered for mid in group}
        originals=[members.get(mid) for mid in ids]
        tuples={(m.get('author'),m.get('date')) for m in originals if m is not None}
        missing=not ids or any(m is None for m in originals)
        ambiguous=len(tuples)>1 or len(covered)>1
        known=not missing and not ambiguous and len(tuples)==1
        author,date=next(iter(tuples)) if known else (None,None)
        state='original' if known and (author is not None or date is not None) else 'ambiguous' if ambiguous else 'unknown'
        part={'text':text[a-start:b-start],'start_char':a,'end_char':b,'author':author,'date':date,'attribution':state}
        if parts and all(parts[-1].get(k)==part.get(k) for k in ('author','date','attribution')) and parts[-1]['end_char']==a:
            parts[-1]['text']+=part['text'];parts[-1]['end_char']=b
        else:parts.append(part)
    return parts or [{'text':text,'author':None,'date':None,'attribution':'unknown'}]

def normalized_words(text):
    # Имена/лексика из индекса, без словаря участников или тем эксперимента.
    result=set()
    for word in re.findall(r"[^\W_]{3,}",text.casefold().replace('ё','е')):
        word=re.sub(r'(?:ского|скому|ским|ская|ской|скую|ский|ских|ыми|ого|ому|ами|ями|ов|ев|ом|ем|ой|ей|ая|ое|ые|ый|ий|а|я|у|ю|ы|и|е|о)$','',word) if len(word)>4 else word
        if len(word)>=2:result.add(word.translate(TRANSLITERATION))
    return result

def requested_authors(chunks,question):
    authors={p.get('author') for c in chunks for p in attribution_parts(c) if p.get('author')}
    return matching_authors(authors,question)

def retrieve_all(chunks,question,qvec,lexicon=None,ranked_out=None):
    core.vector(qvec)
    examples=multiple_examples(question);input_limit=8 if examples else TOP_K
    lexicon=lexicon or Lexical(chunks,attribution_parts,normalized_words)
    authors=requested_authors(chunks,question)
    topical_anchors=technical_anchors(question,authors,normalized_words)
    query_terms=lexicon.terms(question,authors)
    author_terms={a:lexicon.terms(question,authors,a) for a in authors}
    discussion_intent=bool(authors or re.search(r"обсужд|реплик|участник|переписк|советов|предлаг|сказал|ответил|мнени|позици",question,re.I))
    # Резервирование требует полного day token/числа; legacy public parser
    # допускает частичные совпадения Day130 и подстроку в «Сегодня 13».
    numbers=re.findall(r'\b(?:day|д(?:ень|ня|ни|ней|не|нях))\s*(\d+(?:\s*(?:и|,|/)\s*\d+)*)\b',question,re.I)
    days=list(dict.fromkeys(int(n) for group in numbers for n in re.findall(r'\d+',group) if 1<=int(n)<=31))
    assignment_intent=bool(days and re.search(r'задани|услови|требован',question,re.I))
    ranked=[]
    for c in chunks:
        cosine=sum(a*b for a,b in zip(qvec,core.vector(c['vector'])))
        lexical=lexicon.score(c,query_terms)
        parts=attribution_parts(c);features=evidence_features(parts)
        supported_authors={p.get("author") for p in parts if p.get("author")}
        author_matches=sorted(set(authors)&supported_authors)
        boost=.05 if assignment_intent and c.get('source')=='assignment' and c.get('day') in days else 0
        example_boost=(.1 if features['primary_report_or_proposal'] else -.08 if features['compiled_summary'] else -.05 if c['source']=='assignment' else 0) if examples else 0
        score=.7*cosine+.3*lexical+boost+(.12 if author_matches else 0)+(.06 if discussion_intent and c["source"]=="discussion" else 0)+example_boost
        topic_matches=lexicon.anchor_matches(c,topical_anchors)
        primary_matches=lexicon.anchor_matches(c,topical_anchors,primary_only=True)
        topic_priority=2 if discussion_intent and primary_matches else 1 if topic_matches else 0
        ranked.append({k:v for k,v in c.items() if k!='vector'}|{'score':score,'cosine':cosine,'lexical':lexical,'assignment_boost':boost,'evidence_features':features,'example_boost':example_boost,'author_matches':author_matches,'author_aspects':{a:lexicon.score(c,author_terms[a],a) for a in author_matches},
                     'topic_anchor_matches':topic_matches,'topic_primary_discussion_matches':primary_matches,'topic_navigation_priority':topic_priority})
    # Явный термин — navigation anchor как номер дня. Его наличие в
    # оригинале не является доказательством смыслового ответа на вопрос.
    ranked.sort(key=lambda c:(-c['topic_navigation_priority'],-c['score'],c['chunk_id']))
    if ranked_out is not None:ranked_out.extend(ranked)
    eligible=[c for c in ranked if c['score']>=THRESHOLD or c['topic_anchor_matches']]
    selected=eligible[:input_limit]
    diverse=[]
    if examples:
        # В широкой просьбе о разных примерах один повторяющийся обзор не
        # вытесняет несколько самостоятельных сценариев участников.
        explicit_terms=normalized_words(' '.join(re.findall(r'\b[A-Z][A-Za-z0-9_-]{1,}\b',question)))
        primary=[c for c in eligible if c['evidence_features']['primary_report_or_proposal'] and c['source']=='discussion' and
                 lexicon.score(c,explicit_terms or query_terms)>0]
        diverse=[];seen_authors=set()
        for c in primary:
            own={p.get('author') for p in attribution_parts(c) if p.get('author')}
            if own-seen_authors:diverse.append(c);seen_authors.update(own)
            if len(diverse)>=input_limit:break
        ids={c['chunk_id'] for c in diverse}
        selected=diverse+[c for c in eligible if c['chunk_id'] not in ids][:input_limit-len(diverse)]
    # Явно запрошенный тип не исключает остальные; сохраняем релевантный mixed scope.
    requested=[]
    if discussion_intent:requested.append('discussion')
    if re.search(r'задани|услови',question,re.I):requested.append('assignment')
    if re.search(r'заметк',question,re.I):requested.append('personal_note')
    for kind in requested:
        if any(c['source']==kind for c in selected):continue
        candidate=next((c for c in eligible if c['source']==kind),None)
        if candidate:
            if len(selected)>=input_limit:
                replace=next((i for i in range(len(selected)-1,-1,-1) if selected[i]['source'] not in requested or sum(x['source']==selected[i]['source'] for x in selected)>1),None)
                if replace is None:continue
                selected.pop(replace)
            selected.append(candidate)
    # AICODE-NOTE: номер дня уже задаёт точный source anchor без слова
    # «задание». Резервируем оригинал даже при низком semantic score;
    # это не source filter и не повышение cosine/lexical оценки.
    # Чистый запрос обсуждения сохраняет прежний mixed ranking.
    anchors=[]
    if not discussion_intent or assignment_intent:
        for day in days:
            candidate=next((c for c in ranked if c['source']=='assignment' and c.get('day')==day),None)
            if candidate:anchors.append(candidate)
    # Нужны обе позиции, когда релевантные оригиналы доступны; случайный
    # соседний автор не считается покрытием авторской части вопроса.
    author_anchors=[]
    for author in authors:
        candidates=[c for c in eligible if author in c['author_matches']]
        candidate=max(candidates,key=lambda c:(len(lexicon.anchor_matches(c,topical_anchors,author,True)),
                                               len(lexicon.anchor_matches(c,topical_anchors,author)),
                                               .8*c['author_aspects'][author]+.2*c['cosine'],c['score'])) if candidates else None
        if candidate and candidate not in author_anchors:author_anchors.append(candidate)
    day_anchors=list(anchors)
    topic_anchors=[]
    for term in topical_anchors:
        candidate=next((c for c in ranked if term in (c['topic_primary_discussion_matches'] if discussion_intent else c['topic_anchor_matches'])),None)
        if candidate is None:candidate=next((c for c in ranked if term in c['topic_anchor_matches']),None)
        if candidate and candidate not in topic_anchors:topic_anchors.append(candidate)
    anchors=author_anchors+anchors+topic_anchors
    # AICODE-NOTE: широкий shortlist всё равно станет пятью fresh sources.
    # Резервируем разнообразие внутри этой границы, иначе финальный score
    # sort снова оставит только повторяющиеся посты одного участника.
    diversity_anchors=[];reserved={c['chunk_id'] for c in anchors}
    represented={p['author'] for c in anchors if c['evidence_features']['primary_report_or_proposal']
                 for p in attribution_parts(c) if p.get('author')}
    for candidate in diverse:
        if candidate['chunk_id'] in reserved:continue
        own={p['author'] for p in attribution_parts(candidate) if p.get('author')}
        if own and own<=represented:continue
        if len(reserved)>=MAX_OUTPUT_REFS:break
        diversity_anchors.append(candidate);reserved.add(candidate['chunk_id']);represented.update(own)
    anchors+=diversity_anchors
    protected={c['chunk_id'] for c in anchors}
    for candidate in anchors:
        if any(c['chunk_id']==candidate['chunk_id'] for c in selected):continue
        if len(selected)>=input_limit:
            replace=next((i for i in range(len(selected)-1,-1,-1) if selected[i]['chunk_id'] not in protected and
                          (selected[i]['source'] not in requested or sum(c['source']==selected[i]['source'] for c in selected)>1)),None)
            if replace is None:continue
            selected.pop(replace)
        selected.append(candidate)
    selected.sort(key=lambda c:(c['chunk_id'] not in protected,-c['topic_navigation_priority'],-c['score'],c['chunk_id']))
    return selected,{'scope':'all','eligible_count':len(chunks),'above_threshold':sum(c['score']>=THRESHOLD for c in ranked),'top_k':input_limit,'output_max_refs':core.SOURCE_SCHEMA['properties']['source_refs']['maxItems'],'multiple_examples':examples,'threshold':THRESHOLD,
                     'technical_anchors':topical_anchors,'topic_navigation':'exact_normalized_term_with_cyrillic_inflection_aliases',
                     'topic_anchor_admitted_below_threshold':[c['chunk_id'] for c in eligible if c['score']<THRESHOLD],
                     'requested_topic_anchor_ids':[c['chunk_id'] for c in topic_anchors],
                     'selected_topic_anchor_ids':[c['chunk_id'] for c in selected if c['chunk_id'] in {a['chunk_id'] for a in topic_anchors}],
                     'requested_diversity_anchor_ids':[c['chunk_id'] for c in diversity_anchors],
                     'selected_diversity_anchor_ids':[c['chunk_id'] for c in selected if c['chunk_id'] in {a['chunk_id'] for a in diversity_anchors}],
                     'explicit_days':days,'public_day_filter':False,'source_counts':dict(Counter(c['source'] for c in chunks)),
                     'query_terms':sorted(query_terms),'author_query_terms':{a:sorted(t) for a,t in author_terms.items()},'requested_authors':authors,'discussion_intent':discussion_intent,'requested_source_types':requested,'selected_chunk_ids':[c['chunk_id'] for c in selected],
                     'requested_day_anchor_ids':[c['chunk_id'] for c in day_anchors],
                     'selected_day_anchor_ids':[c['chunk_id'] for c in selected if c['chunk_id'] in {a['chunk_id'] for a in day_anchors}]}

def resolve_query(question,turns):
    question=core.validate_question(question)
    ack=r'(?:спасибо(?: большое)?|понятно|ясно|понял|поняла|принято|разобрался|разобралась|ок(?:ей)?|хорошо|благодарю)'
    if re.fullmatch(ack+r'(?:[, .!]+\s*'+ack+r')*[.! ]*',question,re.I):
        return {'intent':'acknowledgement','search_query':None,'anchor':None,'reason':'acknowledgement_without_retrieval'}
    explicit=re.match(r'\s*(?:новая тема|другой вопрос|сменим тему)\s*[:—-]\s*(.+)',question,re.I)
    if explicit:return {'intent':'new_topic','search_query':explicit[1],'anchor':None,'reason':'explicit_topic_switch'}
    # Самостоятельное определение нового предмета важнее местоимения во второй
    # части фразы; правило грамматическое, без списка учебных тем.
    demonstratives=(r'это|этот|эта|эти|этого|этой|этому|этом|этим|эту|этих|этими|'
                    r'(?:тот|та|те|того|той|тому|том|тем|ту|тех|теми)(?=\s+[а-яё][\w-]*\b)|'
                    r'так(?:ой|ая|ое|ие|ого|ому|ом|им|ую|их|ими)(?=\s+[а-яё][\w-]*\b)')
    anaphors=r'\b(?:'+demonstratives+r'|он|она|оно|они|его|него|её|ее|неё|нее|ему|нему|ней|ней|ей|их|них|им|ним|ими|ними|там)\b'
    subject=re.search(r'(?:что такое|как работает|как устроен[ао]?|как настроить|расскажи (?:о|про))\s+([^?.!,]+)',question,re.I)
    if subject:
        head=re.split(r'\s+(?:и|а|но)\s+',subject[1],maxsplit=1)[0].strip()
        if core.words(head) and not re.search(anaphors,head,re.I):
            return {'intent':'new_topic','search_query':question,'anchor':None,'reason':'self_contained_new_subject'}
    # AICODE-NOTE: местоимение может ссылаться на предмет в ЭТОМ вопросе,
    # а не на историю. Именная конструкция «X — это ...» и обозначенный
    # номером/меткой предмет дают локальный antecedent без словаря тем курса.
    definition=re.search(r'(?:^|[.!?]\s*)([^.!?]+?)\s+[—–-]\s*это\b',question,re.I)
    if definition:
        prefix=definition[1].strip();tokens=re.findall(r'[\w-]+',prefix)
        if tokens and tokens[0].casefold() in ('в','на','по','из'):tokens=tokens[2:]
        grammar={'как','почему','что','именно','вот','так','это','этот','эта','он','она','они','его','её','их','там'}
        if core.words(' '.join(tokens))-grammar and not re.search(anaphors,prefix,re.I):
            return {'intent':'new_topic','search_query':question,'anchor':None,'reason':'local_named_definition'}
    first_ref=re.search(anaphors,question,re.I)
    for local_ref in re.finditer(r'\b(?:'+demonstratives+r'|этой|этих|этом|этому|этим)\s+([а-яё][\w-]*)',question,re.I):
        if first_ref is not None and first_ref.start()<local_ref.start():continue
        def stem(word):
            return re.sub(r'(?:иями|ями|ами|иях|ах|ов|ев|ом|ем|ам|ям|ою|ей|ой|ию|ия|ие|ий|ый|ые|ая|яя|ое|ее|а|я|е|у|ю|ы|и|о)$','',word.casefold())
        nominal=stem(local_ref[1])
        named=re.finditer(r'\b([А-Яа-яЁё][\w-]*)\s+(?:\d+\b|[A-ZА-ЯЁ][\w-]*\b)',question[:local_ref.start()])
        if len(nominal)>=2 and any(stem(item[1])==nominal for item in named):
            return {'intent':'new_topic','search_query':question,'anchor':None,'reason':'local_identified_antecedent'}
    # AICODE-NOTE: локальная именная тема до первой анафоры приоритетнее
    # истории. Короткие эллиптические вопросы сохраняют старый предмет.
    if first_ref:
        grammar=set('что как какой какая какие каком какие почему зачем именно имелось имел имела виду можно нужно нужен нужна нужны для при про после перед кто чем сколько это этот эта того такой так а но они оно он она его ее их там ли уже еще подробно подробнее расскажи объясни проверить фиксируется действует делать работает устроен устроена'.split())
        prefix=question[:first_ref.start()]
        meaningful=core.words(prefix)-grammar
        # Только родительный предлог/глагол не задаёт новый предмет; два
        # содержательных слова дают поиску шанс вместо раннего отказа.
        local_name=bool(meaningful and (re.search(r'[—–:]',prefix) or any(re.fullmatch(r'[A-Za-z][\w-]*',w) for w in meaningful)))
        discourse_ref=bool(re.search(r'\b(?:этой|этом|этих|той|том|тех)\s+(?:ветк\w*|реплик\w*|сообщени\w*|обсуждени\w*|разговор\w*|эпизод\w*)',question,re.I))
        if (len(meaningful)>=2 or local_name) and not discourse_ref:
            return {'intent':'new_topic','search_query':question,'anchor':None,'reason':'local_subject_before_reference'}
    follow=bool(re.search(anaphors+r'|подробнее|продолжи|а дальше|что именно|^(?:а\s+)?(?:почему(?:\s+так)?|что\s+дальше)\??$',question,re.I))
    if not follow:return {'intent':'new_topic','search_query':question,'anchor':None,'reason':'standalone_question'}
    previous=next((t for t in reversed(turns) if t.get('status') in ('done','unknown') and (t.get('query') or {}).get('intent') not in ('clarification','acknowledgement')),None)
    if previous is None:return {'intent':'clarification','search_query':None,'anchor':None,'reason':'followup_without_anchor'}
    anchor=(previous.get('query') or {}).get('anchor') or previous['question']
    if re.search(r'\b(?:он|она|его|него|её|ее|неё|нему|ней|ей)\b',question,re.I) and re.search(r'советов|сказ|писал|предлож|ответ|мнен|позици|счит|\bкто\b',question,re.I):
        # Множественное «они/из них» сохраняет коллективный предмет вопроса;
        # число авторов само по себе не делает такую группу неоднозначной.
        authors={p.get('author') for s in (previous.get('answer') or {}).get('sources',[]) for p in s.get('excerpts',[]) if p.get('author')}
        named=set(matching_authors(authors,question))
        if not named:
            prior_questions=(previous.get('query') or {}).get('topic_questions') or [anchor,previous['question']]
            for prior_question in reversed(prior_questions):
                named=set(matching_authors(authors,prior_question))
                if named:break
        if len(authors)>1 and len(named)!=1:
            return {'intent':'clarification','search_query':None,'anchor':anchor,'reason':'ambiguous_participant'}
    chain=(previous.get('query') or {}).get('topic_questions')
    if not chain:
        chain=[anchor]
        if previous['question']!=anchor:chain.append(previous['question'])
    chain=[chain[0]]+chain[-2:] if len(chain)>3 else list(chain)
    chain=list(dict.fromkeys(chain+[question]))
    return {'intent':'followup','search_query':'\nУточнение: '.join(chain),'anchor':anchor,
            'topic_questions':chain,'reason':'user_topic_chain'}

TRANSLITERATION=str.maketrans(dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
    ['a','b','v','g','d','e','e','zh','z','i','i','k','l','m','n','o','p','r','s','t','u','f','h','ts','ch','sh','shch','','y','','e','yu','ya'])))
