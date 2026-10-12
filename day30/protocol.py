"""Protocol06: deterministic provenance и структурный контракт; не semantic PASS."""
import copy
import json
import re

UNKNOWN_CONCLUSION='Вывод: уточните вопрос или нужный источник.'
UNKNOWN_SUMMARY='Не знаю по переданному контексту: не выбран подтверждённый пересказ. Это не доказывает отсутствие сведений во всём архиве.'

def outside_quotes(text):
    """Маскируем вложенные цитаты; escaped delimiters и апострофы слов не закрывают их."""
    pairs={'«':'»','„':'“','“':'”','‘':'’','"':'"',"'":"'"}
    stack=[];masked=[];escaped=False
    # AICODE-NOTE: regex останавливался на первом closing delimiter и принимал
    # команду внутри outer quote. Stack сохраняет nesting без изменения wire question.
    for i,char in enumerate(text):
        quoted=bool(stack)
        if escaped:
            escaped=False
        elif char=='\\':
            escaped=True
        elif char in ("'",'’') and i>0 and i+1<len(text) and text[i-1].isalnum() and text[i+1].isalnum():
            pass
        elif stack and char==stack[-1]:
            stack.pop()
        elif char in pairs:
            stack.append(pairs[char])
        masked.append(' ' if quoted or stack else char)
    return ''.join(masked)

def answer_limits(question):
    """Узкая команда одного примера только в текущем вопросе, без наследования темы."""
    text=re.sub(r'[^\S\n]+',' ',question.lower().replace('ё','е').replace('\r','\n'))
    distributive=re.search(r'\bкажд\w*\b|\bпо\s*(?:одному|одной|1)\b',text)
    outside=outside_quotes(text)
    single=re.search(r'(?:^|[?!.;\n])\s*(?:пожалуйста(?:\s*,\s*|\s+))?(?:назови|приведи|покажи)\s+'
        r'(?:(?:мне|пожалуйста)\s+)?(?:один|одну|одно|1)\s+'
        r'(?:(?:конкретный|конкретную|конкретное)\s+)?(?:пример|проблему|вопрос)\b',outside)
    return {'max_proof_units':1 if single and not distributive else 8,'max_points':1 if single and not distributive else 4}

WIRE_FIELDS={'selection':{'evidence':'a_evidence','coverage':'b_coverage'},
    'synthesis':{'points':'a_points','doubtful_aspect_ids':'b_doubtful_aspect_ids','conclusion':'c_conclusion'}}
CONCLUSION_FIELDS={'text':'a_text','point_refs':'b_point_refs'}

def wire_schema(stage,schema):
    """Переименовываем только структурные schema paths, без обхода IDs/текста."""
    fields=WIRE_FIELDS[stage];result=copy.deepcopy(schema)
    result['properties']={fields[key]:value for key,value in result['properties'].items()}
    result['required']=[fields[key] for key in result['required']]
    if stage=='synthesis':
        conclusion=result['properties']['c_conclusion']
        conclusion['properties']={CONCLUSION_FIELDS[key]:value for key,value in conclusion['properties'].items()}
        conclusion['required']=[CONCLUSION_FIELDS[key] for key in conclusion['required']]
    # AICODE-NOTE: native Qwen3 route сериализует Go map с alphabetical keys.
    # Структурные aliases сохраняют grounding-first даже после provider сортировки.
    return result

def normalize_wire(stage,value):
    fields=WIRE_FIELDS[stage]
    if not isinstance(value,dict) or set(value)!=set(fields.values()):raise ValueError('invalid_wire_shape')
    result={key:value[alias] for key,alias in fields.items()}
    if stage=='synthesis':
        conclusion=result['conclusion']
        if not isinstance(conclusion,dict) or set(conclusion)!=set(CONCLUSION_FIELDS.values()):raise ValueError('invalid_wire_shape')
        result['conclusion']={key:conclusion[alias] for key,alias in CONCLUSION_FIELDS.items()}
    return result

def wire_value(stage,value):
    """Тестовые canonical fixtures переводятся только по тем же structural paths."""
    result={alias:value[key] for key,alias in WIRE_FIELDS[stage].items()}
    if stage=='synthesis':result['c_conclusion']={alias:value['conclusion'][key] for key,alias in CONCLUSION_FIELDS.items()}
    return result

def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate_json_key')
            result[key]=value
        return result
    def constant(value):raise ValueError('invalid_model_json')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)

def unique_ids(value,allowed,minimum=0,maximum=6):
    return (isinstance(value,list) and minimum<=len(value)<=maximum and
            all(isinstance(v,str) and v in allowed for v in value) and len(set(value))==len(value))

def validate_selection(raw,aspects,units,allowed,answer_limits=None):
    if not isinstance(raw,dict) or set(raw)!={'evidence','coverage'} or not isinstance(raw['evidence'],dict):
        raise ValueError('invalid_selection_mapping')
    qids={a['id'] for a in aspects};by_id={u['evidence_id']:u for u in units}
    if not isinstance(raw['coverage'],dict) or set(raw['coverage'])!=qids:raise ValueError('invalid_selection_coverage')
    if len(raw['evidence'])>(answer_limits or {}).get('max_proof_units',8):
        raise ValueError('invalid_selection_quantity' if (answer_limits or {}).get('max_proof_units')==1 else 'invalid_selection_mapping')
    assigned={qid:[] for qid in qids};selected=[]
    for eid,groups in raw['evidence'].items():
        if not isinstance(eid,str) or eid not in allowed or eid not in by_id or not unique_ids(groups,qids,1):
            raise ValueError('invalid_selection_mapping')
        selected.append(eid)
        for qid in groups:assigned[qid].append(eid)
    for qid,status in raw['coverage'].items():
        if not isinstance(status,str) or status not in ('full','partial','none') or (status=='none')!= (not assigned[qid]):
            raise ValueError('invalid_selection_coverage')
    expanded=[]
    for eid in selected:
        for prior in by_id[eid].get('context_ids',[]):
            if prior in by_id and prior not in expanded:expanded.append(prior)
        if eid not in expanded:expanded.append(eid)
    if len({by_id[eid]['source_ref'] for eid in expanded})>5:raise ValueError('too_many_selected_sources')
    chosen=[{**by_id[eid],'evidence_role':'proof' if eid in selected else 'background_context'} for eid in expanded]
    return chosen,{'coverage':dict(raw['coverage']),'aspect_evidence_ids':assigned,'proof_ids':selected,
                   'evidence_to_aspect_ids':copy.deepcopy(raw['evidence'])}

def retain_coverage(coverage,units):
    remaining={u['evidence_id'] for u in units};proof=[eid for eid in coverage['proof_ids'] if eid in remaining]
    assigned={qid:[eid for eid in ids if eid in proof] for qid,ids in coverage['aspect_evidence_ids'].items()}
    statuses={}
    for qid,ids in assigned.items():
        statuses[qid]='none' if not ids else 'partial' if len(ids)<len(coverage['aspect_evidence_ids'][qid]) else coverage['coverage'][qid]
    return {'coverage':statuses,'aspect_evidence_ids':assigned,'proof_ids':proof,
            'evidence_to_aspect_ids':{eid:list(coverage['evidence_to_aspect_ids'][eid]) for eid in proof}}

def model_projection(units,phase):
    """Full text once + essential metadata; backend units остаются неизменёнными."""
    sent={u['evidence_id'] for u in units};projected=[]
    for unit in units:
        item={key:unit.get(key) for key in ('evidence_id','source','author','date','attribution')}
        item['context_ids']=[eid for eid in unit.get('context_ids',[]) if eid in sent]
        item['text']=unit['text']
        if phase=='synthesis':item['evidence_role']=unit.get('evidence_role')
        projected.append(item)
    return projected

SYNTHESIS_SCHEMA={'type':'object','required':['points','doubtful_aspect_ids','conclusion'],'additionalProperties':False,
    'properties':{'points':{'type':'array','maxItems':4,'items':{'type':'object','additionalProperties':False,
        'required':['aspect_ids','evidence_id','text'],'properties':{
            'aspect_ids':{'type':'array','minItems':1,'maxItems':6,'uniqueItems':True,'items':{'type':'string'}},
            'evidence_id':{'type':'string'},
            'text':{'type':'string','minLength':1,'maxLength':300}}}},
        'doubtful_aspect_ids':{'type':'array','maxItems':6,'uniqueItems':True,'items':{'type':'string'}},
        'conclusion':{'type':'object','additionalProperties':False,'required':['text','point_refs'],
            'properties':{'text':{'type':'string','minLength':1,'maxLength':1000},
                'point_refs':{'type':'array','maxItems':4,'uniqueItems':True,'items':{'type':'string','enum':['P1','P2','P3','P4']}}}}}}

def synthesis_schema(aspects,units,coverage,answer_limits=None):
    schema=copy.deepcopy(SYNTHESIS_SCHEMA);qids=[a['id'] for a in aspects]
    props=schema['properties'];point=props['points']['items']['properties']
    point['aspect_ids']['items']['enum']=qids;point['evidence_id']['enum']=list(coverage['proof_ids'])
    maximum=(answer_limits or {}).get('max_points',4)
    props['points']['maxItems']=maximum
    refs=props['conclusion']['properties']['point_refs'];refs['maxItems']=maximum
    refs['items']['enum']=['P'+str(i) for i in range(1,maximum+1)]
    full=[qid for qid in qids if coverage['coverage'][qid]=='full']
    if full:props['doubtful_aspect_ids']['items']['enum']=full
    else:props['doubtful_aspect_ids']['maxItems']=0
    return schema

def materialize_synthesis(raw,aspects,units,coverage,diagnostic=None,answer_limits=None):
    if not isinstance(raw,dict) or set(raw)!={'points','doubtful_aspect_ids','conclusion'}:
        raise ValueError('invalid_synthesis_points')
    points=raw['points'];qids={a['id'] for a in aspects};by_id={u['evidence_id']:u for u in units};covered=set()
    if not isinstance(points,list):raise ValueError('invalid_synthesis_points')
    if len(points)>(answer_limits or {}).get('max_points',4):
        raise ValueError('invalid_synthesis_quantity' if (answer_limits or {}).get('max_points')==1 else 'invalid_synthesis_points')
    refs=[];spans=[]
    for number,point in enumerate(points,1):
        if not isinstance(point,dict) or set(point)!={'aspect_ids','evidence_id','text'}:raise ValueError('invalid_synthesis_points')
        groups=point['aspect_ids'];eid=point['evidence_id'];text=point['text']
        if not unique_ids(groups,qids,1):raise ValueError('invalid_point_aspects')
        if (not isinstance(eid,str) or eid not in by_id or eid not in coverage['proof_ids'] or
                by_id[eid].get('evidence_role')=='background_context' or
                any(eid not in coverage['aspect_evidence_ids'][qid] for qid in groups)):
            raise ValueError('invalid_point_reference')
        # AICODE-NOTE: модель выбирает immutable unit ID; весь quote/span и обязательные
        # missing вычисляет backend. Provenance не доказывает смысл пересказа/вывода.
        unit=by_id[eid]
        spans.append({'point_id':'P'+str(number),'evidence_id':eid,'source_ref':unit.get('source_ref'),
            'quote':unit['text'],'start_char':unit.get('start_char'),'end_char':unit.get('end_char')})
        if not isinstance(text,str) or not text.strip() or len(text)>300:raise ValueError('invalid_synthesis_points')
        covered.update(groups)
        if eid not in refs:refs.append(eid)
    full={qid for qid,status in coverage['coverage'].items() if status=='full'}
    doubtful=raw['doubtful_aspect_ids']
    if not unique_ids(doubtful,full):raise ValueError('invalid_doubtful_aspects')
    missing_set={qid for qid,status in coverage['coverage'].items() if status!='full'} | (qids-covered) | set(doubtful)
    missing=[a['id'] for a in aspects if a['id'] in missing_set]
    if diagnostic is not None:
        diagnostic.update(derived_missing_aspect_ids=missing,point_source_spans=spans)
    conclusion=raw['conclusion']
    if not isinstance(conclusion,dict) or set(conclusion)!={'text','point_refs'}:raise ValueError('invalid_conclusion_refs')
    text=conclusion['text'];point_refs=conclusion['point_refs'];point_ids={'P'+str(i) for i in range(1,len(points)+1)}
    if not isinstance(text,str) or not text.strip() or len(text)>1000 or not text.startswith('Вывод:'):
        raise ValueError('invalid_conclusion_refs')
    if not unique_ids(point_refs,point_ids,1 if points else 0,4):raise ValueError('invalid_conclusion_refs')
    if not points:
        if point_refs or text!=UNKNOWN_CONCLUSION:raise ValueError('invalid_unknown_points')
        return {'status':'unknown','summary':UNKNOWN_SUMMARY,'conclusion':UNKNOWN_CONCLUSION,'source_refs':[],'sources':[]}
    summary=' '.join(point['text'] for point in points)
    if missing:summary+=' Не полностью подтверждены аспекты: '+'; '.join(a['text'] for a in aspects if a['id'] in missing_set)+'.'
    if len(summary)>1800:raise ValueError('rendered_summary_too_long')
    sources=[]
    for ref in refs:
        unit=copy.deepcopy(by_id[ref]);unit['excerpts']=[{'text':unit['text'],'author':unit.get('author'),'date':unit.get('date'),'attribution':unit.get('attribution')}]
        sources.append(unit)
    return {'status':'supported' if not missing and all(v=='full' for v in coverage['coverage'].values()) else 'partial',
            'summary':summary,'conclusion':text,'source_refs':refs,'sources':sources}
