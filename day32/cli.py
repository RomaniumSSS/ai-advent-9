"""Команды локального reviewer; публикации и исполнения PR нет."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from review import Fixture, GitSnapshot, OpenRouter, Runner, Store, dumps, git

ROOT=Path(__file__).resolve().parent


def fixture(root):
    repo=Path(root)/'fixture-repo'
    if repo.exists():
        meta=json.loads((Path(root)/'fixture.json').read_text()); return repo,meta
    repo.mkdir(parents=True)
    shutil.copytree(ROOT/'target',repo,dirs_exist_ok=True)
    def command(*args):
        subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
    command('init','-q'); command('config','user.email','fixture@localhost'); command('config','user.name','Offline fixture')
    command('add','.'); command('commit','-qm','Fixture baseline')
    base=git(repo,'rev-parse','HEAD').decode().strip()
    path=repo/'git_tool.py'; path.write_text(path.read_text().replace('limit <= 10:', 'limit < 10:'))
    command('add','.'); command('commit','-qm','Fixture regression')
    head=git(repo,'rev-parse','HEAD').decode().strip()
    meta=dict(base=base,head=head); (Path(root)/'fixture.json').write_text(dumps(meta))
    return repo,meta


def gh(*args):
    p=subprocess.run(['gh',*args],check=True,capture_output=True,text=True,timeout=40)
    if len(p.stdout)>200000: raise ValueError('GitHub response too large')
    return json.loads(p.stdout)


def poll(repository,cache):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository): raise ValueError('Некорректный owner/repository')
    prs=gh('pr','list','--repo',repository,'--state','open','--limit','20','--json','number,baseRefOid,headRefOid')
    cache=Path(cache)
    if not cache.exists():
        subprocess.run(['git','init','--bare',str(cache)],check=True,capture_output=True)
    for pr in prs:
        # AICODE-NOTE: только фиксированный GitHub URL, не clone URL из недоверенного PR.
        subprocess.run(['git','-C',str(cache),'fetch','--no-tags',
                        'https://github.com/'+repository+'.git',pr['baseRefOid'],
                        'refs/pull/'+str(int(pr['number']))+'/head'],check=True,capture_output=True,timeout=120)
        yield GitSnapshot.build(cache,repository,pr['number'],pr['baseRefOid'],pr['headRefOid'],scope='day32/target')


def main():
    p=argparse.ArgumentParser(description='Day32: локальное ревью PR; fixture не является live-доказательством')
    p.add_argument('command',choices=['fixture','local','watch','serve'])
    p.add_argument('--state',default=str(ROOT/'.runtime'))
    p.add_argument('--mode',choices=['diff','files','rag'],default='rag')
    p.add_argument('--repo'); p.add_argument('--base'); p.add_argument('--head'); p.add_argument('--scope',default='')
    p.add_argument('--number',type=int,default=1); p.add_argument('--live',action='store_true')
    p.add_argument('--budget',type=float); p.add_argument('--interval',type=int,default=30); p.add_argument('--once',action='store_true')
    args=p.parse_args()
    if args.command=='serve':
        from web import serve
        serve(args.state); return
    if args.live and (args.budget is None or not 0 < args.budget < 100): p.error('--live требует явный положительный --budget меньше $100')
    if args.command=='watch' and (not args.live or not args.repo): p.error('watch требует --repo owner/repo --live --budget; платные вызовы требуют разрешения пользователя')
    store=Store(args.state); provider=OpenRouter(True) if args.live else Fixture(); runner=Runner(store,provider,args.budget)
    if args.command=='fixture':
        if args.live: p.error('fixture всегда offline; --live запрещён')
        repo,meta=fixture(args.state); snapshots=[GitSnapshot.build(repo,'offline/fixture',1,meta['base'],meta['head'])]
    elif args.command=='local':
        if not all((args.repo,args.base,args.head)): p.error('local требует --repo PATH --base SHA --head SHA')
        snapshots=[GitSnapshot.build(args.repo,str(Path(args.repo).resolve()),args.number,args.base,args.head,args.scope)]
    else:
        snapshots=None
    while True:
        try:
            for snap in (poll(args.repo,Path(args.state)/'github-cache.git') if snapshots is None else snapshots):
                ident,created=runner.run(snap,'rag' if args.command=='watch' else args.mode)
                print(dumps(dict(trace_id=ident,new=created,provider=provider.name)),flush=True)
        except Exception as exc:
            # Ошибка polling не оплачивает запрос; уже claimed model snapshots повторяться не будут.
            print(dumps({'poll_error':type(exc).__name__+': '+str(exc)[:500]}),flush=True)
            if args.once or snapshots is not None: raise
        if snapshots is not None or args.once: break
        time.sleep(max(args.interval,10))

if __name__=='__main__': main()
