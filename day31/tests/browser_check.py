"""Офлайн Chromium: настоящий MCP, безопасный render и три размера экрана."""
from __future__ import annotations
import argparse
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from playwright.sync_api import sync_playwright
from day31.config import build_assistant
from day31.provider import ProviderResult
from day31.web import make_server


class HtmlProvider:
    model='fake-html'; provider='test'
    def generate(self, question,sources,git_context,trace_id):
        return ProviderResult(json.dumps({'status':'ok','text':'<img src=x onerror="window.xss=1"><script>window.xss=1</script>','source_ids':[sources[0]['id']]}),None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2],help='Git-root для независимой сверки UI/API с командами Git')
    parser.add_argument('--output',type=Path,default=Path('/tmp/day31-browser-check'))
    args=parser.parse_args(); output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    configured_repo=args.repo.expanduser().resolve(strict=True)
    def git(*command):
        return subprocess.check_output(['git','-C',str(configured_repo),*command],stderr=subprocess.PIPE,timeout=10).decode().strip()
    expected_root=Path(git('rev-parse','--show-toplevel')).resolve(strict=True)
    expected_branch=git('branch','--show-current') or None
    expected_head=git('rev-parse','--verify','HEAD')
    expected={'branch':expected_branch,'head':expected_head,'detached':expected_branch is None,'root':str(expected_root)}
    with tempfile.TemporaryDirectory() as temp:
        app=build_assistant(SimpleNamespace(repo=configured_repo,data_dir=Path(temp),live=False,budget_usd=None,env_file=None))
        server=make_server(app,0); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        evidence={'mode':'offline-extract + настоящий stdio MCP','checks':[],'screenshots':[],'git_expected_independent':expected}
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                page=browser.new_page(viewport={'width':1280,'height':800},device_scale_factor=1)
                errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_address[1]}')
                page.get_by_text('Офлайн · без генерации LLM',exact=True).wait_for()
                page.get_by_role('button',name='Устройство Git MCP',exact=True).click()
                with page.expect_response(lambda response:response.url.endswith('/api/answer') and response.request.method=='POST') as response_info:
                    page.get_by_role('button',name='Спросить помощника',exact=False).click()
                value=response_info.value.json()
                page.locator('#status').filter(has_text='Ответ получен').wait_for()
                assert page.locator('#root').inner_text()==expected['root']
                assert page.locator('#branch').inner_text()==f'Ветка: {expected_branch or "detached HEAD"} · HEAD {expected_head}'
                assert {key:value['git_context'][key] for key in ('branch','head','detached')}=={key:expected[key] for key in ('branch','head','detached')}
                evidence['git_observed']=value['git_context']
                assert page.locator('#sources details').count()>0
                page.locator('#citations a').first.click()
                assert page.locator('#sources details[open]').count()==1
                assert 'SHA256' in page.locator('#sources details[open]').inner_text()
                evidence['checks'].extend(['README/docs и раскрываемые строки','точные ветка/HEAD/detached UI+API сверены независимыми командами Git','ссылка открывает существующий источник'])
                for name,width,height in [('desktop',1280,800),('tablet',768,1024),('mobile',375,812)]:
                    page.set_viewport_size({'width':width,'height':height}); page.evaluate('window.scrollTo(0,0)')
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    target=output/f'{name}.png'; page.screenshot(path=str(target),full_page=True)
                    evidence['screenshots'].append(str(target))
                page.get_by_role('button',name='Вне документации',exact=True).click()
                page.get_by_role('button',name='Спросить помощника',exact=False).click()
                page.locator('#status').filter(has_text='Нет данных').wait_for()
                assert page.locator('#sources details').count()==0
                assert 'Пропущено' in page.locator('#stages').inner_text()
                evidence['checks'].append('unknown без вызова модели')
                app.provider=HtmlProvider()
                page.get_by_role('button',name='Устройство Git MCP',exact=True).click()
                page.get_by_role('button',name='Спросить помощника',exact=False).click()
                page.locator('#status').filter(has_text='Ответ получен').wait_for()
                assert '<img' in page.locator('#answer').inner_text()
                assert page.locator('#answer img, #answer script').count()==0
                assert page.evaluate('window.xss === undefined')
                assert not errors,errors
                evidence['checks'].extend(['HTML модели отображается как текст','pageerrors=0','нет горизонтального overflow 1280/768/375'])
                browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)
        (output/'report.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
        print(json.dumps(evidence,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
