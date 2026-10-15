import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,writeFile,rm,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
test('native result is detected in background and served as a downloadable local file', {timeout:20000},async()=>{
 await mkdir(path.join(root,'data'),{recursive:true});const dir=await mkdtemp(path.join(root,'data','test-'));
 const child=spawn(process.execPath,['server.mjs'],{cwd:root,env:{...process.env,STUDIO_PORT:'4318',STUDIO_DATA_DIR:dir},windowsHide:true,stdio:['ignore','pipe','pipe']});
 try{
  await new Promise((resolve,reject)=>{child.stdout.once('data',resolve);child.once('error',reject);child.once('exit',code=>reject(Error('server exit '+code)));});
  const base='http://127.0.0.1:4318',config=await fetch(base+'/api/config').then(r=>r.json());
  const headers={'Content-Type':'application/json',Origin:base,'X-Studio-Token':config.token};
  const request=(p,b)=>fetch(base+p,{method:'POST',headers,body:JSON.stringify(b)});
  assert.equal((await fetch(base+'/api/imagegen',{method:'POST',body:'{}'})).status,403);
  assert.equal((await request('/api/generate',{prompt:'test',images:[],ratio:'3:4',resolution:'1K',model:'qwen'})).status,400);
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7m8AAAAASUVORK5CYII=','base64');
  const b={prompt:'TEST ONLY: preserve image',images:[{role:'base',data:'data:image/png;base64,'+png.toString('base64')}],ratio:'3:4',resolution:'1K'};
  const prepared=await request('/api/prepare',b).then(r=>r.json());assert.ok(prepared.qwen&&prepared.seedream&&prepared.imagegen);
  const waiting=request('/api/worker/wait',{worker:'imagegen-1'}).then(r=>r.json());
  const job=await request('/api/imagegen',b).then(r=>r.json());assert.ok(['native_queued','native_preparing'].includes(job.state));assert.ok(job.text.includes(path.join(dir,job.id,'result.png')));
  const claimed=await waiting;assert.equal(claimed.job.id,job.id);assert.equal(claimed.mode,'generate');
  const waiting2=request('/api/worker/wait',{worker:'imagegen-2'}).then(r=>r.json());
  const job2=await request('/api/imagegen',b).then(r=>r.json());const claimed2=await waiting2;assert.equal(claimed2.job.id,job2.id);assert.notEqual(claimed2.job.id,claimed.job.id);
  await writeFile(path.join(dir,job.id,'progress.json'),JSON.stringify({stage:'generating',message:'Test: generating',updated:new Date().toISOString()}));
  let progress;const progressDeadline=Date.now()+8000;
  do{progress=(await fetch(base+'/api/history').then(r=>r.json())).find(j=>j.id===job.id);if(progress.state==='native_generating')break;await new Promise(r=>setTimeout(r,300));}while(Date.now()<progressDeadline);
  assert.equal(progress.state,'native_generating');assert.equal(progress.progress.message,'Test: generating');
  await writeFile(path.join(dir,job.id,'result.png'),png);
  let result;const deadline=Date.now()+9000;
  do{result=(await fetch(base+'/api/history').then(r=>r.json())).find(j=>j.id===job.id);if(result.state==='success')break;await new Promise(r=>setTimeout(r,300));}while(Date.now()<deadline);
  assert.equal(result.state,'success');assert.equal(result.media.length,1);
  const file=await fetch(base+result.media[0]+'?download=1');assert.equal(file.headers.get('content-type'),'image/png');assert.match(file.headers.get('content-disposition'),/attachment/);assert.deepEqual(Buffer.from(await file.arrayBuffer()),png);
  assert.equal((await fetch(base+'/media/'+job.id+'/reference-1.png')).status,404);
 }finally{child.kill();await new Promise(resolve=>child.once('exit',resolve));await rm(dir,{recursive:true,force:true});}
});
