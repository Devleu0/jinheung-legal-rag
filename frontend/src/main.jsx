import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

async function api(path, options={}) {
  const r = await fetch('/api'+path, {headers:{'Content-Type':'application/json'}, ...options});
  if (!r.ok) {const e=await r.json().catch(()=>({})); const error=new Error(typeof e.detail==='string'? e.detail : '요청을 처리하지 못했습니다. 입력과 서버 연결을 확인하세요.'); error.status=r.status; throw error;}
  return r.status===204 ? null : r.json();
}
function App(){
  const [models,setModels]=useState(null), [provider,setProvider]=useState('');
  useEffect(()=>{api('/models').then(d=>{setModels(d);setProvider(d.enabled?d.default_provider:'');}).catch(()=>setError('AI 모델 설정을 불러오지 못했습니다. 새로고침해 주세요.'));},[]);
  const [session,setSession]=useState(()=>sessionStorage.getItem('legal-session'));
  const [turns,setTurns]=useState([]), [question,setQuestion]=useState('');
  const [busy,setBusy]=useState(false), [error,setError]=useState(''), [source,setSource]=useState(null);
  useEffect(()=>{if(session) api('/sessions/'+session).then(d=>setTurns(d.turns)).catch(()=>{sessionStorage.removeItem('legal-session');setSession(null);setError('이전 대화가 만료되었거나 연결할 수 없습니다. 새 대화를 시작합니다.');});},[]);
  useEffect(()=>{const close=e=>{if(e.key==='Escape')setSource(null);};window.addEventListener('keydown',close);return ()=>window.removeEventListener('keydown',close);},[]);
  async function send(e){
    e.preventDefault(); if(busy||question.trim().length<2)return;
    setBusy(true);setError('');
    try {
      let id=session;
      if(!id){const s=await api('/sessions',{method:'POST'});id=s.session_id;setSession(id);sessionStorage.setItem('legal-session',id);}
      await api('/sessions/'+id+'/messages',{method:'POST',body:JSON.stringify({question, ...(provider?{provider}:{})})});
      // Read back redacted questions; never persist raw user text in browser storage.
      const h=await api('/sessions/'+id);setTurns(h.turns);setQuestion('');
    } catch(e){if(e.status===404){setSession(null);sessionStorage.removeItem('legal-session');}setError(e.message);} finally{setBusy(false);}
  }
  async function clear(){
    setBusy(true);setError('');
    try{if(session)await api('/sessions/'+session,{method:'DELETE'}).catch(e=>{if(e.status!==404)throw e;});setSession(null);sessionStorage.removeItem('legal-session');setTurns([]);setSource(null);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <main><header><span className="brand">진흥 / LEGAL EVIDENCE</span><button onClick={clear} disabled={busy}>대화 삭제</button></header>
    <section className="intro"><span className="eyebrow">지역 주민을 위한 캡스톤 프로젝트</span><h1>법률 정보,<br/>근거부터 확인하세요.</h1><p>질문과 관련된 원문을 찾고, 출처를 함께 읽어보세요.</p></section>
    <aside className="notice">캡스톤 연구 시스템 · 법률 자문이 아닙니다. 시연 모드 자료는 가상이며 실제 근거와 구분됩니다. 이름·주소·주민번호 등 개인정보를 입력하지 마세요. 대화 접근은 24시간 후 만료되고, 서버의 다음 세션 요청 때 삭제됩니다.</aside>
    {!turns.length&&<section className="examples" aria-label="예시 질문">{['근로계약 임금 관련 내용을 찾고 싶어요','층간소음 분쟁은 어디서 확인하나요?','임대차 보증금 반환 자료를 찾아주세요'].map(q=><button key={q} onClick={()=>setQuestion(q)}>{q} ↗</button>)}</section>}
    <section className="conversation" aria-live="polite">{turns.map((t,i)=><article key={i}><h2>Q. {t.question}</h2><div className="answer"><div className="badge">{t.answer.demo?'가상 시연 자료 · 실제 법적 근거 아님':'법률 원문 검색'} / {t.answer.generation}</div><p>{t.answer.message}</p>{t.answer.sentences.map((s,j)=><p className="quote" key={j}>{s.text} <button className="citation" aria-label={`근거 ${j+1} 보기`} onClick={()=>setSource({...t.answer.sources.find(d=>d.id===s.source_id),evidence_quote:s.evidence_quote||s.text})}>[{j+1}]</button></p>)}{t.answer.warning&&<p>{t.answer.warning}</p>}<small>{t.answer.disclaimer}</small></div></article>)}</section>
    {error&&<p role="alert" className="error">{error}</p>}
    <form onSubmit={send}><label htmlFor="provider">AI 모델</label><select id="provider" value={provider} onChange={e=>setProvider(e.target.value)} disabled={busy||!models?.enabled}>
      {!models?.enabled&&<option value="">원문 발췌 (AI 생성 꺼짐)</option>}
      {models?.enabled&&models.providers.map(p=><option key={p.id} value={p.id} disabled={!p.available}>{p.label} · {p.model}{!p.available?' (서버 API 키 필요)':''}</option>)}
    </select><p><small>질문·근거·후속 대화는 선택한 AI 제공자에게 전송됩니다. 실제 검색용 임베딩은 OpenAI를 사용합니다.</small></p><label htmlFor="question">법률 정보 질문</label><textarea id="question" value={question} maxLength={1500} minLength={2} required onChange={e=>setQuestion(e.target.value)} placeholder="어떤 상황인지 개인정보 없이 알려주세요." disabled={busy}/><div className="form-bottom"><small>{question.length}/1500 · 후속 질문은 ‘그럼…’으로 시작하세요.</small><button type="submit" disabled={busy||!models||question.trim().length<2}>{busy?'근거 확인 중…':'근거 찾기 →'}</button></div></form>
    <footer>긴급 위험 상황은 112·119, 법률 상담은 대한법률구조공단 132에 문의하세요.</footer>
    {source&&<dialog open aria-labelledby="source-title"><button autoFocus onClick={()=>setSource(null)}>닫기</button><h2 id="source-title">{source.title}</h2><p>{source.locator}</p><h3>이 문장의 인용 근거</h3><blockquote>{source.evidence_quote}</blockquote><h3>근거 문맥</h3><p>{source.text}</p><small>{source.kind==='demo'?'시연 자료 작성일':source.kind==='case'?'선고일':'시행일'}: {source.effective_date} / 수집일: {source.retrieved_at}</small><p><a href={source.url} target="_blank" rel="noopener noreferrer">공식 원문 확인 ↗</a></p><small>인용 검사는 문자열 일치만 보장합니다. 법적 적용과 최신성을 보장하지 않습니다.</small></dialog>}
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
