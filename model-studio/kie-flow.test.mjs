import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,rm} from 'node:fs/promises';
import path from 'node:path';
import {startStudio,tempDir,waitFor,png,pngData,root} from './support/studio.mjs';
const mock=path.join(root,'support','mock-kie.mjs');
const brief=model=>({model,prompt:'TEST ONLY: сохранить сцену',images:[{role:'base',data:pngData},{role:'style',data:pngData}],ratio:'3:4',resolution:'1K'});
const lines=async f=>(await readFile(f,'utf8').catch(()=>'')).split('\n').filter(Boolean);
async function withStudio(port,scenario,fn,extra={}){
 const dir=await tempDir(),log=path.join(dir,'mock.log'),s=await startStudio({port,dir,env:{STUDIO_KIE_MOCK:mock,MOCK_SCENARIO:scenario,MOCK_LOG:log,...extra}});
 try{await fn(s,dir,log);}finally{await s.stop();await rm(dir,{recursive:true,force:true});}
}
test('успешный цикл KIE: проверка кредитов → загрузки → одна отправка → опрос → файл',{timeout:20000},async()=>{
 await withStudio(4330,'success',async(s,dir,log)=>{
  const r=await s.post('/api/generate',brief('qwen'));assert.equal(r.status,202);const {id}=await r.json();
  const done=await waitFor(async()=>{const j=await s.job(id);return j.state==='success'&&j;});
  assert.equal(done.media.length,1);assert.equal(done.taskId,'task-mock-1');assert.ok(done.preparedPrompt.includes('TEST ONLY'));
  assert.deepEqual(Buffer.from(await (await fetch(s.base+done.media[0])).arrayBuffer()),png);
  const calls=(await lines(log)).filter(l=>l!=='/api/v1/jobs/recordInfo');
  assert.deepEqual(calls,['/api/v1/chat/credit','/api/file-base64-upload','/api/file-base64-upload','/api/v1/jobs/createTask','download https://files.example.test/out.png']);
 });
});
test('ошибка отправки: текст KIE виден, платная отправка не повторяется',{timeout:20000},async()=>{
 await withStudio(4331,'create-error',async(s,dir,log)=>{
  const {id}=await (await s.post('/api/generate',brief('seedream'))).json();
  const j=await waitFor(async()=>{const x=await s.job(id);return x.state==='error'&&x;});
  assert.match(j.error,/KIE API error 402: Insufficient credits/);assert.match(j.error,/Отправка могла быть принята/);
  await new Promise(r=>setTimeout(r,800));
  assert.equal((await lines(log)).filter(l=>l==='/api/v1/jobs/createTask').length,1);
 });
});
test('недостаточно кредитов: ни загрузок, ни отправки',{timeout:20000},async()=>{
 await withStudio(4332,'success',async(s,dir,log)=>{
  const {id}=await (await s.post('/api/generate',brief('seedream'))).json();
  const j=await waitFor(async()=>{const x=await s.job(id);return x.state==='error'&&x;});
  assert.match(j.error,/Недостаточно кредитов/);assert.deepEqual(await lines(log),['/api/v1/chat/credit']);
 },{MOCK_CREDITS:'1'});
});
test('отказ KIE при генерации: понятная ошибка, повторного запуска нет',{timeout:20000},async()=>{
 await withStudio(4333,'fail',async(s,dir,log)=>{
  const {id}=await (await s.post('/api/generate',brief('qwen'))).json();
  const j=await waitFor(async()=>{const x=await s.job(id);return x.state==='fail'&&x;});
  assert.equal(j.error,'Content policy violation');
  assert.equal((await lines(log)).filter(l=>l==='/api/v1/jobs/createTask').length,1);
 });
});
test('перезапуск сервера: задача с taskId дорабатывается без повторной платной отправки',{timeout:30000},async()=>{
 const dir=await tempDir(),log=path.join(dir,'mock.log');let id;
 let s=await startStudio({port:4334,dir,env:{STUDIO_KIE_MOCK:mock,MOCK_SCENARIO:'hang',MOCK_LOG:log}});
 try{
  id=(await (await s.post('/api/generate',brief('qwen'))).json()).id;
  await waitFor(async()=>{const j=await s.job(id);return j.taskId&&['waiting','generating'].includes(j.state);});
  await s.stop();
  s=await startStudio({port:4334,dir,env:{STUDIO_KIE_MOCK:mock,MOCK_SCENARIO:'success',MOCK_LOG:log}});
  const j=await waitFor(async()=>{const x=await s.job(id);return x.state==='success'&&x;});
  assert.equal(j.media.length,1);
  assert.equal((await lines(log)).filter(l=>l==='/api/v1/jobs/createTask').length,1);
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
