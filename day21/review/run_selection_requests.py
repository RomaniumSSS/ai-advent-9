"""Immutable v2 proposals: dry default; pilot/full require separate review gate."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import time
import requests
import certifi
import prepare_selection_requests as prep
from run_openrouter_sample import api_key, ENDPOINT
from run_local_sample import write

VERSION = 1
CAP = 9.0
EXPECTED = '9d70a53c5847793a0a4eb5ed8773c7d337dd03ac1c5f2a6300892e01d98b3b7b'
ROOT = prep.PRIVATE / 'selection-run-v1'


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def reserve(spec):
    return (spec['input_token_conservative_bound'] * .20 + spec['output_token_cap'] * .60) / 1e6


def pilot_ids(rows):
    # The canonical packet manifest supplies exact branch membership, avoiding ID heuristics.
    packets = [json.loads(s) for s in (prep.PRIVATE/'selection-packets-v1/packets.jsonl').read_text().splitlines()]
    byid = {r['case_id']: r for r in rows}; grouped = {}
    for packet in packets:
        if packet['part_count'] > 1 and packet['packet_id'] in byid:
            grouped.setdefault(packet['branch_root_id'], []).append(byid[packet['packet_id']])
    chosen = []
    def add(row):
        if row['case_id'] not in chosen: chosen.append(row['case_id'])
    sizes={p['packet_id']:p['owned_payload_bytes'] for p in packets}
    for group in sorted(grouped.values(), key=lambda g: (-sum(sizes[r['case_id']] for r in g), g[0]['case_id']))[:2]:
        for row in group: add(row)
    unsplit = [r for r in rows if json.loads(r['body']['messages'][1]['content'])['case']['transport_part_count'] == 1]
    add(max(unsplit, key=lambda r:(r['full_utf8_bytes'],r['case_id'])))
    for category in ['media', 'reply', 'singleton']:
        candidates = []
        for row in unsplit:
            p = json.loads(row['body']['messages'][1]['content'])
            match = (any(m['attachment_presence'] is True for m in p['context_messages']) if category == 'media' else
                     any(m['reply_to'] is not None for m in p['owned_messages']) if category == 'reply' else len(row['owned_ids']) == 1)
            if match: candidates.append(row)
        for row in sorted(candidates,key=lambda r:r['case_id'])[:3]: add(row)
    for row in sorted(unsplit,key=lambda r:r['case_id']):
        if len(chosen) >= 12: break
        add(row)
    return chosen


def load():
    source = prep.PRIVATE/'selection-requests-v2'; manifest = strict_json((source/'manifest.json').read_text())
    if prep.file_hash(source/'manifest.json') != EXPECTED: raise ValueError('request_manifest_changed')
    if strict_json((source/'identity.json').read_text()) != manifest['identity']: raise ValueError('identity_changed')
    if prep.file_hash(source/'requests.jsonl') != manifest['artifacts']['requests.jsonl']: raise ValueError('requests_changed')
    original, messages, packets = prep.load_packets(prep.PRIVATE/'selection-packets-v1')
    parser_path=Path(__file__).resolve().parents[2].parent/'day21-sol-high/day21/corpus.py'
    if prep.file_hash(parser_path)!=original['identity']['parser_sha256']: raise ValueError('parser_changed')
    for path, sha in original['identity']['accepted_guard_sha256'].items():
        if prep.file_hash(Path(path)) != sha: raise ValueError('accepted_changed')
    rubric = (prep.RUBRIC.parent/'semantic-rubric-v3.txt').read_text()
    dispositions, rows = prep.generate(messages, packets, rubric)
    saved = [strict_json(s) for s in (source/'requests.jsonl').read_text().splitlines()]
    if saved != rows or dispositions != manifest['dispositions']: raise ValueError('source_ownership_body_mismatch')
    return rows


def schema_check(value, schema):
    try:
        import jsonschema
    except ImportError:
        # Exact subset used by this pinned schema; never silently skip strict validation.
        types = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool}
        if 'type' in schema and type(value) is not types[schema['type']]: raise ValueError('schema_type')
        if 'enum' in schema and value not in schema['enum']: raise ValueError('schema_enum')
        if isinstance(value, dict):
            properties = schema.get('properties', {})
            if any(k not in value for k in schema.get('required', [])): raise ValueError('schema_required')
            if schema.get('additionalProperties') is False and set(value)-set(properties): raise ValueError('schema_extra')
            for key, item in value.items():
                if key in properties: schema_check(item,properties[key])
        if isinstance(value, list):
            if len(value) < schema.get('minItems',0): raise ValueError('schema_array_min')
            if len(value) > schema.get('maxItems', math.inf): raise ValueError('schema_array_size')
            for item in value: schema_check(item,schema.get('items',{}))
        if isinstance(value,str) and len(value)<schema.get('minLength',0): raise ValueError('schema_string_min')
        if isinstance(value,str) and len(value)>schema.get('maxLength',math.inf): raise ValueError('schema_string_size')
    else: jsonschema.validate(value,schema)


def context_guard(spec, output):
    payload = strict_json(spec['body']['messages'][1]['content'])
    records = {m['id']:m for m in payload['owned_messages']+payload['context_messages']}
    errors=[]
    for ident, decision in output['decisions'].items():
        if decision['decision'] != 'include': continue
        parent = records.get(records[int(ident)]['reply_to'])
        if parent and parent['attachment_presence'] is True and parent['content_read'] is False:
            linked = any(int(ident) in g['message_ids'] and parent['id'] in g['context_ids'] for g in output['document_groups'])
            if not linked or 'incomplete_context' not in decision['flags']: errors.append('included_reply_unread_parent:'+ident)
    return errors


def process(spec, raw):
    if raw.get('http_status') != 200: raise ValueError('http_error')
    envelope = strict_json(raw['response_text'])
    if envelope.get('model') != prep.MODEL or envelope.get('provider','').casefold() != 'deepinfra': raise ValueError('provider_model_mismatch')
    choice = envelope['choices'][0]
    if choice['finish_reason'] != 'stop': raise ValueError('incomplete_finish')
    output = strict_json(choice['message']['content'])
    schema_check(output,spec['body']['response_format']['json_schema']['schema'])
    errors=prep.validate_selection_output(spec,output)+context_guard(spec,output)
    if errors: raise ValueError('output_validation')
    return output


def bound(ledger):
    return sum(a['actual_cost'] if a.get('actual_cost') is not None else a['reserve'] for a in ledger['attempts'])


def reconcile(ledger, byid, only=None):
    seen=set()
    for attempt in ledger['attempts']:
        ident=attempt['case_id']
        if ident in seen or ident not in byid or attempt['reserve'] != reserve(byid[ident]): raise ValueError('ledger_consistency')
        if attempt.get('status') not in ['pending','complete','error']: raise ValueError('ledger_status')
        cost=attempt.get('actual_cost')
        if cost is not None and (type(cost) not in (int,float) or not math.isfinite(cost) or cost<0): raise ValueError('ledger_cost')
        seen.add(ident)
        if only is not None and ident != only: continue
        path=ROOT/(ident+'.json')
        if not path.exists():
            if attempt['status'] != 'pending': raise ValueError('missing_result')
            ledger['stop_reason']='pending_without_response'; continue
        if attempt.get('status') not in ['pending','complete','error']: raise ValueError('ledger_status')
        raw=strict_json(path.read_text())
        if raw['body_sha256'] != byid[ident]['body_sha256']: raise ValueError('result_identity')
        try:
            envelope=strict_json(raw['response_text']); cost=envelope.get('usage',{}).get('cost')
        except (ValueError,TypeError): cost=None
        if cost is not None and (type(cost) not in (int,float) or not math.isfinite(cost) or cost<0): cost=None
        attempt['actual_cost']=cost
        try:
            output=process(byid[ident],raw); attempt['status']='complete'
            if cost is not None and cost>attempt['reserve']: raise ValueError('actual_over_reserve')
        except Exception as error:
            attempt['status']='error';ledger['stop_reason']=str(error) if isinstance(error,ValueError) else type(error).__name__
    if bound(ledger)>CAP: raise ValueError('budget_exceeded')
    return seen


def send(spec, key):
    return requests.post(ENDPOINT, data=prep.encoded(spec['body']),
                         headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
                         timeout=180, verify=certifi.where())


def main():
    os.umask(0o077)
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--phase',choices=['pilot','full'],default='pilot');cli.add_argument('--live',action='store_true');cli.add_argument('--approval',type=Path)
    args=cli.parse_args();rows=load();byid={r['case_id']:r for r in rows};pilot=pilot_ids(rows)
    meta={'version':VERSION,'manifest_sha256':EXPECTED,'runner_sha256':prep.file_hash(Path(__file__)),'cap':CAP,'pilot_ids':pilot}
    jobs=[byid[i] for i in pilot] if args.phase=='pilot' else rows
    if ROOT.is_symlink(): raise ValueError('symlink_run')
    ROOT.mkdir(mode=0o700,exist_ok=True);ROOT.chmod(0o700)
    if any(p.is_symlink() for p in ROOT.iterdir()): raise ValueError('symlink_artifact')
    with (ROOT/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=ROOT/'ledger.json';ledger=strict_json(path.read_text()) if path.exists() else {'meta':meta,'attempts':[]}
        if ledger['meta'] != meta: raise ValueError('ledger_metadata')
        seen=reconcile(ledger,byid)
        if args.phase=='full':
            if not args.approval: raise ValueError('full_requires_review_approval')
            approval=strict_json(args.approval.read_text())
            evidence=prep.digest({i:prep.file_hash(ROOT/(i+'.json')) for i in pilot})
            if approval != {'approved':True,'request_manifest_sha256':EXPECTED,'pilot_evidence_sha256':evidence}: raise ValueError('approval_mismatch')
            if not all(any(a['case_id']==i and a['status']=='complete' for a in ledger['attempts']) for i in pilot): raise ValueError('pilot_not_complete')
        remaining=[r for r in jobs if r['case_id'] not in seen]
        print(json.dumps({'phase':args.phase,'calls':len(remaining),'reserve_upper':sum(reserve(r) for r in remaining),'spent_bound':bound(ledger),'cap':CAP,'stop_reason':ledger.get('stop_reason'),'live':args.live}),flush=True)
        if not args.live:return
        write(path,ledger)
        if ledger.get('stop_reason'):raise ValueError('stopped_requires_review')
        key=api_key()
        for spec in remaining:
            upper=reserve(spec)
            if bound(ledger)+upper>CAP:raise ValueError('budget_cap')
            ledger['attempts'].append({'case_id':spec['case_id'],'reserve':upper,'actual_cost':None,'status':'pending','phase':args.phase});write(path,ledger)
            start=time.monotonic();raw={'body_sha256':spec['body_sha256']}
            try:
                response=send(spec,key)
                raw.update(http_status=response.status_code,response_text=response.text,retry_after=response.headers.get('Retry-After'))
            except requests.RequestException as error:raw.update(http_status=None,response_text='',transport_error=type(error).__name__)
            raw['elapsed_seconds']=time.monotonic()-start
            write(ROOT/(spec['case_id']+'.json'),raw)
            reconcile(ledger,byid,only=spec['case_id']);write(path,ledger)
            print(json.dumps({'completed':len(ledger['attempts']),'spent_bound':bound(ledger),'stop_reason':ledger.get('stop_reason')}),flush=True)
            if ledger.get('stop_reason'):break

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'error_type':type(error).__name__}),flush=True);raise SystemExit(1)
