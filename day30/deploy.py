"""Отдельный launchd Day30: подготовка plist не запускает/не меняет сервисы."""
from limits import LAUNCHD_EXIT_TIMEOUT_SECONDS
import argparse
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time
from server import HERE,load_env

def prepare(env_path,label,python,scope=None):
    if not re.fullmatch(r'org\.ai-advent\.day30(?:\.[a-z0-9-]+)?',label):raise ValueError('day30_label_required')
    env_path=Path(env_path).resolve();env=load_env(env_path);private=Path(env['DAY30_PRIVATE']).resolve()
    private.mkdir(parents=True,exist_ok=True,mode=0o700);private.chmod(0o700)
    for name in ('stdout.log','stderr.log'):
        fd=os.open(private/name,os.O_WRONLY|os.O_CREAT,0o600);os.close(fd);(private/name).chmod(0o600)
    args=[str(Path(python).resolve()),str(HERE/'server.py'),'--env',str(env_path)]
    if scope:args+=['--scope',scope]
    plist={'Label':label,'ProgramArguments':args,'WorkingDirectory':str(HERE.parent),
           'RunAtLoad':True,'KeepAlive':{'SuccessfulExit':False},'ThrottleInterval':10,
           'ExitTimeOut':LAUNCHD_EXIT_TIMEOUT_SECONDS,'Umask':0o077,'StandardOutPath':str(private/'stdout.log'),
           'StandardErrorPath':str(private/'stderr.log')}
    path=private/(label+'.plist');fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as out:plistlib.dump(plist,out)
    path.chmod(0o600);return path

def job_state(target,timeout=5):
    result=subprocess.run(['launchctl','print',target],capture_output=True,text=True,timeout=timeout)
    if result.returncode==0:
        match=re.search(r'^\s*pid\s*=\s*(\d+)\s*$',result.stdout,re.M)
        return True,int(match[1]) if match else None
    if 'Could not find service' in result.stderr:return False,None
    raise RuntimeError('day30_launchd_state_unavailable')

def pid_exists(pid):
    if pid is None:return False
    try:os.kill(pid,0)
    except ProcessLookupError:return False
    except PermissionError:return True
    return True

def shutdown_timeout(path):
    with Path(path).open('rb') as source:plist=plistlib.load(source)
    duration=plist.get('ExitTimeOut',LAUNCHD_EXIT_TIMEOUT_SECONDS)
    if type(duration) is not int or duration<1:raise ValueError('invalid_launchd_exit_timeout')
    return duration+5

def stop_job(target,timeout):
    deadline=time.monotonic()+timeout
    def remaining():
        value=deadline-time.monotonic()
        if value<=0:raise TimeoutError('day30_stop_timeout')
        return value
    registered,prior_pid=job_state(target,min(5,remaining()))
    if not registered:raise ValueError('day30_job_not_registered')
    subprocess.run(['launchctl','bootout',target],check=True,timeout=remaining())
    # AICODE-NOTE: bootout вернулся до ухода старого PID/launchd cleanup;
    # немедленный bootstrap давал error5. Оба состояния проверяем до нового start.
    while True:
        registered,_=job_state(target,min(5,remaining()))
        if not registered and not pid_exists(prior_pid):return
        time.sleep(min(.2,remaining()))


def main():
    parser=argparse.ArgumentParser(description='Частный Day30 launchd helper')
    parser.add_argument('command',choices=('prepare','start','stop','restart','status'))
    parser.add_argument('--env',default=str(HERE/'private/.env'));parser.add_argument('--label',default='org.ai-advent.day30')
    parser.add_argument('--python',default=sys.executable);parser.add_argument('--scope',choices=('all','assignment'))
    args=parser.parse_args()
    if not re.fullmatch(r'org\.ai-advent\.day30(?:\.[a-z0-9-]+)?',args.label):raise ValueError('day30_label_required')
    domain=f'gui/{os.getuid()}';target=domain+'/'+args.label
    env=load_env(args.env);path=Path(env['DAY30_PRIVATE']).resolve()/(args.label+'.plist')
    if args.command=='prepare':print(prepare(args.env,args.label,args.python,args.scope));return
    if args.command=='start':
        if not path.is_file():raise ValueError('prepare_plist_first')
        subprocess.run(['launchctl','bootstrap',domain,str(path)],check=True)
    elif args.command=='stop':stop_job(target,shutdown_timeout(path))
    elif args.command=='restart':
        # bootout использует ExitTimeOut; kickstart -k убил бы активную генерацию сразу.
        if not path.is_file():raise ValueError('prepare_plist_first')
        stop_job(target,shutdown_timeout(path))
        subprocess.run(['launchctl','bootstrap',domain,str(path)],check=True)
    else:subprocess.run(['launchctl','print',target],check=True)

if __name__=='__main__':main()
