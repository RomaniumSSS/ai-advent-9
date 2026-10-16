"""Создать НОВЫЙ offline ledger с наглядными SIMULATED fault-сценариями.

Никаких OpenRouter/gh/network calls. Ни один код из рассматриваемого Git не запускается.
"""
import argparse
import json
from pathlib import Path
from review import GitSnapshot, Runner, Store, dumps
from scenario_support import LocalHistory, Simulated, finding, response, seeded_checks


def evaluate(state):
    state=Path(state)
    if state.exists():raise ValueError('Нужна новая папка --state; существующий ledger не перезаписывается')
    state.mkdir(parents=True)
    history=LocalHistory(state/'inputs');snapshot=history.change()
    generated=seeded_checks(history,snapshot)
    store=Store(state);cases=[]
    def case(name,snap,provider,expected,budget=1):
        ident,new=Runner(store,provider,budget).run(snap)
        row=next(row for row in store.reports() if row['id']==ident)
        actual=row['status']
        assertions=[{'test':'terminal status','expected':expected,'actual':actual,'passed':actual==expected},
                    {'test':'simulation label','expected':True,'actual':provider.name.startswith('SIMULATED '),'passed':provider.name.startswith('SIMULATED ')}]
        before=provider.calls
        retry_id,retried=Runner(Store(state),provider,budget).run(snap)
        assertions.append({'test':'persistent dedupe','expected':False,'actual':retried,'passed':not retried and retry_id==ident and provider.calls==before})
        expected_calls=0 if expected=='budget_blocked' else 1
        assertions.append({'test':'single/no call','expected':expected_calls,'actual':provider.calls,'passed':provider.calls==expected_calls})
        cases.append(dict(name=name,trace_id=ident,provider=provider.name,expected=expected,actual=actual,
                          passed=all(t['passed'] for t in assertions),tests=assertions))
    case('Неоднозначный timeout',snapshot,Simulated('timeout',error=TimeoutError('SIMULATED timeout: no retry')),'error')
    case('Повреждённый JSON',snapshot,Simulated('malformed JSON',response(content='{not JSON')),'error')
    case('Усечённый ответ',snapshot,Simulated('truncated output',response(finish='length')),'error')
    case('Невидимая строка',snapshot,Simulated('bad line',response([finding(line=999)])),'error')
    case('Поддельный source ID',snapshot,Simulated('bad source',response([finding(source_ids=['invented'])])),'error')
    case('Пустой choices',snapshot,Simulated('empty choices',{'choices':[]}),'error')
    history.write('oversize.py','x'*25000);history.commit('Offline oversized source')
    limited=history.snapshot(number=2)
    case('Слишком большой файл',limited,Simulated('oversized file',response()),'limited')
    case('Нет бюджета даже для резерва',snapshot,Simulated('budget blocked',response()),'budget_blocked',budget=0)
    clean=GitSnapshot.build(history.path,'offline/scenarios',3,limited['head_sha'],limited['head_sha'],scope='docs')
    case('Чистый diff без выдуманных defects',clean,Simulated('safe clean fixture',response()),'complete')
    total=dict(offline=True,quality_evaluation=False,network_calls=0,provider_policy='SIMULATED only',
               state=str(state.resolve()),seeded_properties=generated,cases=cases,
               tests={'scenario_count':len(cases),'assertion_checks':sum(len(c['tests']) for c in cases),
                      'generated_property_checks':generated['generated_checks'],
                      'unittest_command':'uv run --no-sync python day32/test_scenarios.py',
                      'note':'Число unittest методов берётся из фактического отдельного прогона; assertions не считаются методами.'},
               passed=all(c['passed'] for c in cases))
    (state/'scenarios-summary.json').write_text(dumps(total)+'\n')
    if not total['passed']:raise AssertionError('SIMULATED scenario mismatch; see scenarios-summary.json')
    return total


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',required=True,help='Новая отдельная offline папка')
    args=parser.parse_args();result=evaluate(args.state)
    print(dumps({'offline':True,'quality_evaluation':False,'passed':result['passed'],
                 'scenarios':len(result['cases']),'seed':result['seeded_properties']['seed'],
                 'generated_checks':result['seeded_properties']['generated_checks'],
                 'summary':str(Path(args.state)/'scenarios-summary.json')}))

if __name__=='__main__':main()
