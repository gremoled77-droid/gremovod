import {useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

export type CharacterVersion={id:string;name:string;working_asset_id?:string;version_history?:string[]};
export type ReplacementControls={character?:CharacterVersion;onReplaced?:(character:CharacterVersion,source:string)=>void};

export default function ReplaceCharacterButton({projectId,assetId,character,onReplaced}:{projectId:string;assetId:string}&ReplacementControls){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const current=character?.working_asset_id===assetId;
  const replace=async()=>{if(!character)return;setBusy(true);setError('');try{
    const result=await responseJson(await apiFetch(`/api/characters/${encodeURIComponent(projectId)}/${encodeURIComponent(character.id)}/replace`,{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_id:assetId})}));
    onReplaced?.(result.character,assetId);
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  return <><button disabled={busy||current||!character||!projectId} title={character?`Сделать рабочим образом персонажа «${character.name}». Предыдущая версия сохранится.`:'Выбери персонажа в Character Vault'} onClick={()=>void replace()}>
    {busy?'Сохранение…':current?'✓ Рабочий образ':`Заменить персонажа${character?' · '+character.name:''}`}</button>{error&&<span role="alert">{error}</span>}</>;
}
