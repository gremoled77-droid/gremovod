// Общие помощники для тестов: запуск изолированного сервера на временной папке.
import {spawn} from 'node:child_process';
import {mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
export const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7m8AAAAASUVORK5CYII=','base64');
export const pngData='data:image/png;base64,'+png.toString('base64');
export const tempDir=()=>mkdtemp(path.join(os.tmpdir(),'studio-test-'));
export const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export async function waitFor(fn,ms=8000){const end=Date.now()+ms;do{const v=await fn();if(v)return v;await sleep(100);}while(Date.now()<end);throw Error('waitFor: время ожидания истекло');}
export async function startStudio({port,dir,env={}}){
 const child=spawn(process.execPath,['server.mjs'],{cwd:root,env:{...process.env,STUDIO_PORT:String(port),STUDIO_DATA_DIR:dir,STUDIO_POLL_MS:'150',STUDIO_RETRY_MS:'300',...env},windowsHide:true,stdio:['ignore','pipe','pipe']});
 let out='',err='';child.stderr.on('data',d=>{err+=d;});
 await new Promise((resolve,reject)=>{child.stdout.on('data',d=>{out+=d;if(out.includes('Model Studio:'))resolve();});child.once('error',reject);child.once('exit',code=>reject(Error('сервер завершился с кодом '+code+'\n'+err)));});
 const base=`http://127.0.0.1:${port}`,config=await fetch(base+'/api/config').then(r=>r.json());
 const post=(p,b)=>fetch(base+p,{method:'POST',headers:{'Content-Type':'application/json',Origin:base,'X-Studio-Token':config.token},body:JSON.stringify(b)});
 const get=p=>fetch(base+p).then(r=>r.json());
 const job=async id=>(await get('/api/history')).find(j=>j.id===id);
 const stop=async()=>{if(child.exitCode===null&&!child.killed){const done=new Promise(r=>child.once('exit',r));child.kill();await done;}};
 return {base,config,post,get,job,stop,stderr:()=>err};
}
