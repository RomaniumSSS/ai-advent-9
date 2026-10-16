"""Общий обработчик CLI/UI: поиск → MCP → не более одного вызова модели."""
from __future__ import annotations
import json
import re
import threading
import time
import uuid
from jsonschema import Draft202012Validator
from day31.contracts import Answer
from day31.provider import ANSWER_SCHEMA, ProviderError


class Assistant:
    def __init__(self, index, mcp, provider):
        self.index = index
        self.mcp = mcp
        self.provider = provider
        self._lock = threading.Lock()

    def answer(self, question: str) -> Answer:
        with self._lock:
            return self._answer(question)

    def _answer(self, question):
        started = time.monotonic()
        result = Answer('error','',[],None,uuid.uuid4().hex,model=self.provider.model,provider=self.provider.provider)
        def done():
            result.elapsed_seconds = round(time.monotonic()-started,4)
            return result
        if not isinstance(question,str):
            result.text = 'Вопрос должен быть строкой'
            return done()
        question = question.strip()
        if question == '/help' or question.startswith('/help '):
            question = question[5:].strip()
        if not question or len(question) > 4000:
            result.text = 'Введите /help и вопрос длиной до 4000 символов'
            return done()
        phase = 'search'
        phase_start = time.monotonic()
        try:
            chunks = self.index.search(question)
            result.sources = [chunk.to_dict() for chunk in chunks]
            result.stages.append({'name':'search','status':'ok','seconds':round(time.monotonic()-phase_start,4),'count':len(chunks),'source_ids':[c.id for c in chunks]})
            phase = 'mcp'; phase_start = time.monotonic()
            result.git_context = self.mcp.read()
            result.stages.append({'name':'mcp','status':'ok','seconds':round(time.monotonic()-phase_start,4),'tool':'git_context','arguments':{},'discovery':self.mcp.last_discovery,'result':result.git_context})
            if not chunks:
                result.status = 'unknown'
                result.text = 'В README/docs не найдено данных по этому вопросу. Уточните вопрос о Git MCP или запуске проекта.'
                result.stages.append({'name':'model','status':'skipped','reason':'Пустая выдача поиска: контекста для ответа нет'})
                return done()
            phase = 'model'; phase_start = time.monotonic()
            generated = self.provider.generate(question,result.sources,result.git_context,result.trace_id)
            result.usage = generated.usage
            value = json.loads(generated.content)
            Draft202012Validator(ANSWER_SCHEMA).validate(value)
            if not value['text'].strip():
                raise ValueError('Пустой ответ')
            available = {c.id for c in chunks}
            declared = value['source_ids']
            inline = list(dict.fromkeys(re.findall(r'\[([0-9a-f]{20})\]',value['text'])))
            if not set(declared) <= available or not set(inline) <= available:
                raise ValueError('Ответ ссылается на отсутствующий источник')
            # AICODE-NOTE: валидная inline-ссылка могла отсутствовать в массиве API;
            # нормализуем метаданные после проверки всех ID, не генерируя новый текст.
            added = [source_id for source_id in inline if source_id not in declared]
            value['source_ids'] = list(dict.fromkeys([*declared,*added]))
            Draft202012Validator(ANSWER_SCHEMA).validate(value)
            if value['status']=='ok' and not value['source_ids']:
                raise ValueError('Ответ не содержит обязательной ссылки')
            result.status = value['status']
            result.text = value['text']
            result.source_ids = value['source_ids']
            result.stages.append({'name':'model','status':'ok','seconds':round(time.monotonic()-phase_start,4),'model':self.provider.model,'provider':self.provider.provider,'usage':result.usage,'receipt':generated.receipt,'source_id_normalization':{'method':'deterministic','added_from_inline':added},'validation':'JSON и source_ids проверены; смысловая верность отдельно'})
        except Exception as error:
            if isinstance(error,ProviderError):
                result.usage = error.usage
                result.text = str(error)
            else:
                result.text = {'search':'Ошибка чтения индекса документов','mcp':'Ошибка MCP: Git-контекст недоступен','model':'Ошибка модели: некорректный JSON или ссылки на источники'}.get(phase,'Ошибка запроса')
            result.status = 'error'
            result.source_ids = []
            result.stages.append({'name':phase,'status':'error','seconds':round(time.monotonic()-phase_start,4),'message':result.text})
        return done()
