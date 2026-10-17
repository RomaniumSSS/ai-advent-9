"""Три новых UI-запроса; JSON/тайминги и опциональная запись viewport."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
from playwright.sync_api import sync_playwright

CASES = [('alice', 'T101', 'FAQ-EMAIL'), ('boris', 'T102', 'FAQ-INVITE'), ('alice', 'T103', None)]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def check_response(data, ticket, source, mode):
    assert data['context']['ticket']['id'] == ticket, 'Ответ относится к другому тикету'
    assert data['trace']['mode'] == mode, 'Режим ответа отличается от выбранного'
    assert data['trace']['run_id'], 'Нет run_id'
    assert data['trace']['mcp'] and data['trace']['retrieval_ids'], 'Нет MCP/RAG evidence'
    text = data['answer'].casefold()
    assert not re.search(r'(пришлите|сообщите|отправьте|введите).{0,25}(ваш\s+)?парол', text), 'Ответ просит пароль'
    if source:
        assert source in data['source_ids'] and f'[{source}]' in data['answer'], 'Нет ожидаемого источника'
        assert data['trace']['response_kind'] == 'model_answer', 'Нет ответа модели'
        if ticket == 'T101':
            assert 'почт' in text and 'подтвер' in text, 'Не показаны причина и подтверждение почты'
        else:
            assert 'приглашен' in text and re.search(r'ист[её]к|истеч|просроч|больше не действует|invitation_expired', text) and 'нов' in text, 'Не показаны истечение и новое приглашение'
    else:
        assert data['trace']['response_kind'] == 'rule_based_clarification', 'Уточнение не rule-based'
        assert data['trace']['model'] is None and data['trace']['provider'] is None, 'Модель вызвана без диагностики'
        assert data['answer'] == 'Уточните точный текст ошибки и этап входа. Причина пока неизвестна. Не передавайте пароль.', 'Изменён безопасный ответ'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8133')
    parser.add_argument('--mode', choices=['mock', 'live'], default='mock')
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--timeout-ms', type=int, default=120000)
    parser.add_argument('--read-seconds', type=float, default=7)
    args = parser.parse_args()
    if args.timeout_ms < 1000 or not 0 <= args.read_seconds <= 60:
        parser.error('Некорректное ожидание')
    output = args.output_dir or Path('/tmp/day33-runs') / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    result = {'mode':args.mode, 'record':args.record, 'status':'running', 'cases':[], 'errors':[], 'response_count':0}
    started = time.monotonic()
    responses = []
    with sync_playwright() as p:
        browser = context = page = video = None
        try:
            browser = p.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(viewport={'width':1280,'height':1000}, **({'record_video_dir':str(output/'raw-video'), 'record_video_size':{'width':1280,'height':1000}} if args.record else {}))
            page = context.new_page()
            video = page.video if args.record else None
            page.set_default_timeout(args.timeout_ms)
            page.on('pageerror', lambda error: result['errors'].append(str(error)))

            def observe(response):
                if response.request.method == 'POST' and response.url == args.url.rstrip('/') + '/api/ask':
                    data = response.json()
                    responses.append({'status':response.status, 'data':data})
                    save(output/f'response-{len(responses):02d}.json', responses[-1])
            page.on('response', observe)
            page.goto(args.url)
            page.wait_for_function('!document.querySelector("#ask").disabled')
            expected_badge = 'MOCK' if args.mode == 'mock' else 'LIVE'
            assert expected_badge in page.locator('#mode').inner_text(), 'Сервер в другом режиме; запросы не отправлены'
            page.screenshot(path=str(output/'00-start.png'))
            page.wait_for_timeout(args.read_seconds*1000)
            seen_runs = set()
            for index, (user, ticket, source) in enumerate(CASES, 1):
                step_start = time.monotonic()
                page.wait_for_function('!document.querySelector("#ask").disabled')
                page.select_option('#user', user)
                page.wait_for_function('(user)=>!document.querySelector("#ask").disabled && document.querySelector("#user").value===user', arg=user)
                page.select_option('#ticket', ticket)
                page.fill('#question', 'Почему не работает авторизация?')
                before = len(responses)
                with page.expect_response(lambda response: response.request.method == 'POST' and response.url == args.url.rstrip('/')+'/api/ask', timeout=args.timeout_ms) as pending:
                    page.click('#ask')
                response = pending.value
                page.wait_for_function('!document.querySelector("#ask").disabled', timeout=args.timeout_ms)
                assert response.status == 200, 'HTTP-запрос неуспешен; JSON сохранён'
                assert len(responses) == before+1, 'Неожиданное число ответов'
                data = responses[-1]['data']
                check_response(data, ticket, source, args.mode)
                run_id = data['trace']['run_id']
                assert run_id not in seen_runs, 'Повторно показан старый run_id'
                seen_runs.add(run_id)
                assert page.locator('#answer').inner_text() == data['answer'], 'UI не показал новый ответ'
                details = page.locator('details').first
                if details.get_attribute('open') is None: details.locator('summary').click()
                page.locator('#answer').scroll_into_view_if_needed()
                page.screenshot(path=str(output/f'{index:02d}-{ticket}-answer.png'))
                page.wait_for_timeout(args.read_seconds*1000)
                page.locator('#context').scroll_into_view_if_needed()
                page.screenshot(path=str(output/f'{index:02d}-{ticket}-context.png'))
                page.wait_for_timeout(args.read_seconds*1000)
                result['cases'].append({'ticket':ticket, 'run_id':run_id, 'elapsed_seconds':round(time.monotonic()-step_start,3), 'request_elapsed_seconds':data['trace']['elapsed_seconds'], 'status':'PASS'})
                save(output/'result.json', result)
            assert len(responses) == 3, 'Должно быть ровно три запроса'
            assert not result['errors'], 'Ошибка JavaScript'
            page.screenshot(path=str(output/'99-end.png'))
            result['status'] = 'PASS'
        except Exception as error:
            result['status'] = 'FAIL'
            result['failure'] = f'{type(error).__name__}: {error}'
            if page:
                try: page.screenshot(path=str(output/'failure.png'))
                except Exception: pass
        finally:
            result['response_count'] = len(responses)
            result['elapsed_seconds'] = round(time.monotonic()-started,3)
            try:
                if context: context.close()
                if video: video.save_as(str(output/'viewport.webm'))
            finally:
                if browser: browser.close()
                save(output/'result.json',result)
    if args.record and (output/'viewport.webm').exists():
        subprocess.run(['ffmpeg','-v','error','-i',str(output/'viewport.webm'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(output/'viewport.mp4')],check=True)
        probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=width,height','-of','json',str(output/'viewport.mp4')],check=True,capture_output=True,text=True)
        save(output/'ffprobe.json',json.loads(probe.stdout))
    print(f"{result['status']} mode={args.mode} requests={len(responses)} output={output}")
    return 0 if result['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
