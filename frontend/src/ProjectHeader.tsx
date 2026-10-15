import {Pencil,Save} from 'lucide-react';

type Props={id:string;name:string;editing:boolean;dirty:boolean;busy:boolean;onName:(name:string)=>void;onEdit:()=>void;onCancel:()=>void;onSave:()=>void};

export default function ProjectHeader({id,name,editing,dirty,busy,onName,onEdit,onCancel,onSave}:Props){
  const showInput=!id||editing;
  return <section className="project-header" aria-label="Название и сохранение проекта">
    {showInput?<label>Название проекта<input autoFocus value={name} maxLength={200} disabled={busy} onChange={e=>onName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!busy&&name.trim()){e.preventDefault();onSave()}else if(e.key==='Escape'&&id&&!busy){e.preventDefault();onCancel()}}}/></label>:<><small>Проект</small><div className="project-title-row"><h3>{name}</h3><button className="project-edit" aria-label="Редактировать название проекта" title="Редактировать название проекта" disabled={busy} onClick={onEdit}><Pencil size={16}/></button></div></>}
    {dirty&&id&&<small className="project-unsaved" role="status">Есть несохранённые изменения</small>}
    {(showInput||dirty)&&<div className="project-save-actions"><button className="primary" disabled={busy||!name.trim()} onClick={onSave}><Save size={15}/>{busy?'Сохранение…':'Сохранить'}</button>{id&&editing&&<button disabled={busy} onClick={onCancel}>Отмена</button>}</div>}
  </section>;
}
