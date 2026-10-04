"""Typed evidence checks and metadata derived only from transmitted snapshots."""
import json
from answers import check_answer
from task_contract import format_errors, answer_requirements
import re


def narrative_errors(text):
    clean=text.replace('*','').replace('`','')
    if re.search(r'\b(?:message[_ -]?id|msg[_ -]?id|ID(?:\s+сообщения)?)\s*[:=#№]?\s*\d+',clean,re.I):
        return ['unstructured_message_id']
    return []


def _resolve_reference(ref,chunks,require_quote=False):
    fields={'chunk_id','message_id','day'}|({'quote'} if require_quote else set())
    if not isinstance(ref,dict) or set(ref)!=fields:return ['reference_schema'],None,None
    if not isinstance(ref['chunk_id'],str) or not ref['chunk_id']:return ['reference_chunk_id_invalid'],None,None
    if type(ref['message_id']) is not int or ref['message_id']<=0:return ['reference_message_id_invalid'],None,None
    if ref['day'] is not None and (type(ref['day']) is not int or ref['day']<=0):return ['reference_day_invalid'],None,None
    chunk=next((c for c in chunks if c['chunk_id']==ref['chunk_id']),None)
    if chunk is None:return ['reference_chunk_not_transmitted'],None,None
    if chunk.get('day') is not None and (type(chunk['day']) is not int or chunk['day']<=0):return ['context_day_invalid'],None,None
    if ref['day']!=chunk.get('day'):return ['reference_day_mismatch'],None,None
    parts=[m for m in chunk.get('message_parts',[]) if type(m.get('message_id')) is int and m.get('message_id')==ref['message_id']
           and m.get('attribution')=='single_member']
    if not parts:return ['reference_message_not_in_chunk'],None,None
    if require_quote:
        if not isinstance(ref['quote'],str) or not ref['quote'].strip():return ['reference_quote_not_in_message'],None,None
        errors=narrative_errors(ref['quote'])
        if errors:return errors,None,None
        parts=[m for m in parts if ref['quote'] in m['text']]
        if not parts:return ['reference_quote_not_in_message'],None,None
    return [],chunk,parts[0]


def reference_errors(ref,chunks,require_quote=False):
    return _resolve_reference(ref,chunks,require_quote)[0]


def _text_errors(row,fields):
    errors=[]
    for field in fields:
        if not isinstance(row[field],str) or not row[field].strip():errors.append('comparison_text_required')
        else:errors.extend(narrative_errors(row[field]))
    return errors


def _role_errors(ref,role,chunks):
    errors,chunk,_=_resolve_reference(ref,chunks,require_quote=True)
    if chunk and chunk.get('source')!={'requirement':'assignment','discussion':'discussion'}[role]:
        errors.append('comparison_wrong_source_role')
    return errors


def comparison_errors(rows,chunks):
    if not isinstance(rows,list) or not rows:return ['comparison_rows_required']
    errors=[]
    for row in rows:
        if not isinstance(row,dict):errors.append('comparison_schema');continue
        if row.get('status')=='insufficient_context':
            if set(row)!={'status','aspect','available_evidence','missing_sides','reason'}:
                errors.append('comparison_schema');continue
            errors.extend(_text_errors(row,('aspect','reason')))
            missing=row['missing_sides'];available=row['available_evidence']
            if (not isinstance(missing,list) or not missing or any(x not in ('requirement','discussion') for x in missing)
                or len(set(missing))!=len(missing) or not isinstance(available,list)):
                errors.append('insufficient_context_schema');continue
            roles=[]
            for evidence in available:
                if (not isinstance(evidence,dict) or set(evidence)!={'role','reference'}
                    or evidence['role'] not in ('requirement','discussion')):
                    errors.append('insufficient_context_schema');continue
                roles.append(evidence['role']);errors.extend(_role_errors(evidence['reference'],evidence['role'],chunks))
            if len(set(roles))!=len(roles) or set(roles)&set(missing) or set(roles)|set(missing)!={'requirement','discussion'}:
                errors.append('insufficient_context_sides')
            continue
        if set(row)!={'aspect','requirement','discussion','relationship','analysis'}:
            errors.append('comparison_schema');continue
        errors.extend(_text_errors(row,('aspect','analysis')))
        if row['relationship'] not in ('supports','supplements','differs'):errors.append('comparison_relationship_invalid')
        for role in ('requirement','discussion'):errors.extend(_role_errors(row[role],role,chunks))
    return errors


def metadata_for_reference(ref,chunks):
    errors,chunk,part=_resolve_reference(ref,chunks,require_quote=isinstance(ref,dict) and 'quote' in ref)
    if errors:raise ValueError('invalid_reference')
    return {'day':chunk.get('day'),'message_id':part['message_id'],
            'source':chunk['source'],'chunk_id':chunk['chunk_id'],'date':part.get('date'), 'author':part.get('author')}


SCHEMA_VERSION='typed-evidence-v1'


def comparison_required(question,state):
    requirements=answer_requirements(question,state)
    return requirements['comparison_requested'] and bool(re.search(r'обсужден|участник|позиц',question,re.I)) and bool(re.search(r'требован|услови',question,re.I))


def check_response(content,chunks,question,state):
    parsed=check_answer(content,chunks)
    data=parsed.get('answer')
    base_fields={'answer','sources','quotes'}
    if not isinstance(data,dict) or not base_fields<=set(data) or set(data)-base_fields-{'attributions','comparison'}:
        return dict(parsed,structure_valid=False,outcome='unverified')
    checked=check_answer(json.dumps({k:data[k] for k in base_fields},ensure_ascii=False),chunks)
    checked['normalization']=parsed.get('normalization','none')
    checked['answer']=data
    errors=checked['errors'][:]
    errors.extend(format_errors(data,state))
    if isinstance(data.get('answer'),str):errors.extend(narrative_errors(data['answer']))
    if isinstance(data.get('quotes'),list):
        for quote in data['quotes']:
            if isinstance(quote,dict) and isinstance(quote.get('text'),str):errors.extend(narrative_errors(quote['text']))
    sources=data.get('sources') if isinstance(data.get('sources'),list) else []
    quotes=data.get('quotes') if isinstance(data.get('quotes'),list) else []
    def cited(ref):
        return (isinstance(ref,dict) and any(isinstance(s,dict) and s.get('chunk_id')==ref.get('chunk_id') for s in sources)
                and any(isinstance(q,dict) and q.get('chunk_id')==ref.get('chunk_id') and q.get('text')==ref.get('quote') for q in quotes))
    attributions=data.get('attributions',[])
    rendered={'schema':SCHEMA_VERSION,'attributions':[],'comparison':[],'semantic_review':'NOT_PROVEN'}
    if not isinstance(attributions,list):errors.append('attributions_schema')
    else:
        for ref in attributions:
            ref_errors=reference_errors(ref,chunks)
            errors.extend(ref_errors)
            if ref_errors:continue
            matching=[q for q in quotes if isinstance(q,dict) and q.get('chunk_id')==ref['chunk_id'] and isinstance(q.get('text'),str)
                      and not reference_errors(dict(ref,quote=q['text']),chunks,require_quote=True)]
            if not matching or not any(isinstance(s,dict) and s.get('chunk_id')==ref['chunk_id'] for s in sources):
                errors.append('attribution_not_cited');continue
            rendered['attributions'].append(metadata_for_reference(dict(ref,quote=matching[0]['text']),chunks))
    required=comparison_required(question,state)
    rows=data.get('comparison',[])
    insufficient=False
    if required or rows:
        row_errors=comparison_errors(rows,chunks);errors.extend(row_errors)
        if not row_errors:
            for row in rows:
                if row.get('status')=='insufficient_context':
                    insufficient=True
                    refs=[e['reference'] for e in row['available_evidence']]
                    rendered_row={'status':'insufficient_context','aspect':row['aspect'],'reason':row['reason'],
                                  'missing_sides':row['missing_sides'],'available_evidence':[]}
                    for evidence in row['available_evidence']:
                        ref=evidence['reference']
                        rendered_row['available_evidence'].append({'role':evidence['role'],
                            'metadata':metadata_for_reference(ref,chunks),'quote':ref['quote']})
                else:
                    refs=[row['requirement'],row['discussion']]
                    rendered_row={'status':'compared','aspect':row['aspect'],'analysis':row['analysis'],'relationship':row['relationship']}
                    for role in ('requirement','discussion'):
                        rendered_row[role]={'metadata':metadata_for_reference(row[role],chunks),'quote':row[role]['quote']}
                if any(not cited(ref) for ref in refs):errors.append('comparison_evidence_not_cited')
                rendered['comparison'].append(rendered_row)
    elif not isinstance(rows,list):errors.append('comparison_schema')
    # AICODE-NOTE: a typed empty-context branch is not a substantive success and needs no invented citations.
    if insufficient and not sources and not quotes and all(not row.get('available_evidence',[]) for row in rows if row.get('status')=='insufficient_context'):
        errors=[e for e in errors if e not in ('missing_sources','missing_quotes')]
    checked.update(errors=sorted(set(errors)),structure_valid=not errors,valid=not errors and not insufficient,
                   outcome='insufficient_context' if not errors and insufficient else ('verified' if not errors else 'unverified'),
                   structured_evidence=rendered if not errors else None,schema=SCHEMA_VERSION,semantic_match=None)
    return checked


def model_contract(question,state,chunks):
    refs=[]
    for chunk in chunks:
        for part in chunk.get('message_parts',[]):
            ref={'chunk_id':chunk['chunk_id'],'message_id':part.get('message_id'),'day':chunk.get('day')}
            if not reference_errors(ref,chunks):refs.append(dict(ref,source=chunk.get('source')))
    participant_examples=[]
    for allowed in refs:
        if allowed.get('source')!='discussion' or len(participant_examples)>=2:continue
        ref={k:allowed[k] for k in ('chunk_id','message_id','day')}
        errors,chunk,part=_resolve_reference(ref,chunks,False)
        excerpt=part['text'][:90].strip() if not errors else ''
        if not excerpt or reference_errors(dict(ref,quote=excerpt),chunks,True):continue
        participant_examples.append({'attribution':ref,'source':{'source':chunk['source'],'chunk_id':chunk['chunk_id']},
                                     'quote':{'chunk_id':chunk['chunk_id'],'text':excerpt}})
    required=comparison_required(question,state)
    contract={'schema':SCHEMA_VERSION,'comparison_required':required,
            'allowed_attributions':refs,'participant_citation_examples':participant_examples,
            'response_fields':{'answer':'text without free machine IDs','sources':[{'source':'snapshot source','chunk_id':'snapshot chunk_id'}],
                               'quotes':[{'chunk_id':'snapshot chunk_id','text':'exact message text'}],
                               'attributions':'optional array of {chunk_id,message_id,day}, linked to a cited quote',
                               'comparison':'required nonempty array for comparison_required; otherwise omit' },
            'comparison_row':{'aspect':'text','requirement':{'chunk_id':'ID','message_id':'positive integer','day':'integer or null','quote':'exact text'},
                              'discussion':{'chunk_id':'ID','message_id':'positive integer','day':'integer or null','quote':'exact text'},
                              'relationship':'supports|supplements|differs','analysis':'text'},
            'insufficient_row':{'status':'insufficient_context','aspect':'text',
                                'available_evidence':'array of {role:requirement|discussion,reference:{chunk_id,message_id,day,quote}}',
                                'missing_sides':'array of unavailable roles, at least one','reason':'limited to this aspect and provided context'},
            'rules':'Do not write free message_id/msg_id/ID numbers in answer/aspect/analysis/reason/quotes; typed metadata is rendered from snapshots. '
                    'Do not invent missing evidence: use insufficient_row with zero or one cited side. '
                    'Every typed side quote must also appear in quotes and its chunk in sources. '
                    'Each participant attribution needs a separate exact quote from that same message_id member, not merely the same chunk. '
                    'A quote from participant B cannot cite participant A even when chunk_id is identical. '
                    'Use participant_citation_examples as paired attribution/source/quote examples; copy only actually used pairs. '
                    'Before returning, omit unused attributions or supply their own short member-bound quotes; never invent a quote. '
                    'Comparison evidence may come from different days; obey explicit current period/scope. '
                    'Keep answer concise; use at most 2 comparison aspects and short exact excerpts (prefer <=120 characters). '
                    'Do not duplicate typed sides in attributions; omit attributions unless specifically needed. '
                    'Do not repeat full documents in quotes; sources/quotes only cover actually used evidence. '
                    'Structure and exact quotes do not prove semantic analysis; semantic_review remains NOT_PROVEN.'}
    if not required:
        contract.pop('comparison_row');contract.pop('insufficient_row')
        contract['rules']+=' For ordinary or assignment-only comparison, omit comparison and compare briefly in answer; discussion role is exclusively a discussion source.'
    return contract
