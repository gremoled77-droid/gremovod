import ReplaceCharacterButton,{type ReplacementControls} from './ReplaceCharacterButton';
import {useEffect,useRef,useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

export type RefineDraft={source_asset_id:string;reference_asset_id:string;instruction:string};
export const EMPTY_REFINE:RefineDraft={source_asset_id:'',reference_asset_id:'',instruction:''};
type Asset={id:string;url:string;metadata:{kind?:string;width:number;height:number;provider:string;original_name?:string;character_status?:string}};
type EditJob={id:string;operation:string;status:string;prompt:string;message:string;source_asset_id:string;reference_asset_id:string|null;edit_instruction:string;asset_id:string;image_url:string|null};
type Status={worker_online:boolean;worker_busy:boolean;note:string;chat_url:string};

export default function RefinePanel({projectId,draft,onChange,ensureProject,onAsset,revision,character,onReplaced}:{
  projectId:string;draft:RefineDraft;onChange:(draft:RefineDraft)=>void;ensureProject:()=>Promise<string>;onAsset:()=>void;revision:number;
}&ReplacementControls){
  const [assets,setAssets]=useState<Asset[]>([]),[jobs,setJobs]=useState<EditJob[]>([]),[status,setStatus]=useState<Status|null>(null);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState('');
  const received=useRef(new Set<string>());
  const pending=useRef<{id:string;signature:string}|null>(null);
  useEffect(()=>{let active=true;setAssets([]);setError('');if(projectId)void apiFetch('/api/library?project_id='+encodeURIComponent(projectId)).then(responseJson).then(items=>{if(active)setAssets(items.filter((a:Asset)=>!['video','audio'].includes(a.metadata.kind||'image')))}).catch(e=>{if(active)setError(String(e))});return()=>{active=false}},[projectId,revision]);
  useEffect(()=>{let active=true;setJobs([]);const refresh=async()=>{try{
    const s=await responseJson(await apiFetch('/api/chatgpt/status'));
    const items:EditJob[]=projectId?await responseJson(await apiFetch('/api/chatgpt/jobs?project_id='+encodeURIComponent(projectId))):[];
    if(active){setStatus(s);setJobs(items)}
  }catch(e){if(active)setError(String(e))}};void refresh();const timer=window.setInterval(()=>{if(!document.hidden)void refresh()},4000);return()=>{active=false;window.clearInterval(timer)}},[projectId]);
  useEffect(()=>{for(const job of jobs)if(job.operation==='edit'&&job.asset_id&&!received.current.has(job.asset_id)){received.current.add(job.asset_id);onAsset()}},[jobs,onAsset]);
  const upload=async(file:File,role:'source_asset_id'|'reference_asset_id')=>{setBusy(role);setError('');setNotice('');try{
    const pid=await ensureProject();const form=new FormData();form.append('project_id',pid);form.append('file',file);
    const asset:Asset=await responseJson(await apiFetch('/api/library/import-image',{method:'POST',body:form}));
    setAssets(items=>[asset,...items]);onChange({...draft,[role]:asset.id});onAsset();setNotice('Изображение прикреплено; генерация ещё не запускалась.');
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy('')}};
  const submit=async()=>{setBusy('submit');setError('');setNotice('');try{
    const pid=await ensureProject();const body={project_id:pid,target:'gpt-image-2.5',operation:'edit',source_asset_id:draft.source_asset_id,reference_asset_id:draft.reference_asset_id||null,edit_instruction:draft.instruction};
    const signature=JSON.stringify(body);if(!pending.current||pending.current.signature!==signature)pending.current={id:crypto.randomUUID(),signature};
    const job=await responseJson(await apiFetch('/api/chatgpt/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,request_id:pending.current.id})}));
    pending.current=null;setJobs(items=>[job,...items.filter(j=>j.id!==job.id)]);setNotice('Правка в очереди: улучшение промпта → редактирование оригинала → новая версия.');
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy('')}};
  const active=jobs.some(j=>['queued','preparing','generating'].includes(j.status));
  const source=assets.find(a=>a.id===draft.source_asset_id),reference=assets.find(a=>a.id===draft.reference_asset_id);
  const name=(a:Asset)=>`${a.metadata.original_name||a.id.slice(0,8)} · ${a.metadata.width}×${a.metadata.height}${a.metadata.character_status==='approved'?' · рабочий образ':''}`;
  return <section className="panel refine-panel"><div className="panel-title"><h2>Допилить</h2>{status&&<a className="button" href={status.chat_url}>Открыть чат ↗</a>}</div>
    <p className="muted">Точечные правки через ChatGPT / imagegen. Оригинал задаёт внешность и визуал, дополнительный референс — только нужную деталь.</p>
    <div className="twocol"><div><h3>1. Оригинал для правки</h3>
      <label>Из библиотеки<select value={draft.source_asset_id} onChange={e=>onChange({...draft,source_asset_id:e.target.value})}><option value="">Выбери изображение…</option>{assets.map(a=><option key={a.id} value={a.id}>{name(a)}</option>)}</select></label>
      <label className="upload-area">Прикрепить оригинал<input type="file" accept="image/png,image/jpeg,image/webp" disabled={!!busy||active} onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f,'source_asset_id');e.target.value=''}}/></label>
      {source&&<img className="refine-preview" src={source.url} alt="Оригинал для правки"/>}
    </div><div><h3>2. Референс детали · необязательно</h3>
      <label>Из библиотеки<select value={draft.reference_asset_id} onChange={e=>onChange({...draft,reference_asset_id:e.target.value})}><option value="">Без дополнительного референса</option>{assets.filter(a=>a.id!==draft.source_asset_id).map(a=><option key={a.id} value={a.id}>{name(a)}</option>)}</select></label>
      <label className="upload-area">Прикрепить референс<input type="file" accept="image/png,image/jpeg,image/webp" disabled={!!busy||active} onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f,'reference_asset_id');e.target.value=''}}/></label>
      {reference&&<><img className="refine-preview" src={reference.url} alt="Дополнительный референс детали"/><button onClick={()=>onChange({...draft,reference_asset_id:''})}>Убрать референс</button></>}
    </div></div>
    <label>3. Что изменить<textarea rows={5} maxLength={4000} value={draft.instruction} onChange={e=>onChange({...draft,instruction:e.target.value})} placeholder="Например: заменить только обувь на ботинки с референса. Лицо, кепку, фигуру, одежду, позу, фон и свет сохранить."/></label>
    <details><summary>Что будет добавлено в промпт</summary><p className="muted">Редактировать исходное изображение. Менять только указанную деталь; сохранять лица, идентичность персонажей, остальные предметы, композицию, стиль, свет и цвета. Из дополнительного референса брать только то, что указано в правке. Не пересоздавать картинку по старому промпту.</p></details>
    <p className="muted">Сохранение визуала — инструкция модели; абсолютная неизменность остальных пикселей не гарантируется. Встроенный инструмент не раскрывает точный выбор модели и качества. API автоматически не используется.</p>
    <p className={'worker-status '+(status?.worker_online?'online':'offline')} role="status">{status?.worker_online?(status.worker_busy?'● Чат выполняет задание':'● Обработчик чата подключён'):'○ Обработчик чата неактивен'}</p>
    {!status?.worker_online&&<p className="muted">{status?.note||'Проверка связи…'}</p>}
    <div className="chips"><button className="primary" disabled={!!busy||active||!source||!draft.instruction.trim()||draft.source_asset_id===draft.reference_asset_id} onClick={()=>void submit()}>Улучшить промпт и перегенерировать</button>
      <button disabled={!!busy} onClick={()=>{setBusy('save');void ensureProject().then(()=>setNotice('Черновик правки сохранён.')).catch(e=>setError(String(e))).finally(()=>setBusy(''))}}>Сохранить черновик</button></div>
    {error&&<div className="alert" role="alert">{error}</div>}{notice&&<div className="notice" role="status">{notice}</div>}
    <h3>Версии правок</h3><div className="native-results">{jobs.filter(j=>j.operation==='edit').slice(0,10).map(j=><article className="job" key={j.id}>
      <div className="jobtop"><b>{j.edit_instruction}</b><span>{({queued:'В очереди',preparing:'Улучшение промпта',generating:'Редактирование',completed:'Готово',failed:'Ошибка',cancelled:'Отменено'} as Record<string,string>)[j.status]}</span></div>
      <p className="muted">{j.message}</p>{j.prompt&&<details><summary>Улучшенный промпт imagegen</summary><pre>{j.prompt}</pre></details>}
      {j.image_url&&<><div className="twocol"><div><small>Исходник</small><img src={`/api/library/${j.source_asset_id}/file`} alt="Исходник версии"/></div><div><small>Новая версия</small><img src={j.image_url} alt="Результат правки"/></div></div><div className="chips"><button onClick={()=>onChange({source_asset_id:j.asset_id,reference_asset_id:'',instruction:''})}>Взять за основу следующей правки</button><ReplaceCharacterButton projectId={projectId} assetId={j.asset_id} character={character} onReplaced={onReplaced}/><a href={j.image_url} download>Скачать оригинал</a></div></>}
      {j.status==='queued'&&<button onClick={()=>{void apiFetch(`/api/chatgpt/jobs/${j.id}/cancel`,{method:'POST'}).then(responseJson).then(updated=>setJobs(items=>items.map(x=>x.id===j.id?updated:x))).catch(e=>setError(String(e)))}}>Отменить ожидание</button>}
    </article>)}</div>
  </section>;
}
