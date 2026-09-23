// Never cache legal answers, API calls, or conversation history.
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
  if(event.request.mode==='navigate')event.respondWith(fetch(event.request).catch(()=>new Response('<html lang="ko"><meta charset="utf-8"><p>인터넷 연결이 필요합니다. 법률 답변은 오프라인에 저장하지 않습니다.</p></html>',{headers:{'Content-Type':'text/html; charset=utf-8'}})));
});
