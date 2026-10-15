import {useEffect,useState} from 'react';
import {apiFetch,PAID_LLM_ENABLED} from './api';
export type PromptRequest={project_id:string;target:string;provider:string;model:string};
export default function PromptComposer({request,onClose,onComposed}:{request:PromptRequest;onClose:()=>void;onComposed:(prompt:string)=>void}){
  const [preview,setPreview]=useState<{context:Record<string,unknown>;system_rules:string}|null>(null);
  const [approved,setApproved]=useState(false);const [busy,setBusy]=useState(false);const [attempted,setAttempted]=useState(false);const [error,setError]=useState('');
  useEffect(()=>{let active=true;void(async()=>{try{const r=await apiFetch('/api/compose/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));if(active)setPreview(d)}catch(e){if(active)setError(e instanceof Error?e.message:String(e))}})();return()=>{active=false}},[request]);
  const compose=async()=>{setBusy(true);setAttempted(true);setError('');try{const r=await apiFetch('/api/compose',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...request,approved:true})});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));onComposed(d.prompt)}catch(e){setError((e instanceof Error?e.message:String(e))+' Автоматический платный повтор не выполняется.')}finally{setBusy(false)}};
  return <div className="modal-backdrop"><section className="panel generation-review" role="dialog" aria-modal="true" aria-labelledby="compose-title">
    <h2 id="compose-title">Подготовка промпта через API</h2><p className="notice">API-резерв временно отключён до настройки оценки стоимости. Контекст можно просмотреть, а промпт подготовить в основном чате Codex.</p><p>{request.provider} · {request.model} → {request.target}</p>
    <p className="muted">Сервер собрал задание, библию мира, выбранного персонажа, его профиль для этой модели, настройки и описания референсов. Используются правила ai-video и cinematic-studio; LLM получает их вместе с контекстом.</p>
    {preview&&<><details><summary>Контекст проекта</summary><pre>{JSON.stringify(preview.context,null,2)}</pre></details><details><summary>Инструкции для модели</summary><pre>{preview.system_rules}</pre></details></>}
    <p className="muted">Один платный LLM-запрос, ответ до 1400 токенов. Точная стоимость зависит от тарифа выбранной модели и длины контекста; долларовая оценка пока недоступна. Видео автоматически не запускается. Промпт и фактический usage сохраняются в истории проекта.</p>
    <label className="inline-checkbox"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)} disabled={attempted}/> Разрешаю один платный LLM-запрос для подготовки промпта</label>
    {error&&<div className="alert" role="alert">{error}</div>}
    <div className="chips"><button className="primary" disabled={!PAID_LLM_ENABLED||!preview||!approved||busy||attempted} onClick={compose}>{busy?'LLM готовит промпт…':'Подготовить через API'}</button><button disabled={busy} onClick={onClose}>Закрыть</button></div>
  </section></div>;
}
