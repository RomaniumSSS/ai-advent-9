"""Офлайн: кнопка запуска и безопасное отображение текста; HTTP подставлен."""
from playwright.sync_api import sync_playwright
from record_live import HTML

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.expose_function('generate', lambda: {'answer': '<script>bad()</script>',
        'sources': [{'source':'assignment','chunk_id':'c'}],
        'quotes':[{'text':'Проверенная цитата'}], 'cost':.001})
    page.set_content(HTML)
    page.locator('#run').click()
    page.wait_for_function("document.getElementById('status').textContent.includes('Новый ответ получен')")
    assert page.locator('#answer').inner_text() == '<script>bad()</script>'
    assert page.locator('#answer script').count() == 0 and not errors
    b.close()
print('ok: browser button + escaped answer; fake generation, no cloud')
