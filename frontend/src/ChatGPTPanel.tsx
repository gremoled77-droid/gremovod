import ReplaceCharacterButton,{type ReplacementControls} from './ReplaceCharacterButton';
import {useEffect,useRef,useState} from 'react';
import {apiFetch} from './api';
import {type CameraSelection} from './CameraPanel';
import {type FrameSelection} from './FramePanel';

type ChatJob={production_node_id?:string|null;id:string;target:string;operation:string;status:string;prompt:string;message:string;asset_id:string;image_url:string|null;chat_url:string;use_scene:boolean;camera_movement?:CameraSelection|null;frame_composition?:FrameSelection|null};
type ChatStatus={chat_url:string;worker_online:boolean;worker_busy:boolean;note:string};
export async function responseJson(r:Response){const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));return d}

export default function ChatGPTPanel({projectId,target='gpt-image-2.5',useScene=false,ensureProject,onPrompt,onAsset,character,onReplaced}:{
  projectId:string;target?:string;useScene?:boolean;ensureProject:()=>Promise<string>;
  onPrompt:(prompt:string,target:string,camera?:CameraSelection|null,composition?:FrameSelection|null)=>void;onAsset:()=>void;
}&ReplacementControls){
  const [status,setStatus]=useState<ChatStatus|null>(null),[jobs,setJobs]=useState<ChatJob[]>([]);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const applied=useRef(new Set<string>()),assets=useRef(new Set<string>());
  const baseline=useRef(false);
  const pending=useRef<{id:string;operation:string;project:string}|null>(null);
  useEffect(()=>{
    let active=true;setJobs([]);baseline.current=false;
    const refresh=async()=>{try{
      const s=await responseJson(await apiFetch('/api/chatgpt/status'));
      const items=projectId?await responseJson(await apiFetch('/api/chatgpt/jobs?project_id='+encodeURIComponent(projectId))):[];
      if(active){if(!baseline.current){for(const item of items as ChatJob[]){if(item.prompt)applied.current.add(item.id);if(item.asset_id)assets.current.add(item.asset_id)}baseline.current=true}setStatus(s);setJobs(items)}
    }catch(e){if(active)setError(e instanceof Error?e.message:String(e))}};
    void refresh();const timer=window.setInterval(()=>{if(!document.hidden)void refresh()},4000);
    return()=>{active=false;window.clearInterval(timer)};
  },[projectId]);
  useEffect(()=>{for(const job of jobs){
    if(!job.production_node_id&&['prompt','generate'].includes(job.operation)&&job.use_scene===useScene&&job.target===target&&job.prompt&&!applied.current.has(job.id)){applied.current.add(job.id);onPrompt(job.prompt,job.target,job.camera_movement,job.frame_composition)}
    if(job.asset_id&&!assets.current.has(job.asset_id)){assets.current.add(job.asset_id);onAsset()}
  }},[jobs,onPrompt,onAsset,target]);
  const submit=async(operation:string)=>{setBusy(true);setError('');try{
    const id=await ensureProject();
    // Preserve the submission ID after a lost response; never silently duplicate a generation.
    if(!pending.current||pending.current.operation!==operation||pending.current.project!==id)
      pending.current={id:crypto.randomUUID(),operation,project:id};
    const job=await responseJson(await apiFetch('/api/chatgpt/jobs',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({project_id:id,target,operation,use_scene:useScene,request_id:pending.current.id})}));
    pending.current=null;setJobs(items=>[job,...items.filter(x=>x.id!==job.id)]);
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  const isImage=target.startsWith('gpt-image-');
  const visible=jobs.filter(j=>!j.production_node_id&&['prompt','generate'].includes(j.operation)&&j.use_scene===useScene&&j.target===target);
  const active=jobs.some(j=>['queued','preparing','generating'].includes(j.status));
  return <section className={useScene?'chatgpt-scene':'panel chatgpt-panel'}>
    <div className="panel-title"><h2>{useScene?'GPT-ветка · промпт сцены':isImage?'GPT-ветка · фотопромпт':'GPT-ветка · видеопромпт'}</h2>
      {status&&<a className="button" href={status.chat_url}>Открыть GPT-ветку ↗</a>}</div>
    <p className="muted">Выбранные параметры, задание и референсы станут базой для GPT. Готовый промпт вернётся сюда для проверки. Подготовка промпта не запускает генерацию изображения или видео.</p>
    {isImage&&<p className="muted">Целевая модель: {target}. Встроенный инструмент чата не раскрывает выбор версии и технических настроек; точная модель не подтверждена.</p>}
    <p className={'worker-status '+(status?.worker_online?'online':'offline')} role="status">
      {status?.worker_online?(status.worker_busy?'● Чат выполняет задание':'● Обработчик чата подключён'):'○ Обработчик чата неактивен'}</p>
    {!status?.worker_online&&<p className="muted">{status?.note||'Проверка связи…'}</p>}
    <div className="chips"><button className="primary" disabled={busy||active} onClick={()=>void submit('prompt')}>✦ Подготовить промпт в GPT-ветке</button></div>
    {isImage&&<details className="native-generation-extra"><summary>Дополнительно: подготовить промпт и сразу создать фото</summary><p className="muted">Этот отдельный запуск использует встроенную генерацию изображения в GPT-ветке.</p><button disabled={busy||active} onClick={()=>void submit('generate')}>Подготовить промпт и создать фото</button></details>}
    {error&&<div className="alert" role="alert">{error}</div>}
    <div className="native-results">{visible.slice(0,6).map(job=><article className="job" key={job.id}>
      <div className="jobtop"><b>{job.target}</b><span>{({queued:'В очереди',preparing:'Подготовка промпта',generating:'Генерация изображения',completed:'Готово',failed:'Ошибка',cancelled:'Отменено'} as Record<string,string>)[job.status]||job.status}</span></div>
      <p className="muted">{job.message}</p>
      {job.prompt&&<details open={job.operation==='prompt'}><summary>Готовый промпт</summary><pre>{job.prompt}</pre></details>}
      {job.image_url&&<><img src={job.image_url} alt="Изображение из чата"/><div className="chips">
        <a className="button primary" href={job.chat_url}>Править в чате ↗</a><ReplaceCharacterButton projectId={projectId} assetId={job.asset_id} character={character} onReplaced={onReplaced}/><a href={job.image_url} download>Скачать оригинал</a></div></>}
      {job.status==='queued'&&<button onClick={()=>{void apiFetch(`/api/chatgpt/jobs/${job.id}/cancel`,{method:'POST'}).then(responseJson).then(updated=>setJobs(items=>items.map(x=>x.id===job.id?updated:x))).catch(e=>setError(String(e)))}}>Отменить ожидание</button>}
    </article>)}</div>
  </section>;
}
