import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {randomUUID} from 'node:crypto';
import {access,mkdir,readFile,rm,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {startStudio,tempDir,waitFor,png,pngData,root} from './support/studio.mjs';

const exec=promisify(execFile);
const brief={prompt:'TEST ONLY: preserve reference',images:[{role:'base',data:pngData}],ratio:'3:4',resolution:'1K'};
const client=(s,threadId,args=[])=>exec(process.execPath,['worker-client.mjs',...args],{
 cwd:root,windowsHide:true,timeout:5000,env:{...process.env,STUDIO_URL:s.base,CODEX_THREAD_ID:threadId}
});

test('active Codex chats resolve their workers and receive the existing handoff',{timeout:20000},async()=>{
 const dir=await tempDir(),legacyId=randomUUID();
 const legacy={id:legacyId,model:'imagegen',state:'waiting_native',prompt:'legacy',handoff:'old manual handoff',created:'2020-01-01T00:00:00.000Z'};
 await mkdir(path.join(dir,legacyId));
 await writeFile(path.join(dir,legacyId+'.json'),JSON.stringify(legacy));
 // Completed API jobs exercise observe delivery without invoking KIE.
 for(const model of ['qwen','seedream']){
  const id=randomUUID();
  const threadId=model==='qwen'?'01a13d63-d334-72b3-b3fa-7ac32ca3cb17':'01a13d63-e266-7512-b9df-a454fe4cc3e7';
  await writeFile(path.join(dir,id+'.json'),JSON.stringify({id,model,state:'success',files:[],workerThreadId:threadId,created:new Date().toISOString()}));
 }
 const s=await startStudio({port:4343,dir});
 try{
  assert.equal(s.config.dispatch,'long-poll');
  for(const worker of ['imagegen-1','imagegen-2']){
   const created=await (await s.post('/api/imagegen',brief)).json();
   const result=JSON.parse((await client(s,s.config.workers[worker].threadId)).stdout);
   assert.equal(result.mode,'generate');assert.equal(result.job.id,created.id);
   assert.equal(result.job.workerSlot,worker);
   assert.equal(result.job.workerThreadId,s.config.workers[worker].threadId);
   assert.equal(result.job.state,'native_preparing');
   assert.match(await readFile(result.taskPath,'utf8'),/reference-1\.png/);
   await access(path.join(dir,created.id,'reference-1.png'));
   assert.equal(JSON.parse(await readFile(path.join(dir,created.id,'worker.lock'),'utf8')).worker,worker);
  }
  for(const worker of ['qwen','seedream']){
   const result=JSON.parse((await client(s,s.config.workers[worker].threadId)).stdout);
   assert.equal(result.mode,'observe');assert.equal(result.job.model,worker);
  }
  assert.equal((await s.job(legacyId)).state,'waiting_native');
  assert.equal((await s.job(legacyId)).handoff,legacy.handoff);
  await assert.rejects(access(path.join(dir,legacyId,'worker.lock')),{code:'ENOENT'});
  // Legacy manual jobs still accept a result file, without ever being claimed.
  await writeFile(path.join(dir,legacyId,'result.png'),png);
  await waitFor(async()=>(await s.job(legacyId)).state==='success');
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});

test('explicit workers still work and unknown chats fail before claiming a job',{timeout:10000},async()=>{
 const dir=await tempDir(),s=await startStudio({port:4344,dir});
 try{
  const created=await (await s.post('/api/imagegen',brief)).json();
  await assert.rejects(client(s,'unconfigured-chat'),e=>{
   assert.match(JSON.parse(e.stdout).message,/configured Codex chat/);return true;
  });
  assert.equal((await s.job(created.id)).state,'native_queued');
  const result=JSON.parse((await client(s,'unconfigured-chat',['imagegen-1'])).stdout);
  assert.equal(result.job.id,created.id);assert.equal(result.mode,'generate');
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
