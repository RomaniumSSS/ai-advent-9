"""Проверки настоящего UI с локальными фикстурами; Ollama не вызывается."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

from playwright.async_api import async_playwright


def stream(text, *, complete=True):
    events = [{'type': 'delta', 'content': text}]
    if complete:
        events.append({'type': 'done', 'done_reason': 'stop'})
    return ''.join(json.dumps(event, ensure_ascii=False) + '\n' for event in events)


async def check(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    result = {'kind': 'browser-fixtures', 'real_model_calls': 0,
              'started_at': datetime.now(timezone.utc).isoformat(), 'checks': []}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 1000})
        page = await context.new_page()
        requests, responses, errors = [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.route('**/api/health', lambda route: route.fulfill(json={
            'ready': True, 'message': 'Проверка интерфейса · фикстуры'}))

        async def respond(route):
            requests.append(route.request.post_data_json)
            response = responses.pop(0)
            if response.get('delay'):
                await asyncio.sleep(response['delay'])
            await route.fulfill(status=response.get('status', 200),
                                content_type=response.get('content_type', 'application/x-ndjson'),
                                body=response['body'])

        await page.route('**/api/chat', respond)

        async def send(question, body, state='done', **options):
            ident = len(requests) + 1
            responses.append({'body': body, **options})
            await page.locator('#prompt').fill(question)
            await page.locator('#send').click()
            if options.get('delay'):
                assert await page.locator('#prompt').is_disabled()
                assert await page.locator('#new-chat').is_disabled()
                assert await page.locator('#send').is_disabled()
            article = page.locator(f'[data-request-id="{ident}"]')
            await page.wait_for_function(
                "id => document.querySelector(`[data-request-id=\"${id}\"]`)?.dataset.state === "
                + json.dumps(state), arg=ident)
            assert await page.locator('#prompt').is_enabled()
            assert await page.locator('#new-chat').is_enabled()
            assert await page.locator('#send').is_enabled()
            return article

        try:
            await page.goto(args.url)
            await page.wait_for_selector('#connection-dot.ready')
            first = await send('первый вопрос', stream('первый ответ'), delay=0.4)
            assert '—' in await first.locator('.meta').inner_text()
            await send('второй вопрос', stream('второй ответ'))
            assert requests[-1]['messages'] == [
                {'role': 'user', 'content': 'первый вопрос'},
                {'role': 'assistant', 'content': 'первый ответ'},
                {'role': 'user', 'content': 'второй вопрос'}]
            await page.locator('#new-chat').click()
            assert await page.locator('.message').count() == 0
            await send('после сброса', stream('ответ после сброса'))
            assert requests[-1]['messages'] == [{'role': 'user', 'content': 'после сброса'}]
            result['checks'].append('completed history, reset, missing metrics, busy controls: PASS')

            failed = await send('оборванный вопрос', stream('частичный ответ', complete=False), 'error')
            assert await failed.locator('.text').inner_text() == 'частичный ответ'
            assert 'не добавлен' in await failed.locator('.meta').inner_text()
            await send('повторный вопрос', stream('полный ответ'))
            assert requests[-1]['messages'] == [
                {'role': 'user', 'content': 'после сброса'},
                {'role': 'assistant', 'content': 'ответ после сброса'},
                {'role': 'user', 'content': 'повторный вопрос'}]
            await send('вопрос при недоступности', json.dumps({'error': 'Ollama недоступна'}),
                       'error', status=503, content_type='application/json')
            await send('вопрос после ошибки', stream('ответ после ошибки'))
            assert all('недоступности' not in message['content'] for message in requests[-1]['messages'])
            result['checks'].append('partial EOF and HTTP errors excluded from history; recovery: PASS')

            await page.locator('#new-chat').click()
            for index in range(10):
                await send(f'вопрос {index}', stream(f'ответ {index}'))
            assert len(requests[-1]['messages']) == 17
            assert requests[-1]['messages'][0] == {'role': 'user', 'content': 'вопрос 1'}
            assert requests[-1]['messages'][-1] == {'role': 'user', 'content': 'вопрос 9'}
            assert await page.locator('.message').count() == 20
            result['checks'].append('last eight completed turns sent; earlier turns remain visible: PASS')

            await page.locator('#new-chat').click()
            await send('Покажи три шага создания локального чата.', stream(
                '1. Запустите Ollama и локальную модель.\n'
                '2. Подключите приложение к локальному HTTP API.\n'
                '3. Проверьте ввод, ответы и продолжение разговора.'))
            for name, width, height in [('desktop', 1280, 1000), ('tablet', 768, 1024), ('mobile', 375, 812)]:
                await page.set_viewport_size({'width': width, 'height': height})
                await page.screenshot(path=str(output / f'{name}.png'))
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                for selector in ['#prompt', '#send', '#new-chat']:
                    box = await page.locator(selector).bounding_box()
                    assert box and 0 <= box['x'] and box['x'] + box['width'] <= width + 1
                    assert 0 <= box['y'] and box['y'] + box['height'] <= height + 1
            result['checks'].append('desktop/tablet/mobile controls fit viewport: PASS')
            assert not errors, errors
            result.update(status='pass', page_errors=errors, intercepted_requests=len(requests))
        except Exception as error:
            result.update(status='fail', error=str(error), page_errors=errors)
            raise
        finally:
            result['finished_at'] = datetime.now(timezone.utc).isoformat()
            (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            await context.close()
            await browser.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8067')
    parser.add_argument('--output', required=True)
    asyncio.run(check(parser.parse_args()))
