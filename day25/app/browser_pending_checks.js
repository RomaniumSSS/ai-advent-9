async (page) => {
  await page.goto('http://127.0.0.1:8053/');
  await page.waitForFunction(()=>document.getElementById('send').disabled===false);
  const turns=await page.locator('.turn').count();
  const before=await page.evaluate(async()=> (await (await fetch('/api/state')).json()).test_metrics);
  const sent=page.waitForRequest(r=>r.url().endsWith('/api/ask')&&r.method()==='POST');
  await page.locator('#question').fill('подробнее');await page.locator('#send').click();await sent;
  await page.reload();
  await page.waitForFunction(count=>document.querySelectorAll('.turn').length===count+1&&!document.getElementById('send').disabled,turns);
  const after=await page.evaluate(async()=> (await (await fetch('/api/state')).json()).test_metrics);
  if(after.searches!==before.searches+1||after.generations!==before.generations+1)throw Error('reload repeated a request');
  return {pendingReload:'PASS',before,after};
}
