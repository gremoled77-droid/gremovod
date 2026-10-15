import {useEffect,useRef,useState} from 'react';
import './StoryboardDemo.css';

type Kind='scene'|'character'|'location'|'frame';
type Variant={id:string;image:string;prompt:string};
type Unit={id:string;kind:Kind;name:string;description:string;refs:string[];variants:Variant[];selected:string|null;prompt:string;request:string;video:boolean};
type Scene={id:string;characters:string[];location:string;frames:string[]};
type Demo={units:Record<string,Unit>;scenes:Scene[];script:string};
type Job={id:string;target:string;name:string;status:string;done:boolean};
const LABELS:Record<Kind,string>={scene:'Сцена',character:'Персонаж',location:'Локация',frame:'Кадр'};
const SCRIPT='Сцена 1 — Знакомство\nГрэм встречает гостя в салоне такси.\nГрэм: Куда едем?\nГость: Пока просто вперёд.\n\nСцена 2 — Разговор по дороге\nЗа окном вечерний город. Гость рассказывает свою историю.\nГрэм слушает и улыбается.';
const uid=()=>crypto.randomUUID();
function sketch(kind:Kind,n=0){
 const accent=['#e9b778','#b3a8ed','#96ccbd'][n%3];
 const content=kind==='character'?'<circle cx="300" cy="130" r="62" fill="#8c87ac"/><path d="M232 115Q300 30 369 115" fill="#263852"/><path d="M195 290Q205 195 300 195Q395 195 405 290" fill="#364e70"/><circle cx="280" cy="128" r="5"/><circle cx="321" cy="128" r="5"/>':'<path d="M30 185V75H90V185M115 185V40H190V185M410 185V60H470V185M495 185V95H570V185" fill="#30344f"/><path d="M110 265L153 167Q300 122 447 167L490 265Z" fill="#4b516a"/><path d="M179 180Q300 145 421 180L450 235H150Z" fill="#1b2237"/><circle cx="240" cy="206" r="25" fill="#8c87ac"/><circle cx="370" cy="206" r="25" fill="#b8a48f"/><path d="M210 259Q240 218 270 259M340 259Q370 218 400 259" fill="#62748c"/>';
 return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="600" height="340" viewBox="0 0 600 340"><rect width="600" height="340" fill="#151a2d"/><circle cx="510" cy="70" r="30" fill="${accent}" opacity=".6"/>${content}<rect x="20" y="303" width="560" height="23" rx="5" fill="${accent}" opacity=".25"/><text x="300" y="320" text-anchor="middle" fill="${accent}" font-size="13" font-family="sans-serif">ДЕМО · СХЕМА, НЕ AI-ГЕНЕРАЦИЯ</text></svg>`);
}
function unit(id:string,kind:Kind,name:string,description:string,preview=false):Unit{
 const v={id:uid(),image:sketch(kind),prompt:'Стартовая схема демо'};
 return {id,kind,name,description,refs:[],variants:preview?[v]:[],selected:preview?v.id:null,prompt:'',request:'',video:false};
}
function initial():Demo{
 return {script:SCRIPT,units:{
  grem:unit('grem','character','Грэм','Водитель и главный герой. Демо-описание: настоящий канон и референсы подключим при интеграции.',true),
  guest:unit('guest','character','Гость','Гость серии. Внешность пока не утверждена.',true),
  cab:unit('cab','location','Салон такси','Вечерний город за окнами. Руль слева, Грэм за рулём, гость сзади справа.',true),
  s1:unit('s1','scene','Знакомство','Грэм встречает гостя в салоне.\n— Куда едем?\n— Пока просто вперёд.'),
  s2:unit('s2','scene','Разговор по дороге','Гость рассказывает свою историю. Грэм слушает и улыбается.'),
  f1:unit('f1','frame','Общий план','Установочный кадр салона и героев.',true),
  f2:unit('f2','frame','Грэм задаёт вопрос','Средний план Грэма. Гость остаётся за кадром.'),
  f3:unit('f3','frame','Реакция гостя','Средний план гостя на заднем сиденье.')
 },scenes:[{id:'s1',characters:['grem','guest'],location:'cab',frames:['f1','f2']},{id:'s2',characters:['grem','guest'],location:'cab',frames:['f3']}]};
}
function imageOf(u:Unit){return u.variants.find(v=>v.id===u.selected)?.image;}

export default function StoryboardDemo({open,onClose}:{open:boolean;onClose:()=>void}){
 const [data,setData]=useState<Demo>(initial),[editor,setEditor]=useState<string|null>(null),[trail,setTrail]=useState<string[]>([]);
 const [tab,setTab]=useState<'board'|'characters'|'locations'>('board'),[showScript,setShowScript]=useState(false);
 const [jobs,setJobs]=useState<Job[]>([]),[notice,setNotice]=useState(''),[pendingImport,setPendingImport]=useState<{title:string;text:string}[]|null>(null);
 const timers=useRef<ReturnType<typeof setTimeout>[]>([]);
 const editorRef=useRef<HTMLDivElement>(null),closeRef=useRef<HTMLButtonElement>(null);
 useEffect(()=>()=>timers.current.forEach(clearTimeout),[]);
 useEffect(()=>{if(open){const old=document.body.style.overflow;document.body.style.overflow='hidden';closeRef.current?.focus();return()=>{document.body.style.overflow=old}}},[open]);
 useEffect(()=>{if(editor)editorRef.current?.focus()},[editor]);
 const edit=(id:string)=>{setTrail([]);setEditor(id)};
 const nested=(id:string)=>{if(editor)setTrail(t=>[...t,editor]);setEditor(id)};
 const back=()=>{setEditor(trail[trail.length-1]||null);setTrail(t=>t.slice(0,-1))};
 const patch=(id:string,change:Partial<Unit>)=>setData(d=>({...d,units:{...d.units,[id]:{...d.units[id],...change}}}));
 const entity=editor?data.units[editor]:null;
 const scene=entity?.kind==='scene'?data.scenes.find(s=>s.id===entity.id):data.scenes.find(s=>s.frames.includes(entity?.id||''));
 function generate(id:string,video=false){
  const source=data.units[id],related=data.scenes.find(s=>s.id===id||s.frames.includes(id));
  if(jobs.some(j=>j.target===id&&!j.done))return;
  if(video&&!imageOf(source)){setNotice('Сначала выбери основное фото кадра.');return}
  const jobId=uid(),snapshot={...source};
  const context=related?`\nУчастники сцены: ${related.characters.map(k=>data.units[k].name).join(', ')}.\nЛокация: ${data.units[related.location].name}. ${data.units[related.location].description}`:'';
  const prompt=`${video?'Оживить утверждённый кадр':'Подготовить изображение'}: ${snapshot.name}.\n${snapshot.description}${context}\nПравка: ${snapshot.request||'Сохранить заданный визуал и постановку'}.\nСохранить идентичность персонажей и географию пространства. Референсов единицы: ${snapshot.refs.length}.`;
  setJobs(j=>[{id:jobId,target:id,name:source.name,status:'Имитация · подготовка промпта',done:false},...j]);
  setNotice('Демо-задание отправлено. Можно открыть другую карточку — результат вернётся к исходной.');
  timers.current.push(setTimeout(()=>setJobs(j=>j.map(x=>x.id===jobId?{...x,status:video?'Имитация · оживление':'Имитация · создание изображения'}:x)),800));
  timers.current.push(setTimeout(()=>{
   setData(d=>{const current=d.units[id];if(!current)return d;const variant:Variant={id:uid(),image:sketch(source.kind,current.variants.length),prompt};
    return {...d,units:{...d.units,[id]:video?{...current,video:true}:{...current,variants:[...current.variants,variant]}}}});
   setJobs(j=>j.map(x=>x.id===jobId?{...x,status:video?'Готово · демо видео':'Готово · новый вариант',done:true}:x));
   setNotice(`Результат для «${snapshot.name}» сохранён в её карточке. ${video?'Видео показано условной анимацией.':'Открой вариант и выбери его основным.'}`);
  },2000));
 }
 function previewImport(){
  const lines=data.script.split(/\r?\n/),parsed:{title:string;text:string}[]=[];let preamble='';
  for(const line of lines){const match=line.match(/^\s*(?:#{1,3}\s*)?Сцена\s+\d+\s*[.\-—:)]?\s*(.*)$/i);
   if(match)parsed.push({title:match[1]||`Сцена ${parsed.length+1}`,text:''});
   else if(parsed.length)parsed[parsed.length-1].text+=line+'\n';else preamble+=line+'\n';}
  if(!parsed.length){setNotice('Добавь заголовки «Сцена 1 — Название», «Сцена 2 — Название».');return}
  if(preamble.trim())parsed[0].text=preamble+parsed[0].text;
  setPendingImport(parsed);
 }
 function importScenes(){
  if(!pendingImport)return;
  setData(d=>{const units={...d.units},scenes=[...d.scenes];for(const item of pendingImport){const id=uid();units[id]=unit(id,'scene',item.title,item.text.trim());scenes.push({id,characters:['grem','guest'],location:'cab',frames:[]})}return {...d,units,scenes}});
  setPendingImport(null);setShowScript(false);setNotice('Сцены добавлены в конец доски. Прежние сцены и кадры сохранены. Участники и салон назначены как демо — их можно изменить.');
 }
 function addFrame(sceneId:string){const id=uid();setData(d=>({...d,units:{...d.units,[id]:unit(id,'frame','Новый кадр','Опиши действие и композицию.')},scenes:d.scenes.map(s=>s.id===sceneId?{...s,frames:[...s.frames,id]}:s)}));nested(id)}
 function move(id:string,direction:number){setData(d=>{const scenes=[...d.scenes],i=scenes.findIndex(s=>s.id===id),j=i+direction;if(j<0||j>=scenes.length)return d;[scenes[i],scenes[j]]=[scenes[j],scenes[i]];return {...d,scenes}})}
 function moveFrame(sceneId:string,id:string,direction:number){setData(d=>({...d,scenes:d.scenes.map(s=>{if(s.id!==sceneId)return s;const frames=[...s.frames],i=frames.indexOf(id),j=i+direction;if(j<0||j>=frames.length)return s;[frames[i],frames[j]]=[frames[j],frames[i]];return {...s,frames}})}))}
 async function attach(id:string,files:FileList|null){
  if(!files)return;const accepted=Array.from(files).filter(f=>['image/png','image/jpeg','image/webp'].includes(f.type)&&f.size<=2*1024*1024).slice(0,4);
  if(accepted.length!==files.length)setNotice('Демо принимает до 4 PNG/JPEG/WebP за раз, каждый до 2 МБ.');
  const urls=await Promise.all(accepted.map(f=>new Promise<string>((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result));r.onerror=()=>reject(Error('Не удалось прочитать референс'));r.readAsDataURL(f)})));
  setData(d=>({...d,units:{...d.units,[id]:{...d.units[id],refs:[...d.units[id].refs,...urls].slice(-8)}}}));
 }
 const mini=(id:string,click=edit)=><button key={id} className="sd-mini" onClick={()=>click(id)}>{imageOf(data.units[id])&&<img src={imageOf(data.units[id])} alt=""/>}<span>{data.units[id].name}<small>{LABELS[data.units[id].kind]} · открыть</small></span></button>;
 const frameCard=(id:string,index:number,sceneId:string)=><div className="sd-frame" key={id}><button className="sd-frame-open" onClick={()=>edit(id)}>{imageOf(data.units[id])?<img src={imageOf(data.units[id])} alt={data.units[id].name}/>:<div className="sd-placeholder">＋ Фото пока нет</div>}<b>{index+1}. {data.units[id].name}</b><small>{data.units[id].video?'▶ Демо видео':imageOf(data.units[id])?'Фото выбрано':data.units[id].variants.length?'Выбери вариант':'Запланирован'}</small></button><div className="sd-order"><button aria-label={`Кадр ${index+1} левее`} disabled={!index} onClick={()=>moveFrame(sceneId,id,-1)}>←</button><button aria-label={`Кадр ${index+1} правее`} disabled={index===data.scenes.find(s=>s.id===sceneId)!.frames.length-1} onClick={()=>moveFrame(sceneId,id,1)}>→</button></div></div>;
 return <div hidden={!open} className="sd-root"><div className="sd-shell" role="dialog" aria-modal="true" aria-label="Демо раскадровки" onKeyDown={e=>{
  if(e.key==='Escape'){e.stopPropagation();if(editor)back();else if(pendingImport)setPendingImport(null);else onClose()}
  if(e.key==='Tab'){const container=editor?editorRef.current:e.currentTarget;const nodes=Array.from(container?.querySelectorAll<HTMLElement>('button:not(:disabled),input,textarea,select,[tabindex="0"]')||[]).filter(n=>n.getClientRects().length);const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}
 }}>
 <header className="sd-header"><div><small>ИНТЕРАКТИВНОЕ ДЕМО · ДАННЫЕ ДО ПЕРЕЗАГРУЗКИ</small><h1>GremoVOD <span>/ Раскадровка</span></h1><p>Серия 01 · Случайный попутчик</p></div><button ref={closeRef} onClick={onClose}>Вернуться в студию ✕</button></header>
 <div className="sd-banner">GPT и видео здесь имитируются. Изображения — условные схемы. Референсы остаются в браузере; запросов к провайдерам и изменений рабочего проекта нет.</div>
 <div className="sd-toolbar"><div>{(['board','characters','locations'] as const).map(t=><button key={t} className={tab===t?'sd-active':''} onClick={()=>setTab(t)}>{t==='board'?'Сцены и кадры':t==='characters'?'Персонажи':'Локации'}</button>)}</div><button onClick={()=>setShowScript(s=>!s)}>Вставить сценарий</button></div>
 {notice&&<p className="sd-notice" role="status">{notice}</p>}
 {showScript&&<section className="sd-script"><h2>Сценарий серии</h2><label>Текст с заголовками «Сцена 1», «Сцена 2»<textarea rows={9} value={data.script} onChange={e=>{setData(d=>({...d,script:e.target.value}));setPendingImport(null)}}/></label><button onClick={previewImport}>Разобрать на сцены</button>{pendingImport&&<div><p>Будет добавлено сцен: {pendingImport.length}. Существующие остаются.</p>{pendingImport.map((s,i)=><p key={i}>{i+1}. {s.title}</p>)}<button className="sd-primary" onClick={importScenes}>Добавить сцены на доску</button><button onClick={()=>setPendingImport(null)}>Отмена</button></div>}</section>}
 <div className="sd-layout"><div>{tab==='board'?data.scenes.map((s,i)=><section className="sd-scene" key={s.id}><div className="sd-scene-heading"><button onClick={()=>edit(s.id)}><small>СЦЕНА {String(i+1).padStart(2,'0')}</small><h2>{data.units[s.id].name} ↗</h2></button><div><button aria-label={`Сцена ${i+1} выше`} disabled={!i} onClick={()=>move(s.id,-1)}>↑</button><button aria-label={`Сцена ${i+1} ниже`} disabled={i===data.scenes.length-1} onClick={()=>move(s.id,1)}>↓</button></div></div><p className="sd-action">{data.units[s.id].description}</p><div className="sd-links">{s.characters.map(id=>mini(id))}{mini(s.location)}</div><div className="sd-frames">{s.frames.map((id,j)=>frameCard(id,j,s.id))}<button className="sd-add" onClick={()=>addFrame(s.id)}>＋ Добавить кадр</button></div></section>):<section className="sd-scene"><h2>{tab==='characters'?'Персонажи проекта':'Локации проекта'}</h2><div className="sd-links">{Object.values(data.units).filter(u=>u.kind===(tab==='characters'?'character':'location')).map(u=>mini(u.id))}</div></section>}</div>
 <aside className="sd-queue"><h3>Как пройти демо</h3><ol><li>Открой сцену и её участников.</li><li>Открой персонажа или локацию.</li><li>Добавь референс и напиши правку.</li><li>Отправь в GPT и выбери новый вариант.</li><li>Открой кадр, создай фото и нажми «Оживить».</li></ol><h3>Возврат из GPT · демо</h3>{!jobs.length&&<p>Здесь появятся задания. Можно переключать карточки во время ожидания.</p>}{jobs.map(j=><button key={j.id} className="sd-job" onClick={()=>edit(j.target)}><b>{j.name}</b><small>{j.status}</small><span>Открыть исходную карточку ↗</span></button>)}</aside></div>
 {entity&&<div className="sd-overlay"><div ref={editorRef} tabIndex={-1} className="sd-editor" role="dialog" aria-modal="true" aria-label={`${LABELS[entity.kind]}: ${entity.name}`}><div className="sd-editor-heading"><small>{LABELS[entity.kind]} · отдельная карточка</small><button onClick={back}>{trail.length?'← Назад к сцене':'Закрыть ✕'}</button></div><label>Название<input value={entity.name} onChange={e=>patch(entity.id,{name:e.target.value})}/></label><label>{entity.kind==='scene'?'Сценарий сцены':'Описание и неизменные особенности'}<textarea rows={4} value={entity.description} onChange={e=>patch(entity.id,{description:e.target.value})}/></label>
 {scene&&<><h3>Участники и бэкграунд</h3><div className="sd-links">{scene.characters.map(id=>mini(id,nested))}{mini(scene.location,nested)}</div>{entity.kind==='scene'&&<fieldset><legend>Кто участвует в сцене</legend>{Object.values(data.units).filter(u=>u.kind==='character').map(u=><label key={u.id} className="sd-check"><input type="checkbox" checked={scene.characters.includes(u.id)} onChange={e=>{const checked=e.target.checked;setData(d=>({...d,scenes:d.scenes.map(s=>s.id===scene.id?{...s,characters:checked?[...s.characters,u.id]:s.characters.filter(id=>id!==u.id)}:s)}))}}/>{u.name}</label>)}</fieldset>}</>}
 {entity.kind==='character'&&<p className="sd-muted">Голос: не назначен. В рабочей версии здесь будет карточка ElevenLabs / Fish Audio.</p>}
 <h3>Референсы</h3><label className="sd-upload">＋ Прикрепить фото<input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={e=>{void attach(entity.id,e.target.files).catch(()=>setNotice('Не удалось прочитать референс.'));e.target.value=''}}/></label><div className="sd-refs">{entity.refs.map((src,i)=><div key={i}><img src={src} alt={`Референс ${i+1}`}/><button aria-label={`Удалить референс ${i+1}`} onClick={()=>patch(entity.id,{refs:entity.refs.filter((_,j)=>i!==j)})}>✕</button></div>)}</div>
 <label>Что создать или изменить<textarea rows={2} value={entity.request} onChange={e=>patch(entity.id,{request:e.target.value})} placeholder="Например: сделать свет мягче, остальное сохранить"/></label><button className="sd-primary" disabled={jobs.some(j=>j.target===entity.id&&!j.done)} onClick={()=>generate(entity.id)}>Отправить в GPT · промпт + изображение (демо)</button>
 <h3>Рабочее изображение и варианты</h3>{!entity.variants.length&&<p>Изображений пока нет. Отправь задание выше.</p>}<div className="sd-variants">{entity.variants.map((v,i)=><article key={v.id} className={entity.selected===v.id?'sd-selected':''}><img src={v.image} alt={`Вариант ${i+1} — ${entity.name}`}/><small>Вариант {i+1}{entity.selected===v.id?' · Основной':''}</small><button disabled={entity.selected===v.id} onClick={()=>patch(entity.id,{selected:v.id,prompt:v.prompt,video:false})}>{entity.selected===v.id?'Выбран':'Сделать основным'}</button><details><summary>Промпт варианта</summary><p>{v.prompt}</p></details></article>)}</div>
 <label>Промпт выбранного изображения<textarea rows={3} value={entity.prompt} onChange={e=>patch(entity.id,{prompt:e.target.value})} placeholder="Выбери полученный вариант — его промпт появится здесь"/></label>
 {entity.kind==='frame'&&<section className="sd-video"><h3>Оживить выбранное фото</h3><p>Демо: камера закреплена, герой слегка улыбается. В рабочей версии здесь будет выбор видеомодели и стоимости.</p><button disabled={!imageOf(entity)||jobs.some(j=>j.target===entity.id&&!j.done)} onClick={()=>generate(entity.id,true)}>▶ Оживить · демо</button>{entity.video&&<div className="sd-video-stage"><img src={imageOf(entity)} alt="Условная анимация выбранного кадра"/><span>ДЕМО · условный наезд, не видеофайл</span></div>}</section>}
 {entity.kind==='scene'&&scene&&<section><h3>Кадры сцены</h3><div className="sd-links">{scene.frames.map(id=><button key={id} onClick={()=>nested(id)}>{data.units[id].name} ↗</button>)}<button onClick={()=>addFrame(scene.id)}>＋ Добавить кадр</button></div></section>}
 <p className="sd-muted">Изменения сохраняются только в памяти этого демо до перезагрузки страницы.</p></div></div>}
 </div></div>;
}
