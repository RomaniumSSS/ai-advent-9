"""Офлайн-данные сценариев; не исполняет код рассматриваемого репозитория."""
import copy
import json
from pathlib import Path
import subprocess
from review import GitSnapshot, git


class LocalHistory:
    def __init__(self, root):
        self.path=Path(root)/'repository';self.path.mkdir(parents=True)
        self.command('init','-q');self.command('config','user.email','scenarios@localhost')
        self.command('config','user.name','Offline scenarios')
        self.write('history.py',''.join(f'value_{i} = {i}\n' for i in range(1,101)))
        self.write('docs/contract.md','history limit recent commits: допустимо от 1 до 10 включительно.\n')
        self.base=self.commit('Offline baseline')
    def command(self,*args):
        return subprocess.run(['git','-C',str(self.path),*args],check=True,capture_output=True).stdout
    def write(self,path,text):
        target=self.path/path;target.parent.mkdir(parents=True,exist_ok=True)
        if isinstance(text,bytes):target.write_bytes(text)
        else:target.write_text(text)
    def commit(self,message):
        self.command('add','-A');self.command('commit','--allow-empty','-qm',message)
        return git(self.path,'rev-parse','HEAD').decode().strip()
    def snapshot(self,number=1,scope=''):
        return GitSnapshot.build(self.path,'offline/scenarios',number,self.base,
                                 git(self.path,'rev-parse','HEAD').decode().strip(),scope)
    def change(self,path='history.py'):
        text=(self.path/path).read_text();self.write(path,text.replace('value_50 = 50','value_50 = 500'))
        self.commit('Offline change');return self.snapshot()


def finding(path='history.py',line=50,version='head',**changes):
    value=dict(category='bug',path=path,version=version,line=line,
               evidence='Проверяемое учебное замечание',suggestion='Проверить контракт',source_ids=[])
    value.update(changes);return value


def response(findings=None,finish='stop',content=None,usage=None):
    return {'choices':[{'finish_reason':finish,'message':{'content':content if content is not None else json.dumps({'findings':findings or []})}}], 'usage':usage}


class Simulated:
    """Имя не маскирует офлайн-ответ под реальную модель."""
    def __init__(self,label,payload=None,error=None):
        self.name='SIMULATED '+label;self.payload=payload;self.error=error;self.calls=0
    def __call__(self,messages):
        self.calls+=1
        if self.error:raise self.error
        return copy.deepcopy(self.payload if self.payload is not None else response())


SEED = 320016


def seeded_checks(history,snapshot,seed=SEED):
    """100 детерминированных invariant checks, а не 100 отдельных тестов."""
    import importlib.util
    import random
    from review import context, validate
    randomizer=random.Random(seed);data=context(snapshot,'diff')[1];checks=0
    for _ in range(40):
        line=randomizer.randint(-10,110)
        expected=47 <= line <= 53
        try:
            validate({'findings':[finding(line=line)]},snapshot,data);actual=True
        except ValueError:actual=False
        if actual != expected:raise AssertionError(('line invariant',seed,line,expected,actual))
        checks+=1
    for _ in range(30):
        field,value=randomizer.choice([
            ('path','../escape.py'),('path','missing.py'),('source_ids',['invented']),
            ('version','other'),('line',True),('line',500),('category','execute')])
        try:validate({'findings':[finding(**{field:value})]},snapshot,data)
        except ValueError:pass
        else:raise AssertionError(('invalid reference accepted',seed,field,value))
        checks+=1
    spec=importlib.util.spec_from_file_location('trusted_scenario_baseline',Path(__file__).parent/'target/git_tool.py')
    baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    for _ in range(30):
        value=randomizer.choice([True,False,None,'10',1.0,-1,0,1,2,9,10,11,100])
        expected=type(value) is int and 1 <= value <= 10
        try:baseline.recent_commits(history.path,value);actual=True
        except ValueError:actual=False
        if actual != expected:raise AssertionError(('boundary invariant',seed,repr(value),expected,actual))
        checks+=1
    return {'seed':seed,'generated_checks':checks,'status':'PASS','groups':{'line_coordinates':40,'invalid_references':30,'target_boundaries':30}}
