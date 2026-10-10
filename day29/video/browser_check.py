"""Браузерные контракты на явной фикстуре: без Ollama и оценки качества модели."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import app
from core import DB_SHA, GENERATION, load_profiles


class FixtureEngine:
    identity = {'generation': GENERATION, 'db_sha256': DB_SHA}

    def ask(self, question, profile_id, run_id=None, request_id=None):
        profile = load_profiles()[profile_id]
        text = '<img src=x onerror="window.fixtureXss=true"> Это тест интерфейса, не ответ LLM.'
        unknown = 'бюджет' in question
        sources = [] if unknown else [{'source': 'assignment:18', 'chunk_id': 'fixture-chunk'}]
        quotes = [] if unknown else [{'chunk_id': 'fixture-chunk', 'text': text}]
        return {'run_id': run_id, 'request_id': request_id, 'question': question,
                'profile_id': profile_id, 'scope': 'public', 'model': profile['model'],
                'generation_options': profile['options'], 'index': self.identity,
                'status': 'unknown' if unknown else 'done', 'citations_valid': True,
                'answer': {'answer': 'Не знаю по переданному контексту' if unknown else text,
                           'sources': sources, 'quotes': quotes},
                'selected': [{'source': 'assignment', 'document_id': 'assignment:18',
                              'chunk_id': 'fixture-chunk', 'text': text}],
                'times': {'generation': 1.25, 'total': 1.5},
                'metrics': {'seconds': {'load_duration': 0.001}},
                'resources': {'observed_max_sum_rss_bytes': 3 * 1024**3},
                'context_sha256': 'fixture-only'}


def run(output):
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=False)
    checks = []
    errors = []
    with tempfile.TemporaryDirectory(prefix='day29-browser-fixture-') as directory:
        temp = Path(directory)
        shutil.copytree(HERE / 'static', temp / 'static')
        shutil.copy2(HERE / 'profiles.json', temp / 'profiles.json')
        (temp / 'results').mkdir()
        summary = {'historical': True, 'metadata': {'warm_run_id': 'fixture-warm-run',
                   'generated_at': '2026-10-10T00:00:00Z'},
                   'groups': [{'profile_id': 'candidate', 'mode': 'warm', 'case_id': 'E02',
                               'generation_seconds': {'count': 2, 'median': 12.5},
                               'observed_rss_bytes': {'median': 3 * 1024**3}}],
                   'quality': {'note': 'Фикстура UI; не проверка реальной LLM.'},
                   'verdict': {'proven': False, 'reason': 'fixture_only'},
                   'quantization': {'status': 'fixture_only'},
                   'delivery': {'code': 'fixture only', 'video': 'not recorded', 'published': False}}
        (temp / 'results' / 'public-summary.json').write_text(json.dumps(summary, ensure_ascii=False))
        previous = app.HERE
        app.HERE = temp
        server = None
        try:
            instance = app.Application(FixtureEngine(), temp / 'receipts')
            server = ThreadingHTTPServer(('127.0.0.1', 8069), app.handler_for(instance))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                try:
                    for label, width, height in [('desktop', 1280, 1000),
                                                 ('tablet', 768, 1024), ('mobile', 375, 812)]:
                        context = browser.new_context(viewport={'width': width, 'height': height})
                        try:
                            page = context.new_page()
                            page.on('pageerror', lambda err: errors.append(str(err)))
                            page.goto('http://127.0.0.1:8069')
                            page.wait_for_function("() => document.querySelector('#profile').options.length > 0")
                            page.locator('#profile').select_option('candidate')
                            page.locator('#question').fill('Что требуется сделать в задании дня 18?')
                            page.locator('#send').click()
                            page.wait_for_function("() => document.querySelector('#result').dataset.state === 'done'")
                            assert 'Это тест интерфейса' in page.locator('#answer').inner_text()
                            assert page.locator('#sources .source').count() == 1
                            assert page.evaluate('() => window.fixtureXss !== true')
                            assert page.locator('#answer img, #sources img').count() == 0
                            assert not page.locator('#send').is_disabled()
                            assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth + 1')
                            assert '6144' in page.locator('#parameters').inner_text()
                            page.locator('#result').scroll_into_view_if_needed()
                            page.screenshot(path=str(output / (label + '-answer.png')))
                            page.locator('#question').scroll_into_view_if_needed()
                            page.locator('#question').fill('Какой точный бюджет в евро установлен для выполнения задания дня 18?')
                            page.locator('#send').click()
                            page.wait_for_function("() => document.querySelector('#result').dataset.state === 'unknown'")
                            assert page.locator('#sources .source').count() == 0
                            assert 'Не знаю' in page.locator('#answer').inner_text()
                            page.locator('#summary').scroll_into_view_if_needed()
                            page.screenshot(path=str(output / (label + '-summary.png')))
                            checks.append({'viewport': label, 'size': [width, height],
                                           'status': 'PASS', 'contracts': ['declared profile', 'fresh request state',
                                           'full text', 'XSS text-only', 'unknown source reset', 'no horizontal overflow']})
                        finally:
                            context.close()
                    context = browser.new_context()
                    try:
                        client = context.request
                        assert client.get('http://127.0.0.1:8069/private/structure.db').status == 404
                        assert client.get('http://127.0.0.1:8069/api/state', headers={'Host': 'evil.example'}).status == 403
                        assert client.post('http://127.0.0.1:8069/api/ask',
                                           data={'question': 'x', 'profile_id': 'baseline'},
                                           headers={'Origin': 'https://evil.example'}).status == 403
                        assert client.post('http://127.0.0.1:8069/api/ask',
                                           data={'question': 'x', 'profile_id': 'baseline', 'scope': 'all'}).status == 400
                        assert client.post('http://127.0.0.1:8069/api/ask',
                                           data={'question': 'x', 'profile_id': 'unknown'}).status == 400
                        checks.append({'group': 'HTTP boundaries', 'status': 'PASS'})
                    finally:
                        context.close()
                finally:
                    browser.close()
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
            app.HERE = previous
    result = {'status': 'PASS' if not errors else 'FAIL', 'fixture': True,
              'real_model_calls': 0, 'checks': checks, 'page_errors': errors}
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if errors:
        raise RuntimeError('browser_page_errors')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Day29 браузер: явная фикстура без inference')
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
