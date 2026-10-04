"""Sequential global-cap accounting; never asks a question or invokes a provider."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from common import save
from privacy import private_output


def validate_profile(profile):
    cap=Decimal(profile['global_cap_usd']);public=Decimal(profile['initial_public_cap_usd'])
    if not cap.is_finite() or not public.is_finite() or not Decimal(0)<public<=cap<=Decimal('.10'):raise ValueError('invalid_global_caps')
    if set(profile['scopes'])!={'public','all'}:raise ValueError('invalid_global_scopes')
    for phase in profile['scopes'].values():
        private_output(phase['data_dir']);private_output(phase['run_dir'])
    return profile


def ledger_charge(directory):
    ledger=json.loads((Path(directory)/'ledger.json').read_text())
    total=Decimal(0)
    for entry in ledger['entries']:
        if entry.get('status')!='completed' or entry.get('cost_unknown'):raise ValueError('ambiguous_spend_stop')
        value=entry.get('charged')
        if type(value) not in (int,float):raise ValueError('invalid_charge')
        charge=Decimal(str(value))
        if not charge.is_finite() or charge<0:raise ValueError('invalid_charge')
        total+=charge
    return total


def no_listener(url):
    parsed=urlsplit(url)
    if parsed.hostname!='127.0.0.1' or parsed.port in (None,8050):raise ValueError('dedicated_loopback_required')
    with socket.socket() as connection:
        connection.settimeout(.5)
        if connection.connect_ex(('127.0.0.1',parsed.port))==0:raise ValueError('previous_paid_server_must_be_stopped')


def balance(profile):
    validate_profile(profile)
    public=ledger_charge(profile['scopes']['public']['data_dir'])
    all_charge=ledger_charge(profile['scopes']['all']['data_dir'])
    if profile.get('public_final_charge') is not None and public!=Decimal(profile['public_final_charge']):raise ValueError('public_charge_changed')
    remaining=Decimal(profile['global_cap_usd'])-public-all_charge
    if remaining<0:raise ValueError('global_budget_exceeded')
    return {'public_charge_usd':str(public),'all_charge_usd':str(all_charge),'remaining_global_usd':str(remaining)}


def completed_phase(profile,scope):
    phase=profile['scopes'][scope]
    run=json.loads((private_output(phase['run_dir'])/'run.json').read_text())
    if run.get('current_action') is not None or sum(bool(r.get('generation_started')) for r in run['results'])>15:raise ValueError('ambiguous_phase_stop')
    if run['status']!='MECHANICAL_RUN_COMPLETE' or len(run['results'])!=15 or any(r['scope']!=scope for r in run['results']):raise ValueError('scope_phase_not_complete')
    if run['scenario_sha256']!=profile['scenario_sha256']:raise ValueError('scenario_mismatch')
    return run


def activate_public(path):
    path=private_output(path);profile=validate_profile(json.loads(path.read_text()))
    if profile['phase']!='PLANNED' or profile.get('approved') is not True:raise ValueError('global_user_approval_required')
    if any(json.loads((Path(p['data_dir'])/'ledger.json').read_text())['entries'] for p in profile['scopes'].values()):raise ValueError('fresh_ledgers_required')
    other=profile['scopes']['all'];no_listener(other['url'])
    auth_path=private_output(profile['scopes']['public']['data_dir'])/'authorization.json';auth=json.loads(auth_path.read_text())
    auth.update(approved=True,approval_status='USER_GRANTED',budget=float(Decimal(profile['initial_public_cap_usd'])))
    save(auth_path,auth);profile['phase']='PUBLIC_ACTIVE';save(path,profile)


def activate_all(path):
    path=private_output(path);profile=validate_profile(json.loads(path.read_text()))
    if profile['phase']!='PUBLIC_ACTIVE' or profile.get('approved') is not True:raise ValueError('invalid_global_phase')
    public=profile['scopes']['public'];no_listener(public['url']);completed_phase(profile,'public')
    current=balance(profile)
    if json.loads((Path(profile['scopes']['all']['data_dir'])/'ledger.json').read_text())['entries']:raise ValueError('fresh_all_ledger_required')
    remaining=Decimal(current['remaining_global_usd'])
    if remaining<Decimal('.0676032'):raise ValueError('insufficient_all_phase_worst_reserve_stop')
    public_auth=Path(public['data_dir'])/'authorization.json';auth=json.loads(public_auth.read_text());auth.update(approved=False,approval_status='REVOKED_AFTER_PUBLIC_PHASE');save(public_auth,auth)
    all_path=private_output(profile['scopes']['all']['data_dir'])/'authorization.json';auth=json.loads(all_path.read_text())
    auth.update(approved=True,approval_status='USER_GRANTED_REMAINING_GLOBAL_CAP',budget=float(remaining));save(all_path,auth)
    profile.update(phase='ALL_ACTIVE',public_final_charge=current['public_charge_usd'],all_total_cap_usd=str(remaining),public_ledger_sha256=hashlib.sha256((Path(public['data_dir'])/'ledger.json').read_bytes()).hexdigest());save(path,profile)
    return current


def manual_ready(path):
    path=private_output(path);profile=validate_profile(json.loads(path.read_text()))
    if profile['phase']!='ALL_ACTIVE':raise ValueError('invalid_global_phase')
    no_listener(profile['scopes']['all']['url']);completed_phase(profile,'all')
    current=balance(profile)
    public=profile['scopes']['public'];auth=json.loads((Path(public['data_dir'])/'authorization.json').read_text())
    if auth.get('approved'):raise ValueError('public_authorization_must_stay_revoked')
    if hashlib.sha256((Path(public['data_dir'])/'ledger.json').read_bytes()).hexdigest()!=profile['public_ledger_sha256']:raise ValueError('public_ledger_changed')
    all_dir=Path(profile['scopes']['all']['data_dir']);auth=json.loads((all_dir/'authorization.json').read_text())
    if Decimal(str(auth['budget']))!=Decimal(profile['all_total_cap_usd']):raise ValueError('all_cap_changed')
    from service import Service
    chat=Service(all_dir).create_chat('Мой чат','all')
    profile.update(phase='MANUAL_READY',manual_chat_id=chat['chat_id'],manual_remaining_usd=current['remaining_global_usd']);save(path,profile)
    return current


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['balance','activate-public','activate-all','manual-ready']);parser.add_argument('profile')
    args=parser.parse_args()
    if args.action=='balance':result=balance(json.loads(private_output(args.profile).read_text()))
    else:result={'activate-public':activate_public,'activate-all':activate_all,'manual-ready':manual_ready}[args.action](args.profile)
    print(json.dumps(result or {'status':'DONE'}))
