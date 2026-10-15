// Run from a dedicated Codex chat. This never starts a paid request by itself.
const requestedWorker=process.argv[2];
const base=process.env.STUDIO_URL||'http://127.0.0.1:4317';
try{
 const c=await fetch(base+'/api/config').then(r=>r.json());
 const worker=requestedWorker||Object.keys(c.workers).find(name=>c.workers[name].threadId===process.env.CODEX_THREAD_ID);
 if(!Object.hasOwn(c.workers,worker))throw Error('Expected a configured Codex chat or explicit worker name');
 const r=await fetch(base+'/api/worker/wait',{method:'POST',headers:{Origin:base,'Content-Type':'application/json','X-Studio-Token':c.token},body:JSON.stringify({worker}),signal:AbortSignal.timeout(55000)});
 const result=await r.json();if(!r.ok)throw Error(result.error||'Worker request failed');
 console.log(JSON.stringify(result));
}catch(e){console.log(JSON.stringify({offline:true,message:e.message}));process.exitCode=1;}
