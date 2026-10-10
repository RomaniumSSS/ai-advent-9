"""Новые ответы в браузере: одинаковый сценарий сухого прогона и живой записи."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from core import context_messages, save_private, sha


def run(args):
    from playwright.sync_api import sync_playwright

    if args.url != 'http://127.0.0.1:8069':
        raise ValueError('demo_fixed_loopback_required')
    suite = json.loads((HERE / 'eval-suite.json').read_text())
    cases = {case['case_id']: case for case in suite['cases']}
    steps = [('E02', 'baseline'), ('E02', args.candidate),
             ('E01', args.candidate), ('E03', args.candidate)]
    run_id = uuid.uuid4().hex
    output = args.output or HERE / 'video' / 'runs' / run_id
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    output.chmod(0o700)
    result = {'run_id': run_id, 'mode': 'record' if args.record else 'dry-run',
              'url': args.url, 'candidate': args.candidate, 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat(),
              'requests': [], 'frames': [], 'page_errors': []}
    video = None
    print(json.dumps({'run_id': run_id, 'output': str(output)}), flush=True)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = None
            try:
                options = {'viewport': {'width': 1280, 'height': 1000}}
                if args.record:
                    options.update(record_video_dir=str(output / 'raw'),
                                   record_video_size=options['viewport'])
                context = browser.new_context(**options)
                capture_start = time.monotonic()
                page = context.new_page()
                page.on('pageerror', lambda err: result['page_errors'].append(str(err)))
                page.goto(args.url)
                page.locator('#send').wait_for(state='visible')
                page.wait_for_function("() => document.querySelector('#profile').options.length > 0")
                state = page.request.get(args.url + '/api/state').json()
                result['app_state'] = state
                if state.get('scope', 'public') != 'public':
                    raise RuntimeError('demo_requires_public_scope')

                def frame(name, pause=3500):
                    page.screenshot(path=str(output / (name + '.png')))
                    if args.record:
                        page.wait_for_timeout(650)
                    result['frames'].append({'name': name, 'file': name + '.png',
                                             'video_seconds': time.monotonic() - capture_start})
                    save_private(output / 'results.json', result)
                    if args.record:
                        page.wait_for_timeout(pause)

                frame('start')
                for number, (case_id, profile_id) in enumerate(steps, 1):
                    case = cases[case_id]
                    page.locator('#question').scroll_into_view_if_needed()
                    page.locator('#profile').select_option(profile_id)
                    page.locator('#question').fill(case['question'])
                    started = time.monotonic()
                    with page.expect_response(
                        lambda response: response.url == args.url + '/api/ask'
                        and response.request.method == 'POST'
                    ) as response_event:
                        page.locator('#send').click()
                    response = response_event.value
                    submission = response.json()
                    request_id = submission.get('request_id')
                    if response.status != 202 or not request_id:
                        raise RuntimeError('live_request_not_submitted')
                    page.wait_for_function(
                        "rid => {const r=document.querySelector('#result'); "
                        "return r.dataset.requestId===rid && "
                        "['done','unknown','error','rejected'].includes(r.dataset.state)}",
                        arg=request_id, timeout=330000)
                    actual_response = page.request.get(args.url + '/api/requests/' + request_id)
                    actual = actual_response.json()
                    if actual_response.status != 200 or actual.get('request_id') != request_id:
                        raise RuntimeError('wrong_live_request')
                    if actual.get('profile_id') != profile_id or actual.get('question') != case['question']:
                        raise RuntimeError('wrong_profile_or_question')
                    if actual.get('scope') != 'public' or any(
                        c.get('source') != 'assignment' for c in actual.get('selected', [])):
                        raise RuntimeError('private_scope_leak')
                    expected_status = 'unknown' if case_id == 'E03' else 'done'
                    if actual.get('status') != expected_status or not actual.get('citations_valid'):
                        raise RuntimeError('live_answer_contract_failed:' + request_id)
                    answer = actual.get('answer') or {}
                    expected_sources = set(case['expected']['required_document_ids'])
                    actual_sources = {source['source'] for source in answer.get('sources', [])}
                    if not expected_sources.issubset(actual_sources):
                        raise RuntimeError('missing_required_source:' + request_id)
                    if case_id == 'E03' and (answer.get('sources') or answer.get('quotes')):
                        raise RuntimeError('unknown_has_unfounded_sources')
                    visible = page.locator('#answer').inner_text()
                    if answer.get('answer', '').strip() not in visible:
                        raise RuntimeError('visible_answer_differs_from_receipt')
                    if result['page_errors']:
                        raise RuntimeError('browser_page_error')
                    item = {'case_id': case_id, 'profile_id': profile_id,
                            'request_id': request_id, 'elapsed_seconds': time.monotonic() - started,
                            'actual': actual, 'visible_answer': visible,
                            'semantic_assessment': 'Отдельная проверка полноты и фактов после прогона.'}
                    result['requests'].append(item)
                    page.locator('#result').evaluate("e => e.scrollIntoView({block: 'start'})")
                    frame('answer-' + str(number), pause=6000)
                    details = page.locator('#sources details')
                    for index in range(details.count()):
                        details.nth(index).evaluate('(e) => {e.open = true}')
                    source_cards = page.locator('#sources .source')
                    for index in range(source_cards.count()):
                        source_cards.nth(index).evaluate("e => e.scrollIntoView({block: 'start'})")
                        frame(f'source-{number}-{index + 1}')
                    print(json.dumps({'case_id': case_id, 'profile_id': profile_id,
                                      'request_id': request_id, 'status': actual['status']}), flush=True)

                e02 = result['requests'][:2]
                # AICODE-NOTE: живой retrieval повторяется; score не передаётся LLM.
                # Сравниваем именно вопрос/текст/порядок, отдельно сохраняя snapshot hashes.
                actual_pair = [item['actual'] for item in e02]
                context_inputs = [context_messages(item['question'], item['selected'])[1]
                                  for item in actual_pair]
                index_keys = [(item['index']['generation'], item['index']['db_sha256'])
                              for item in actual_pair]
                result['live_pair_verification'] = {
                    'input_sha256': [sha(item) for item in context_inputs],
                    'same_input_text_and_order': context_inputs[0] == context_inputs[1],
                    'same_index': index_keys[0] == index_keys[1],
                    'snapshot_sha256': [item.get('context_sha256') for item in actual_pair]}
                if context_inputs[0] != context_inputs[1] or index_keys[0] != index_keys[1]:
                    raise RuntimeError('live_comparison_context_changed')
                page.locator('#summary').evaluate("e => e.scrollIntoView({block: 'start'})")
                frame('summary', pause=6500)
                summary_blocks = page.locator('#summary .summary-block')
                for index in range(summary_blocks.count()):
                    summary_blocks.nth(index).evaluate("e => e.scrollIntoView({block: 'start'})")
                    frame('summary-' + str(index + 1))
                summary_table = page.locator('#summary table')
                if summary_table.count():
                    summary_table.evaluate("e => e.scrollIntoView({block: 'start'})")
                    frame('comparison-table', pause=6500)
                result['visible_summary'] = page.locator('#summary').inner_text()
                result.update(status='completed', semantic_review='required', video_review='required')
                if args.record:
                    video = page.video
            finally:
                if context is not None:
                    if args.record and video is None and context.pages:
                        video = context.pages[0].video
                    context.close()
                    if video is not None:
                        video.save_as(str(output / 'live.webm'))
                browser.close()
        if args.record:
            mp4 = output / 'live.mp4'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
                            '-i', str(output / 'live.webm'), '-c:v', 'libx264',
                            '-crf', '20', '-pix_fmt', 'yuv420p', '-an',
                            '-movflags', '+faststart', str(mp4)], check=True)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_format',
                                    '-show_streams', '-of', 'json', str(mp4)],
                                   capture_output=True, text=True, check=True)
            result['ffprobe'] = json.loads(probe.stdout)
            result['video_sha256'] = hashlib.sha256(mp4.read_bytes()).hexdigest()
    except Exception as err:
        result.update(status='error', error={'type': type(err).__name__, 'message': str(err)})
        raise
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        save_private(output / 'results.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Day29: четыре новых ответа, сухой прогон или запись')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--dry-run', action='store_true')
    modes.add_argument('--record', action='store_true')
    parser.add_argument('--url', default='http://127.0.0.1:8069')
    parser.add_argument('--candidate', default='candidate')
    parser.add_argument('--output', type=Path)
    run(parser.parse_args())
