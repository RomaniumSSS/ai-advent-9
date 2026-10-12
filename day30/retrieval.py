"""Самостоятельная лексика Day29 full_chat_retrieval.py, база b3e607e."""
"""Полный чат: имена/IDF/авторские аспекты, без topic/author whitelist."""
from collections import Counter
from functools import lru_cache
import math,re

TRANSLITERATION=str.maketrans(dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
 ['a','b','v','g','d','e','e','zh','z','i','i','k','l','m','n','o','p','r','s','t','u','f','h','ts','ch','sh','shch','','y','','e','yu','ya'])))

def name_words(text):
    return re.findall(r'[^\W_]{3,}',text.casefold().replace('ё','е'))

@lru_cache(maxsize=8192)
def forms(word):
    raw=word.translate(TRANSLITERATION);result={raw}
    if re.search('[а-я]',word):
        stem=re.sub(r'(?:ого|ему|ому|ыми|ими|ым|им|ой|ей|ий|ый|ая|яя|ое|ее|ую|юю|а|я|у|ю|ы|и|е|о)$','',word)
        if len(stem)>=3:result.add(stem.translate(TRANSLITERATION))
    for item in list(result):
        result.add(re.sub(r'(?:skii|skiy|skij|sky|skoy|skoi|skomu|skogo|skaya|skuyu)$','sk',item))
        if len(item)>4 and item[-1:] in ('i','y','j'):result.add(item[:-1])
    return frozenset(result)

def matching_authors(authors,question):
    authors=sorted(set(authors))
    words=list(re.finditer(r"[^\W_]+",question))
    query_forms=[forms(w[0].casefold().replace('ё','е')) for w in words]
    slots={a:[forms(w) for w in name_words(re.sub(r'\[[^]]*\]','',a))] for a in authors}
    def neighboring(start,length):
        return all(re.fullmatch(r'[\s-]*',question[words[i].end():words[i+1].start()]) for i in range(start,start+length-1))
    full=[]
    for author in authors:
        seq=slots[author];n=len(seq)
        if not n:continue
        for i in range(len(words)-n+1):
            if not neighboring(i,n):continue
            window=query_forms[i:i+n]
            if all(a&b for a,b in zip(seq,window)) or n==2 and all(a&b for a,b in zip(reversed(seq),window)):
                full.append(author);break
    # Явная фамилия одного упоминания не достраивает другое имя через союз.
    occupied=set()
    known=set().union(*(slot for seq in slots.values() for slot in seq)) if slots else set()
    for i in range(len(words)-1):
        if neighboring(i,2) and query_forms[i]&known and query_forms[i+1]&known:occupied.update((i,i+1))
    matched=list(full)
    for author in authors:
        if author in matched:continue
        for i,qform in enumerate(query_forms):
            if i in occupied:continue
            for slot in slots[author]:
                if slot&qform and sum(any(slot&other for other in slots[b]) for b in authors)==1:
                    matched.append(author);break
            if author in matched:break
    return [a for a in matched if not any(len(slots[a])<len(slots[b]) and all(any(sa&sb for sb in slots[b]) for sa in slots[a]) for b in full)]

FUNCTION_WORDS='что как какой какая какие какую кто где зачем почему чем сколько именно можно нужно ли для при про после перед пример примеры участник участники переписка обсуждение обсуждения говорили обозначил предложил сообщал сказал второй первый разные назови расскажи подробно схема порядок вопрос они них него ее их этому этих этом этой этот тот таких такие три разных писал писали приводил приводили называть назвать советовал советы проверка проверку'

def technical_anchors(question,authors,normalize):
    """Явные uppercase/backtick термины, без списка технологий."""
    quoted=re.findall(r'`([^`\n]+)`',question)
    acronyms=re.findall(r'(?<!\w)[A-ZА-ЯЁ]{2,}[A-ZА-ЯЁ0-9_-]*(?!\w)',question)
    names=set().union(*(forms(w) for a in authors for w in name_words(a))) if authors else set()
    return sorted(t for t in normalize(' '.join(quoted+acronyms)) if t not in names)

def anchor_words(text,normalize):
    # AICODE-NOTE: точный короткий термин сопоставляется с допустимым
    # склонением кириллического слова, а не с произвольным prefix из 3 букв.
    variants=set(normalize(text))
    for word in name_words(text):
        if re.search('[а-я]',word):variants.update(forms(word))
    return variants

def similarity(a,b):
    if a==b:return 1.
    if min(len(a),len(b))<4:return 0.
    common=0
    for x,y in zip(a,b):
        if x!=y:break
        common+=1
    ratio=common/min(len(a),len(b))
    return ratio if common>=4 and ratio>=.75 else 0.

class Lexical:
    def __init__(self,chunks,attribution,normalize):
        self.chunks=chunks;self.attribution=attribution;self.normalize=normalize
        self.stop=normalize(FUNCTION_WORDS);self.rows={};self.anchor_rows={};df=Counter()
        for c in chunks:
            rows=[];anchor_rows=[]
            for part in attribution(c):
                terms=normalize(part['text'])-self.stop
                rows.append((part.get('author'),terms));df.update(terms)
                features=evidence_features([part])
                primary=bool(c['source']=='discussion' and part.get('author') and
                             not features['compiled_summary'] and not features['assignment_announcement'] and
                             not features['link_only_navigation'])
                anchor_rows.append((part.get('author'),anchor_words(part['text'],normalize),primary))
            self.rows[c['chunk_id']]=rows;self.anchor_rows[c['chunk_id']]=anchor_rows
        self.df=df;self.n=sum(len(rows) for rows in self.rows.values())
        self.authors={a for rows in self.rows.values() for a,_ in rows if a}
    @lru_cache(maxsize=4096)
    def idf(self,t):
        df=min(self.n,sum(n for w,n in self.df.items() if similarity(t,w)))
        return math.log(1+(self.n-df+.5)/(df+.5))
    def terms(self,question,authors,author=None):
        if author:
            clauses=re.split(r'[;:]|\s+и\s+(?=(?:что|какую|какой|как|почему|зачем|какие|где|чем)\b)',question,flags=re.I)
            matching=[cl for cl in clauses if author in matching_authors(authors,cl)]
            if matching:question=' '.join(matching)
        # AICODE-NOTE: склонённое/транслитерированное имя не является
        # топическим признаком; удаляем все совпавшие name forms до stem.
        names=set().union(*(forms(w) for a in authors for w in name_words(a))) if authors else set()
        topical=[w for w in name_words(question) if not forms(w)&names]
        return self.normalize(' '.join(topical))-self.stop
    def score(self,c,terms,author=None):
        available=set().union(*(words for a,words in self.rows[c['chunk_id']] if not author or a==author))
        weight=sum(self.idf(t) for t in terms)
        return sum(self.idf(t)*max((similarity(t,w) for w in available),default=0) for t in terms)/weight if weight else 0.
    def anchor_matches(self,c,anchors,author=None,primary_only=False):
        available=set().union(*(words for a,words,primary in self.anchor_rows[c['chunk_id']]
                               if (not author or a==author) and (not primary_only or primary)))
        return sorted(set(anchors)&available)


def multiple_examples(question):
    return bool(re.search(r'\b(?:пример\w*|случа\w*|вариант\w*|способ\w*|сценари\w*)\b',question,re.I) and
                re.search(r'\b(?:разн\w*|нескольк\w*|два|две|три|четыре|пять|[2-9])\b',question,re.I))


def evidence_features(parts):
    # Это ранжирование первичных реплик, а не доказательство совершённого
    # действия: условная конструкция и отчёт остаются различными статусами.
    text=' '.join(p['text'] for p in parts)
    compiled=bool(re.search(r'^(?:[^\w]*)(?:что обсуждали|дайджест|сводка обсуждений|обзор обсуждений)\b',text,re.I))
    without_urls=re.sub(r'https?://[^\s<>]+|www\.[^\s<>]+',' ',text,flags=re.I)
    caption=re.sub(r'\b(?:читать|читайте|полностью|подробнее|подробности|полная|полный|версия|статья|текст|источник|ссылка|здесь|тут|read|more|full|article|source|link|here)\b',' ',without_urls,flags=re.I)
    link_only=bool(without_urls!=text and not re.search(r'\w',caption))
    day_heading=bool(re.search(r'^[^\w]*(?:день|day)\s*\d+\s*(?:[.:-]|\n)',text,re.I))
    # AICODE-NOTE: «добавил/составил» — отчёт, не imperative. Эта
    # эвристика также ограничивает proof IDs, поэтому общего stem мало.
    directive=re.search(r'\b(?:реализуй(?:те)?|сравни(?:те)?|составь(?:те)?|добавь(?:те)?|создай(?:те)?|сделай(?:те)?|напиши(?:те)?|проверь(?:те)?|построй(?:те)?|используй(?:те)?)\b',text,re.I)
    condition_structure=re.search(r'(?:^|\n)\s*(?:задание|усиление|требования|цель|шаг(?:\s+\d+)?)\s*:',text,re.I)
    report=re.search(r'\b(?:я|мы)\s+(?:\w+\s+){0,3}(?:реализова\w*|сдела\w*|добави\w*|состави\w*|провери\w*|написа\w*|собра\w*|разработа\w*|использова\w*|примени\w*|планир\w*|хочу|буду)\b',text,re.I)
    first_instruction=min((m.start() for m in (directive,condition_structure) if m),default=len(text))
    own_intro=bool(report and report.start()<first_instruction and any(p.get('author') for p in parts))
    # Приглашение проверить уже описанную собственную работу не превращает
    # весь original report/plan в текст задания. Условия до отчёта остаются gate.
    announcement=bool(day_heading and (directive or condition_structure) and not own_intro)
    own=any(p.get('author') and
            (re.search(r'\b(?:я|мы|мной|нами|у меня|мой|наша?|свой)\b',p['text'],re.I) or
             re.search(r'\b(?:недавно|вчера|сегодня|уже|сейчас|пока)\s+(?:\w+\s+){0,3}(?:использова|сдела|реализова|разработ|примени|собра|написа|пилю|пишу)',p['text'],re.I))
            for p in parts)
    return {'compiled_summary':compiled,'assignment_announcement':announcement,'link_only_navigation':link_only,
            'primary_report_or_proposal':bool(own and not compiled and not announcement and not link_only)}
