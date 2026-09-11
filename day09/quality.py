"""Лексическая сверка заранее заданных фактов; семантическое ревью — отдельно.

Совпадение слова не доказывает правильность утверждения. Контрольные ответы
сохраняются целиком для проверки отрицаний, добавленных условий и источников.
"""
import json
import re
from pathlib import Path
ROOT=Path(__file__).parent/'results'/'final'

def checks(scenario,text,turn):
    t=text.casefold().replace('*','')
    has=lambda pattern:bool(re.search(pattern,t))
    if scenario=='project':
        result={'название Маяк':has('маяк'),'бюджет 1200 евро':has(r'1[\s,]?200') and has(r'евро|€|\beur\b'),
                'срок 25 октября':has(r'25\s*(?:октябр|[./]10)'),
                'русский и польский':has('русск') and has('польск'),
                'онлайн-оплата исключена (требует проверки отрицания)':has(r'онлайн.{0,2}оплат')}
        if turn==16:
            # Финальный вопрос просит ограничения и отменённый срок, не название.
            result.pop('название Маяк')
            result['старый срок 18 октября назван']=has(r'18\s*(?:октябр|[./]10)')
    else:
        result={'имя Роман':has('роман'),'город Вроцлав':has('вроцлав'),'чай':has('чай'),
                'без мяса':has(r'не.{0,15}мяс|без\s+мяс|вегетариан'),
                'суббота 11:00':has('суббот') and has(r'11[:.]00|11\s*час')}
        if turn==16:
            # Здесь спрашивают предпочтения и планы, а не имя и город.
            result.pop('имя Роман');result.pop('город Вроцлав')
            result['отменены воскресенье и 10:00']=has('воскрес') and has(r'10[:.]00|10\s*час')
    return result

def main():
    records=json.loads((ROOT/'control-answers.json').read_text())
    results=[]
    for row in records:
        found=checks(row['scenario'],row['answer'],row['turn'])
        results.append({k:row[k] for k in ('scenario','repeat','turn','side')}|
                       {'checks':found,'passed':sum(found.values()),'total':len(found)})
    output={'method':'лексическая сверка, не семантический судья и не человеческая приёмка',
            'passed':sum(r['passed'] for r in results),'total':sum(r['total'] for r in results),'answers':results}
    (ROOT/'quality-lexical.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print('Лексическая сверка:',output['passed'],'/',output['total'])
    for r in results:
        if r['passed']<r['total']:print(r)
if __name__=='__main__':main()
