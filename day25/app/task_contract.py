"""Explicit format checks; free-form task meaning remains a semantic review."""
import re

NUMBERS={'одного':1,'двух':2,'трёх':3,'трех':3,'четырёх':4,'четырех':4,'пяти':5}


def sentence_limit(state):
    limits=[]
    for text in state.get('constraints',[]):
        match=re.search(r'не более\s+(\d+|одного|двух|трёх|трех|четырёх|четырех|пяти)\s+предложени',text,re.I)
        if match:limits.append(int(match[1]) if match[1].isdigit() else NUMBERS[match[1].lower()])
    return min(limits) if limits else None


def refusal_text(answer):
    if not isinstance(answer,dict) or answer.get('sources')!=[] or answer.get('quotes')!=[] or not isinstance(answer.get('answer'),str):return ''
    text=re.sub(r'^\s*(?:\d+[.)]|[-*•])\s+','',answer['answer'],count=1)
    return text if text.startswith('Не знаю:') and 'уточн' in text.lower() else ''


def point_limit(state):
    limits=[]
    for text in state.get('constraints',[]):
        match=re.search(r'не более\s+(\d+|одного|двух|трёх|трех|четырёх|четырех|пяти)\s+пункт',text,re.I)
        if match:limits.append(int(match[1]) if match[1].isdigit() else NUMBERS[match[1].lower()])
    return min(limits) if limits else None


def sentence_count(text):
    # AICODE-NOTE: numbered list markers and decimal dots are not sentence boundaries.
    text=re.sub(r'^\s*\d+[.)]\s+','',text,flags=re.M).strip()
    parts=re.split(r'[.!?]+["»”)]*(?:\s+|$)',text)
    return sum(bool(part.strip()) for part in parts)


def format_errors(answer,state):
    limit=sentence_limit(state)
    if limit is not None and isinstance(answer,dict) and isinstance(answer.get('answer'),str):
        if sentence_count(answer['answer'])>limit:return ['task_sentence_limit_exceeded']
    points=point_limit(state)
    if points is not None and isinstance(answer,dict) and isinstance(answer.get('answer'),str):
        if answer['answer'].startswith('Не знаю:') and answer.get('sources')==[] and answer.get('quotes')==[]:return []
        lines=[line.strip() for line in answer['answer'].splitlines() if line.strip()]
        if not lines or any(not re.match(r'^(?:\d+[.)]|[-*•])\s+',line) for line in lines):return ['task_points_require_explicit_list']
        if len(lines)>points:return ['task_point_limit_exceeded']
    return []


def answer_requirements(question,state):
    limit=sentence_limit(state)
    points=point_limit(state)
    format_guidance=(f' Ответ answer должен содержать не более {limit} предложений; '
                     'источники и quotes находятся в отдельных JSON полях, не добавляй сверх лимита '
                     'предложения для цитат или пояснений.') if limit is not None else ''
    if points is not None:format_guidance+=f' В answer используй явно нумерованный список: не более {points} пунктов, каждый на отдельной строке; объединяй связанные этапы, без отдельного вступления. Для отказа без источников ответ начинается «Не знаю: ...» и предлагает уточнение; допустима одна строка либо список с первым пунктом «1. Не знаю: ...». Не прячь эту метку в последнем пункте.'
    comparison=bool(re.search(r'\b(?:сравн(?:и(?:те|ть)?|ени[еяюий]|ений|ениями)|сопостав(?:ь(?:те)?|ить|им|ьте|лени[еяюий]|лений|лениями))\b|\bчем\b.*\bотлич',question,re.I))
    comparison_guidance=('Сравнение выполняешь ты по переданным материалам: выдели сопоставимые аспекты '
                         'требований и позиций участников, покажи подтверждённые совпадения и различия с источниками. '
                         'Не требуй, чтобы обсуждение содержало готовое сравнение или буквальное упоминание номера '
                         'дня задания. Материалы соседнего этапа курса могут относиться к тому же аспекту; связь '
                         'обоснуй содержанием, не угадывай. Если доказательств нет для отдельного аспекта, явно '
                         'ограничь вывод этим аспектом, а не отказывайся от всего сравнения. Явное ограничение '
                         'периода или области обсуждений в текущем вопросе сохраняет приоритет.') if comparison else ''
    # Требование 1-3 спеки: вопрос об исполнении цели при непустой state['goal'] получает отдельное
    # требование конкретных действий пользователя, и флаг, по которому это можно утверждать отдельно от текста.
    goal_execution_requested=bool(state.get('goal')) and bool(re.search(r'действи[ея]|шаг(?:и|ов|ам)?|план\b|с чего.*начать|что мне делать|что дальше',question,re.I))
    goal_execution_guidance=(' Вопрос об исполнении цели: опиши конкретные действия пользователя для текущей '
                             'task_state.goal, опираясь на зафиксированные clarifications и constraints; требования '
                             'корпуса допустимы только как обоснование шага, не как сам ответ; не пересказывай условия '
                             'задания вместо шагов пользователя.') if goal_execution_requested else ''
    return {'max_sentences':limit,'max_points':points,
            'comparison_requested':comparison, 'comparison_guidance':comparison_guidance,
            'goal_execution_requested':goal_execution_requested,
            'selected_user_choices':[text for text in state.get('clarifications',[])
                                     if re.search(r'\b(?:выбрал|выбрала|выбрали|выбран|выбрана)\b',text,re.I)],
            'requested_tool_return':bool(re.search(r'ответ\w*\s+пользовател|возвращ\w*\s+результат|что.*возвращ',question,re.I)),
            'guidance':('В итоге для текущей цели используй выбранное пользователем решение, а не список альтернатив; '
                        'обязательное требование корпуса отдели от выбранного примера. Если запрошен ответ пользователю, '
                        'опиши возвращаемый инструментом результат по контексту, а не готового агента или формат сдачи. '
                        'Разделяй сохраняемые входные данные, возвращаемый пользователю результат и итог проекта; '
                        'не называй готовый агент сохранёнными данными без прямого подтверждения источником. '
                        'Если указательное «это» допускает несколько ближайших значений, явно уточни значение или дай условные варианты; не выбирай старую тему молча.'
                        + format_guidance + goal_execution_guidance)}
