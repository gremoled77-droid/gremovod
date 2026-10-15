import {useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
type Preview={task_id:string;status:string;provider_input:Record<string,unknown>;different_fields:string[];note:string};
export default function RecoverJob({jobId,onRecovered}:{jobId:string;onRecovered:()=>void}){
  const [id,setId]=useState(''),[preview,setPreview]=useState<Preview|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const recover=async(approved:boolean)=>{setBusy(true);setError('');try{
    const result=await responseJson(await apiFetch(`/api/jobs/${jobId}/recover`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:id.trim(),approved})}));
    if(result.attached)onRecovered();else setPreview(result);
  }catch(e){setError(String(e))}finally{setBusy(false)}};
  return <div><p>Ответ об отправке потерян. Найди уже созданную задачу в <a href="https://piapi.ai/workspace/tasks-history" target="_blank" rel="noreferrer">истории PiAPI</a> и укажи её Task ID.</p><label>Task ID провайдера<input value={id} onChange={e=>{setId(e.target.value);setPreview(null)}}/></label><button disabled={busy||!id.trim()} onClick={()=>void recover(false)}>Проверить существующую задачу</button>
    {preview&&<><p>{preview.note} Статус: {preview.status}.</p><pre>{JSON.stringify(preview.provider_input,null,2)}</pre>{preview.different_fields.length>0&&<p>Отличаются поля: {preview.different_fields.join(', ')}. Сверь их вручную перед привязкой.</p>}<button disabled={busy} onClick={()=>void recover(true)}>Параметры проверены — привязать без повторной генерации</button></>}{error&&<p role="alert">{error}</p>}</div>;
}
