import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readdir,readFile,writeFile,rm,access} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {startStudio,tempDir,waitFor,pngData} from './support/studio.mjs';
const brief={prompt:'TEST ONLY',images:[{role:'base',data:pngData}],ratio:'3:4',resolution:'1K'};
test('запуск переживает повреждённый файл задачи и чистит остатки аварийных запросов',{timeout:20000},async()=>{
 const dir=await tempDir(),good=randomUUID(),bad=randomUUID();
 await writeFile(path.join(dir,bad+'.json'),'{оборванный json');
 await writeFile(path.join(dir,good+'.json'),JSON.stringify({id:good,model:'qwen',prompt:'ok',state:'success',files:[],created:new Date().toISOString()}));
 await writeFile(path.join(dir,randomUUID()+'.request.json'),'{"base64Data":"секретное фото"}');
 await writeFile(path.join(dir,randomUUID()+'.response.json'),'{}');
 await writeFile(path.join(dir,good+'.json.abcd1234.tmp'),'частичная запись');
 const s=await startStudio({port:4340,dir});
 try{
  const history=await s.get('/api/history');assert.deepEqual(history.map(j=>j.id),[good]);
  const left=await readdir(dir);assert.ok(!left.some(n=>/\.(request|response)\.json$|\.tmp$/.test(n)),'остатки удалены: '+left);
  assert.ok(left.includes(bad+'.json'),'повреждённый файл не удаляется, его можно разобрать вручную');
  assert.match(s.stderr(),/повреждённый файл задачи/);
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
test('imagegen: задача видна исполнителю только после записи task.txt и референсов',{timeout:20000},async()=>{
 const dir=await tempDir(),s=await startStudio({port:4341,dir});
 try{
  const waiting=s.post('/api/worker/wait',{worker:'imagegen-1'}).then(r=>r.json());
  const created=await (await s.post('/api/imagegen',brief)).json();
  const claim=await waiting;assert.equal(claim.job.id,created.id);
  await access(claim.taskPath);await access(path.join(dir,created.id,'reference-1.png'));
  assert.match(await readFile(claim.taskPath,'utf8'),/reference-1\.png/);
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
test('imagegen: зависшая задача переходит в ошибку и освобождает слот',{timeout:25000},async()=>{
 const dir=await tempDir(),s=await startStudio({port:4342,dir,env:{STUDIO_STALE_MS:'800'}});
 try{
  const first=await (await s.post('/api/imagegen',brief)).json();
  const claim=await (await s.post('/api/worker/wait',{worker:'imagegen-1'})).json();assert.equal(claim.job.id,first.id);
  // Исполнитель «пропал»: progress.json не появляется. Вторая задача ждёт, пока слот занят.
  const second=await (await s.post('/api/imagegen',brief)).json();
  const next=await (await s.post('/api/worker/wait',{worker:'imagegen-1'})).json();
  assert.equal(next.job.id,second.id,'слот освободился после таймаута');
  const stale=await s.job(first.id);assert.equal(stale.state,'error');assert.match(stale.error,/не подавал признаков жизни/);
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
