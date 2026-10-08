"""Offline design prototype; not imported by the application or generator."""
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
            'source':chunk['source'],'chunk_id':chunk['chunk_id'],'date':part.get('date')}
