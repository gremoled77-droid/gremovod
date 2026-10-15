import {useEffect,useState} from 'react';
import {apiFetch} from './api';
import ChatGPTPanel,{responseJson} from './ChatGPTPanel';
import {CameraSelector,cameraBasis,cameraOutdated,type CameraPreset,type CameraSelection} from './CameraPanel';
import {FrameSelector,frameBasis,frameOutdated,type FrameCatalogue,type FrameSelection} from './FramePanel';

export type Scene={brief:string;assets:{asset_id:string;role:string;note:string}[];target:string;prompts:Record<string,string>;cameraPromptBasis?:Record<string,string>;compositionPromptBasis?:Record<string,string>};
export const EMPTY_SCENE:Scene={brief:'',assets:[],target:'gpt-image-2.5',prompts:{}};
type Asset={id:string;url:string;metadata:{kind?:string;width:number;height:number}};
export default function ScenePanel({scene,onChange,projectId,revision,models,ensureProject,onAsset,onGenerate,cameraPresets,camera,onCamera,frameCatalogue,composition,onComposition,onFrameCatalogue,onCameraCatalogue}:{
  scene:Scene;onChange:(scene:Scene)=>void;projectId:string;revision:number;models:{id:string;kind:string;enabled:boolean}[];
  ensureProject:()=>Promise<string>;onAsset:()=>void;onGenerate:(target:string,prompt:string)=>void;
  cameraPresets:CameraPreset[];camera?:CameraSelection;onCamera:(camera:CameraSelection)=>void;
  frameCatalogue:FrameCatalogue;composition?:FrameSelection;onComposition:(value:FrameSelection)=>void;
  onFrameCatalogue:()=>void;onCameraCatalogue:()=>void;
}){
  const [assets,setAssets]=useState<Asset[]>([]),[error,setError]=useState('');
  useEffect(()=>{let active=true;setAssets([]);if(projectId)void apiFetch('/api/library?project_id='+encodeURIComponent(projectId)).then(responseJson).then(items=>{if(active)setAssets(items.filter((x:Asset)=>!['video','audio'].includes(x.metadata.kind||'image')))}).catch(e=>{if(active)setError(String(e))});return()=>{active=false}},[projectId,revision]);
  const selected=new Set(scene.assets.map(x=>x.asset_id));
  const model=models.find(x=>x.id===scene.target);
  return <section className="panel scene-panel"><h2>Сцена</h2>
    <p className="muted">Соедини персонажа, локацию и предметы в одном кадре. Роли исходников и инструкция сохраняются вместе с проектом ролика.</p>
    {error&&<div className="alert">{error}</div>}
    <div className="scene-assets">{scene.assets.map((item,index)=>{const asset=assets.find(x=>x.id===item.asset_id);return <article className="connection-card" key={item.asset_id}>
      {asset&&<img src={asset.url} alt={'Исходник '+(index+1)}/>}<b>Изображение {index+1}</b>
      <label>Роль<select value={item.role} onChange={e=>onChange({...scene,assets:scene.assets.map((x,i)=>i===index?{...x,role:e.target.value}:x)})}>
        <option value="character">Персонаж / внешность</option><option value="location">Локация / геометрия</option><option value="object">Предмет</option><option value="style">Стиль / свет</option><option value="composition">Композиция</option></select></label>
      <label>Что взять из изображения<input value={item.note} onChange={e=>onChange({...scene,assets:scene.assets.map((x,i)=>i===index?{...x,note:e.target.value}:x)})}/></label>
      <button onClick={()=>onChange({...scene,assets:scene.assets.filter(x=>x.asset_id!==item.asset_id)})}>Убрать из сцены</button></article>})}</div>
    <label>Добавить из библиотеки<select value="" onChange={e=>e.target.value&&onChange({...scene,assets:[...scene.assets,{asset_id:e.target.value,role:scene.assets.length?'location':'character',note:''}]})}>
      <option value="">Выбери исходник…</option>{assets.filter(x=>!selected.has(x.id)).map(x=><option key={x.id} value={x.id}>{x.id.slice(0,8)} · {x.metadata.width}×{x.metadata.height}</option>)}</select></label>
    {!assets.length&&<p className="muted">Сначала сохрани изображения в библиотеку и нажми «Отправить в сцену».</p>}
    <label>Постановка сцены<textarea rows={5} value={scene.brief} onChange={e=>onChange({...scene,brief:e.target.value})} placeholder="Кто и где находится, масштаб и расположение, действие, камера, свет. Для видео — что меняется во времени."/></label>
    <label>Целевая модель<select value={scene.target} onChange={e=>onChange({...scene,target:e.target.value})}>{models.map(x=><option key={x.id} value={x.id}>{x.kind==='video'?'Видео':'Фото'} · {x.id}</option>)}</select></label>
    {model?.kind==='video'&&<CameraSelector setupEnabled={!!frameCatalogue.capabilities?.prompt_setup} presets={cameraPresets} value={camera} onChange={onCamera} onCatalogue={onCameraCatalogue}/>}
    {model?.kind==='image'&&<FrameSelector catalogue={frameCatalogue} value={composition} onChange={onComposition} onCatalogue={onFrameCatalogue}/>}
    <ChatGPTPanel projectId={projectId} target={scene.target} useScene ensureProject={ensureProject} onAsset={onAsset} onPrompt={(prompt,target,movement,frame)=>onChange({...scene,prompts:{...scene.prompts,[target]:prompt},cameraPromptBasis:{...scene.cameraPromptBasis,[target]:cameraBasis(movement)},compositionPromptBasis:{...scene.compositionPromptBasis,[target]:frameBasis(frame)}})}/>
    <label>Улучшенный промпт · {scene.target}<textarea rows={6} value={scene.prompts[scene.target]||''} onChange={e=>onChange({...scene,prompts:{...scene.prompts,[scene.target]:e.target.value}})}/></label>
    {model?.kind==='video'&&cameraOutdated(camera,scene.cameraPromptBasis?.[scene.target],scene.prompts[scene.target]||'')&&<div className="notice" role="status"><p>Камера изменена. Пересобери промпт или проверь его вручную.</p><button onClick={()=>onChange({...scene,cameraPromptBasis:{...scene.cameraPromptBasis,[scene.target]:cameraBasis(camera)}})}>Камера учтена в этом промпте</button></div>}
    {model?.kind==='image'&&frameOutdated(composition,scene.compositionPromptBasis?.[scene.target],scene.prompts[scene.target]||'')&&<div className="notice" role="status"><p>Ракурс или свет изменены. Подготовь новый фотопромпт либо проверь его вручную.</p><button onClick={()=>onChange({...scene,compositionPromptBasis:{...scene.compositionPromptBasis,[scene.target]:frameBasis(composition)}})}>Ракурс и свет учтены в промпте</button></div>}
    {!scene.target.startsWith('gpt-image-')&&<><button className="primary" disabled={!scene.prompts[scene.target]?.trim()||!model?.enabled||(model?.kind==='video'&&cameraOutdated(camera,scene.cameraPromptBasis?.[scene.target],scene.prompts[scene.target]||''))||(model?.kind==='image'&&frameOutdated(composition,scene.compositionPromptBasis?.[scene.target],scene.prompts[scene.target]||''))} onClick={()=>onGenerate(scene.target,scene.prompts[scene.target])}>Проверить стоимость и создать {model?.kind==='video'?'видео':'фото'} через API</button>
      {!model?.enabled&&<p className="muted">Промпт доступен; запуск провайдера этой модели пока не подключён.</p>}</>}
  </section>;
}
