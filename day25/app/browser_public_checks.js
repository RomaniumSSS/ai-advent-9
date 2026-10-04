async (page) => {
  const check=(value,message)=>{if(!value)throw Error(message);};
  await page.setViewportSize({width:1280,height:800});
  await page.goto('http://127.0.0.1:8054/');
  await page.waitForFunction(()=>document.getElementById('fixture-banner').hidden===false);
  check(await page.locator('#scope option[value=all]').count()===0,'all scope exposed');
  check(!(await page.content()).includes('PRIVATE_ONLY_'),'private chat/trace exposed');
  const visible=await page.evaluate(async()=>await(await fetch('/api/state')).json());
  check(visible.chats.every(chat=>chat.scope==='public'),'private chat in state');
  for(const chat of visible.chats){
    await page.locator('#chats button[data-chat-id="'+chat.chat_id+'"]').click();
    await page.waitForFunction(id=>document.querySelector('#chats button[aria-pressed=true]')?.dataset.chatId===id,chat.chat_id);
    check(!(await page.content()).includes('PRIVATE_ONLY_'),'private archive/diagnostic exposed');
  }
  return {publicOnly:'PASS',visibleChats:visible.chats.length};
}
