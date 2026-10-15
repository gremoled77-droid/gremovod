import {useEffect,useId,useRef,useState,type ReactNode} from 'react';
import catalogue from '../../backend/prompt_setup_catalogue.json';
import {PresetTile} from './StudioControls';
import './prompt-start-menu.css';

export type PromptSetup=Partial<Record<'render_style'|'genre'|'capture'|'lens'|'view'|'focus'|'palette'|'mood'|'finish',string>>;
type Group=(typeof catalogue.groups)[number];
export function setupBasis(value?:PromptSetup){return Object.fromEntries(catalogue.groups.filter(g=>value?.[g.id as keyof PromptSetup]).map(g=>[g.id,value![g.id as keyof PromptSetup]])) as PromptSetup}
export function hasSetup(value?:PromptSetup){return Object.keys(setupBasis(value)).length>0}

function SetupArt({group,id}:{group:string;id:string}){
  const uid=useId().replace(/:/g,''),warm=['warm-vintage','warm','amber-blue','film-35'].includes(id),cool=id==='cool',grain=['film-8','film-35','textured'].includes(id);
  const accent=warm?'#e3b97a':cool?'#82bbd5':'#b6c9b7';
  return <svg viewBox="0 0 240 125" aria-hidden="true"><defs><linearGradient id={uid}><stop stopColor={accent}/><stop offset="1" stopColor="#465c61"/></linearGradient></defs><rect width="240" height="125" fill={warm?'#292b24':'#19262a'}/><path d="M0 90L60 66H165L240 98V125H0Z" fill="#2e4141"/><path d="M17 18H53V87H17ZM183 10H220V93H183Z" fill={cool?'#3b6577':'#435e5d'}/><circle cx="198" cy="31" r={id==='halation'?17:7} fill={accent} opacity={id==='halation'?.45:.85}/>{id==='halation'&&<circle cx="198" cy="31" r="8" fill="#fce3b8"/>}{id.includes('anamorphic')&&<path d="M130 31H240" stroke="#9bcbd3" strokeWidth="2" opacity=".7"/>}<ellipse cx="115" cy="130" rx="42" ry="46" fill={'url(#'+uid+')'}/><ellipse cx="115" cy="57" rx={id==='graphic'?19:21} ry="28" fill={'url(#'+uid+')'}/><path d="M96 49Q92 22 119 27L138 45" fill="#304442"/><path d="M106 56h3m14 0h3M109 73q7 4 14 0" stroke="#273d3c" strokeWidth="2" fill="none"/>{grain&&<g fill="#f2dfb2" opacity=".25">{Array.from({length:24},(_,i)=><circle key={i} cx={(i*37)%240} cy={(i*23)%125} r="1"/>)}</g>}<text x="10" y="115" fill="#bbcbc3" fontSize="8">{catalogue.groups.find(g=>g.id===group)?.title} · условный пример</text></svg>;
}

export default function PromptStartMenu({value,onChange,disabled=false,extra}:{value?:PromptSetup;onChange:(value:PromptSetup)=>void;disabled?:boolean;extra?:ReactNode}){
  const selected=setupBasis(value),[active,setActive]=useState<Group|null>(null),titleId=useId(),dialogRef=useRef<HTMLDivElement>(null),opener=useRef<HTMLButtonElement|null>(null);
  const chosen=catalogue.groups.flatMap(g=>{const p=g.options.find(p=>p.id===selected[g.id as keyof PromptSetup]);return p?[{group:g.title,...p}]:[]});
  useEffect(()=>{if(!active)return;const previous=document.activeElement as HTMLButtonElement|null;opener.current=previous;dialogRef.current?.querySelector<HTMLButtonElement>('button')?.focus();return()=>opener.current?.focus()},[active]);
  return <div className="prompt-start-menu">
    <p className="start-explanation">Выбери основу кадра. GPT соберёт из параметров, задания и референсов готовый промпт в отдельной ветке.</p>
    <div className="start-parameter-grid">{extra}{catalogue.groups.map(group=>{const current=group.options.find(p=>p.id===selected[group.id as keyof PromptSetup]);return <button type="button" className={'start-parameter'+(current?' configured':'')} key={group.id} disabled={disabled} aria-haspopup="dialog" aria-label={group.title+': '+(current?.title||'По заданию')} onClick={()=>setActive(group)}><span className="start-parameter-icon" aria-hidden="true">{group.icon}</span><span><small>{group.title}</small><b>{current?.title||'По заданию'}</b></span></button>})}</div>
    <div className="start-base-footer"><span>{chosen.length?`Параметров обработки выбрано: ${chosen.length}`:'Незаполненные параметры GPT возьмёт из задания и референсов'}</span>{chosen.length>0&&<button type="button" disabled={disabled} onClick={()=>onChange({})}>Сбросить обработку</button>}</div>
    {chosen.length>0&&<details className="start-base-summary"><summary>База для GPT · проверить выбор</summary><ul>{chosen.map(p=><li key={p.group}><b>{p.group}: {p.title}.</b> {p.description}</li>)}</ul><p>Это исходные условия. GPT согласует их с композицией, светом и каноном персонажей и напишет связный промпт для выбранной модели.</p></details>}
    {active&&<div className="start-picker-backdrop" onClick={e=>{if(e.target===e.currentTarget)setActive(null)}}><div ref={dialogRef} className="start-picker director-studio" role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();setActive(null)}if(e.key==='Tab'){const buttons=dialogRef.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');if(!buttons?.length)return;const first=buttons[0],last=buttons[buttons.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}}}>
      <div className="start-picker-title"><div><small>ОСНОВА ПРОМПТА</small><h3 id={titleId}>{active.title}</h3></div><button type="button" onClick={()=>setActive(null)}>Готово</button></div>
      <div className="start-picker-grid"><PresetTile title="По заданию и референсу" subtitle="Без дополнительного указания" selected={!selected[active.id as keyof PromptSetup]} onClick={()=>{onChange({...selected,[active.id]:''});setActive(null)}}/><>{active.options.map(p=><PresetTile key={p.id} title={p.title} subtitle={p.description} selected={selected[active.id as keyof PromptSetup]===p.id} disabled={disabled} onClick={()=>{onChange({...selected,[active.id]:p.id});setActive(null)}}><SetupArt group={active.id} id={p.id}/></PresetTile>)}</></div>
      <p className="director-help">Авторские описания визуального результата. Миниатюры условные; выбор не запускает генерацию.</p>
    </div></div>}
  </div>;
}
