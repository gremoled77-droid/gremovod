import http from 'node:http';
import {readFile,writeFile,mkdir,readdir,rename,rm} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {EventEmitter} from 'node:events';
import {preparePrompt,makeInput} from './prompts.mjs';
import {describeKieError} from './kie-errors.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),data=process.env.STUDIO_DATA_DIR||path.join(root,'data');
await mkdir(data,{recursive:true});
const port=Number(process.env.STUDIO_PORT||4317);
if(!Number.isInteger(port)||port<1024||port>65535)throw Error('Invalid studio port');
const exec=promisify(execFile),origin=`http://127.0.0.1:${port}`,token=randomUUID();
const models={seedream:'seedream/5-pro-image-to-image',qwen:'qwen2-1/image-to-image'};
const jobs=new Map(),working=new Set(),terminal=new Set(['success','fail','error']);
const events=new EventEmitter();events.setMaxListeners(20);
const slots={
 'imagegen-1':{model:'imagegen',threadId:'01a13d5d-5ce1-7411-b619-d6da973ca788'},
 'imagegen-2':{model:'imagegen',threadId:'01a13d63-ef48-7022-a59a-1ad4a553411d'},
 qwen:{model:'qwen',threadId:'01a13d63-d334-72b3-b3fa-7ac32ca3cb17'},
 seedream:{model:'seedream',threadId:'01a13d63-e266-7512-b9df-a454fe4cc3e7'}
};
const observed=new Map();
const POLL_MS=Number(process.env.STUDIO_POLL_MS||5000),RETRY_MS=Number(process.env.STUDIO_RETRY_MS||30000),STALE_MS=Number(process.env.STUDIO_STALE_MS||600000);
const draftFile=path.join(data,'draft.json'),draftImagesFile=path.join(data,'draft-images.json');
// Фоновые задачи не должны ронять процесс: ошибки логируются, а не превращаются в unhandledRejection.
const bg=(promise,label)=>promise.catch(e=>console.error(label+':',e?.message||e));
process.on('unhandledRejection',e=>console.error('Необработанная ошибка:',e?.message||e));
// Атомарная запись с уникальным tmp-файлом и повтором rename: на Windows антивирус/индексатор может кратко держать файл.
async function atomicWrite(file,content){
 const tmp=`${file}.${randomUUID().slice(0,8)}.tmp`;await writeFile(tmp,content);
 for(let attempt=0;;attempt++){
  try{await rename(tmp,file);return;}
  catch(e){if(attempt>=5||!['EPERM','EBUSY','EACCES'].includes(e.code)){await rm(tmp,{force:true});throw e;}await new Promise(r=>setTimeout(r,50*(attempt+1)));}
 }
}
const psEnv={...process.env,PSModulePath:[path.join(process.env.SystemRoot||'C:\\Windows','System32/WindowsPowerShell/v1.0/Modules'),path.join(process.env.ProgramFiles||'C:\\Program Files','WindowsPowerShell/Modules')].join(';')};
async function kieReal(api,body,upload=false){
 const id=randomUUID(),input=path.join(data,id+'.request.json'),output=path.join(data,id+'.response.json');
 const args=['-NoProfile','-ExecutionPolicy','Bypass','-File',path.resolve(root,'../kie-access/request.ps1'),'-Path',api,'-OutputFile',output];
 if(body){await writeFile(input,JSON.stringify(body));args.push('-Method','Post','-BodyFile',input);}if(upload)args.push('-Upload');
 try{await exec('powershell.exe',args,{windowsHide:true,env:psEnv,maxBuffer:1024*1024,timeout:150000});return JSON.parse((await readFile(output,'utf8')).replace(/^\uFEFF/,''));}
 catch(e){throw Error(describeKieError(e));}
 finally{await Promise.all([rm(input,{force:true}),rm(output,{force:true})]);}
}
// Тестовая подмена KIE (без платных запросов): STUDIO_KIE_MOCK=<путь к модулю с экспортами kie и download>.
const mock=process.env.STUDIO_KIE_MOCK?await import(pathToFileURL(path.resolve(process.env.STUDIO_KIE_MOCK)).href):null;
const kie=mock?.kie||kieReal;
const RATIOS=['1:1','4:3','3:4','16:9','9:16','2:3','3:2','21:9'];
function checkParams(b){if(!RATIOS.includes(b.ratio)||!['1K','2K'].includes(b.resolution))throw Error('Неверные параметры.');}
function checkImages(images,{data=true,min=1}={}){
 if(!Array.isArray(images)||images.length<min||images.length>10)throw Error('Добавьте от 1 до 10 референсов.');
 for(const i of images){
  if(!i||typeof i!=='object')throw Error('Неверные референсы.');
  if(data&&(typeof i.data!=='string'||!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(i.data)||Buffer.from(i.data.split(',')[1],'base64').length>10*1024*1024))throw Error('Только PNG, JPEG, WebP до 10 МБ.');
 }
}
function validate(b,native=false){
 if(typeof b.prompt!=='string'||b.prompt.trim().length<(native?1:4)||b.prompt.length>5000)throw Error(native?'Заполните промпт (до 5000 символов).':'Промпт: от 4 до 5000 символов.');
 checkImages(b.images);checkParams(b);
 if(b.preparedPrompt!==undefined&&(typeof b.preparedPrompt!=='string'||b.preparedPrompt.trim().length<4||b.preparedPrompt.length>5000))throw Error('Промпт модели: от 4 до 5000 символов.');
}
// «Подготовить промпты» использует только промпт, роли и формат: сами картинки не нужны.
function validatePrepare(b){
 if(typeof b.prompt!=='string'||b.prompt.trim().length<4||b.prompt.length>5000)throw Error('Промпт: от 4 до 5000 символов.');
 checkImages(b.images,{data:false});checkParams(b);
}
// Черновик: текст сохраняется отдельно от картинок, поэтому правка текста не пересылает и не перезаписывает base64.
function validateDraft(b){
 if(typeof b.prompt!=='string'||b.prompt.length>5000)throw Error('Промпт: до 5000 символов.');
 checkParams(b);
 if(b.images!==undefined)checkImages(b.images,{min:0});
}
async function saveDraft(b){
 await atomicWrite(draftFile,JSON.stringify({prompt:b.prompt,ratio:b.ratio,resolution:b.resolution}));
 if(Array.isArray(b.images))await atomicWrite(draftImagesFile,JSON.stringify(b.images.map(({data,role})=>({data,role:typeof role==='string'?role:'reference'}))));
}
async function loadDraft(){
 let meta;try{meta=JSON.parse(await readFile(draftFile,'utf8'));}catch{return null;}
 let images=[];try{images=JSON.parse(await readFile(draftImagesFile,'utf8'));}catch{}
 return {...meta,images:Array.isArray(images)?images:[]};
}
async function save(job){await atomicWrite(path.join(data,job.id+'.json'),JSON.stringify(job,null,2));jobs.set(job.id,job);events.emit('changed');}
async function trySave(job){try{await save(job);}catch(e){console.error('Не удалось сохранить задачу '+job.id+':',e.message);}}
async function takeJob(slotName){
 const slot=slots[slotName];if(!slot)throw Error('Неизвестный исполнитель.');
 if(slot.model!=='imagegen'){
  const seen=observed.get(slotName)||new Map();observed.set(slotName,seen);
  for(const j of [...jobs.values()].sort((a,b)=>a.created.localeCompare(b.created))){
   if(j.workerThreadId!==slot.threadId)continue;const key=j.state+JSON.stringify(j.files||[]);
   if(seen.get(j.id)===key)continue;seen.set(j.id,key);return {mode:'observe',job:view(j)};
  }return null;
 }
 if([...jobs.values()].some(j=>j.workerSlot===slotName&&!terminal.has(j.state)))return null;
 const j=[...jobs.values()].sort((a,b)=>a.created.localeCompare(b.created)).find(j=>j.model==='imagegen'&&j.state==='native_queued'&&!working.has(j.id));
 if(!j)return null;
 working.add(j.id);j.workerSlot=slotName;j.workerThreadId=slot.threadId;j.state='native_preparing';j.claimed=new Date().toISOString();
 try{
  try{await writeFile(path.join(data,j.id,'worker.lock'),JSON.stringify({worker:slotName,claimed:new Date().toISOString()}),{flag:'wx'});}
  catch(e){if(e.code==='EEXIST'){j.state='error';j.error='Задача уже была захвачена исполнителем. Повторная генерация заблокирована.';await trySave(j);return null;}j.state='error';j.error='Не удалось захватить задачу: '+e.message;await trySave(j);return null;}
  j.progress={stage:'preparing',message:'Задание получено исполнителем '+slotName,updated:new Date().toISOString()};await save(j);
  return {mode:'generate',job:view(j),taskPath:path.join(data,j.id,'task.txt'),resultPath:path.join(data,j.id,'result.png'),progressPath:path.join(data,j.id,'progress.json')};
 }finally{working.delete(j.id);}
}
async function waitJob(slotName,res){
 const deadline=Date.now()+50000;
 while(Date.now()<deadline&&!res.destroyed){
  let wake;const event=new Promise(resolve=>{wake=resolve;});events.once('changed',wake);
  const timer=setTimeout(wake,Math.min(5000,deadline-Date.now()));
  try{const next=await takeJob(slotName);if(next)return next;await event;}
  finally{clearTimeout(timer);events.off('changed',wake);}
 }
 return {idle:true};
}
function imageType(bytes){if(bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))return 'png';if(bytes[0]===255&&bytes[1]===216&&bytes[2]===255)return 'jpeg';if(bytes.toString('ascii',0,4)==='RIFF'&&bytes.toString('ascii',8,12)==='WEBP')return 'webp';throw Error('Полученный файл не является PNG, JPEG или WebP.');}
async function downloadReal(url){
 const u=new URL(url);if(u.protocol!=='https:'||u.username||u.password)throw Error('KIE вернул недопустимый URL результата.');
 const r=await fetch(u,{signal:AbortSignal.timeout(90000)});if(!r.ok)throw Error('Не удалось получить файл KIE: HTTP '+r.status);
 const chunks=[];let size=0;for await(const c of r.body){size+=c.length;if(size>40*1024*1024)throw Error('Файл результата превышает 40 МБ.');chunks.push(c);}const bytes=Buffer.concat(chunks);return {bytes,ext:imageType(bytes)};
}
const download=mock?.download||downloadReal;
async function run(job,b){
 working.add(job.id);
 try{
  const input=makeInput(job.model,b,[]);job.preparedPrompt=input.prompt;
  const credit=await kie('/api/v1/chat/credit');const estimate=job.model==='seedream'?(b.resolution==='2K'?14:7)+Math.max(0,b.images.length-1)*0.5:(b.resolution==='2K'?8:4);
  if(typeof credit.data!=='number'||credit.data<estimate)throw Error('Недостаточно кредитов KIE для этой задачи.');
  job.state='uploading';await save(job);
  for(const i of b.images){const r=await kie('/api/file-base64-upload',{base64Data:i.data,uploadPath:'images/model-studio',fileName:randomUUID()+'.'+i.data.match(/^data:image\/(\w+)/)[1]},true);if(!r.data?.downloadUrl)throw Error('KIE не вернул URL референса.');input.image_urls.push(r.data.downloadUrl);}
  job.state='submitting';await save(job);
  const r=await kie('/api/v1/jobs/createTask',{model:models[job.model],input});if(!r.data?.taskId)throw Error('KIE не вернул ID задачи.');
  job.taskId=r.data.taskId;job.state='waiting';await save(job);
 }catch(e){job.error=e.message+(job.state==='submitting'?' Отправка могла быть принята KIE: проверьте кабинет перед повтором.':'');job.state='error';await trySave(job);}finally{working.delete(job.id);}
}
async function poll(job){
 if(working.has(job.id)||terminal.has(job.state))return;working.add(job.id);
 try{
  if(job.model==='imagegen'){
   try{
    const progress=JSON.parse(await readFile(path.join(data,job.id,'progress.json'),'utf8'));
    const stages={preparing:'native_preparing',generating:'native_generating',error:'error'};
    if(stages[progress.stage]){job.state=stages[progress.stage];job.progress={stage:progress.stage,message:String(progress.message||'').slice(0,1000),updated:progress.updated};if(progress.stage==='error')job.error=job.progress.message;await save(job);}
   }catch(e){if(e.code!=='ENOENT'&&!(e instanceof SyntaxError))throw e;}
   const p=path.join(data,job.id,'result.png');let bytes;try{bytes=await readFile(p);}catch(e){if(e.code!=='ENOENT')throw e;}
   if(!bytes){
    // Нет результата: если исполнитель взял задачу, но давно не обновлял progress.json, задача считается зависшей, слот освобождается.
    if(['native_preparing','native_generating'].includes(job.state)){
     const last=Date.parse(job.progress?.updated||job.claimed||job.created);
     if(Number.isFinite(last)&&Date.now()-last>STALE_MS){
      const span=STALE_MS>=60000?Math.round(STALE_MS/60000)+' мин':Math.round(STALE_MS/1000)+' с';
      job.state='error';job.error=`Исполнитель imagegen не подавал признаков жизни более ${span}. Задача остановлена; повторная генерация автоматически не запускалась.`;
      job.progress={stage:'error',message:job.error,updated:new Date().toISOString()};await save(job);
     }
    }
    return;
   }
   imageType(bytes);job.files=['result.png'];job.state='success';job.progress={stage:'complete',message:'Изображение готово',updated:new Date().toISOString()};job.completed=new Date().toISOString();await save(job);return;
  }
  if(!job.taskId)return;
  if(!job.remoteUrls){const r=await kie('/api/v1/jobs/recordInfo?taskId='+encodeURIComponent(job.taskId));const d=r.data;
   job.state=d.state;job.pollError=null;job.lastChecked=new Date().toISOString();
   if(d.state==='fail'){job.error=d.failMsg||'Генерация не удалась.';await save(job);return;}
   if(d.state!=='success'){await save(job);return;}
   const result=d.response||JSON.parse(d.resultJson||'{}');job.remoteUrls=(result.resultUrls||[]).filter(x=>typeof x==='string'&&x.startsWith('https://'));
   if(!job.remoteUrls.length){job.state='error';job.error='KIE завершил задачу без URL изображения.';await save(job);return;}
  }
  job.state='downloading';await save(job);await mkdir(path.join(data,job.id),{recursive:true});
  const files=[];for(let i=0;i<job.remoteUrls.length;i++){const {bytes,ext}=await download(job.remoteUrls[i]);const name=`result-${i+1}.${ext}`;const p=path.join(data,job.id,name);await atomicWrite(p,bytes);files.push(name);}
  job.files=files;job.urls=undefined;job.state='success';job.pollError=null;job.completed=new Date().toISOString();await save(job);
 }catch(e){job.pollError=e.message;job.nextCheck=Date.now()+RETRY_MS;await trySave(job);}finally{working.delete(job.id);}
}
for(const name of await readdir(data)){
 // Остатки аварийно прерванных запросов (с base64 фото) и недозаписанные tmp-файлы удаляются.
 if(/\.(request|response)\.json$|\.tmp$/.test(name)){await rm(path.join(data,name),{force:true});continue;}
 if(!/^[\da-f-]{36}\.json$/.test(name))continue;
 let job;
 try{
  job=JSON.parse(await readFile(path.join(data,name),'utf8'));
  if(!job||job.id+'.json'!==name||typeof job.model!=='string'||typeof job.created!=='string')throw Error('неверная структура');
 }catch(e){console.warn(`Пропущен повреждённый файл задачи ${name}: ${e.message}`);continue;}
 if(job.model!=='imagegen'&&!job.taskId&&!terminal.has(job.state)){job.state='error';job.error='Сервер остановлен до сохранения ID. Проверьте кабинет KIE перед повтором.';}
 if(job.state==='success'&&!job.files&&job.urls?.length){job.remoteUrls=job.urls;job.state='downloading';}
 jobs.set(job.id,job);
}
// Старый формат черновика хранил картинки внутри draft.json: разделяем на два файла.
try{const old=JSON.parse(await readFile(draftFile,'utf8'));if(Array.isArray(old.images))await saveDraft({prompt:old.prompt,ratio:old.ratio,resolution:old.resolution,images:old.images});}catch{}
setInterval(()=>{for(const j of jobs.values())if((!j.nextCheck||j.nextCheck<Date.now())&&!terminal.has(j.state))bg(poll(j),'poll');},POLL_MS);
async function json(req){let chunks=[],size=0;for await(const c of req){size+=c.length;if(size>140e6)throw Error('Загрузка слишком большая.');chunks.push(c);}return JSON.parse(Buffer.concat(chunks).toString());}
const view=j=>({...j,media:(j.files||[]).map(n=>`/media/${j.id}/${n}`)});
http.createServer(async(req,res)=>{
 const send=(status,obj)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(obj));};
 try{
  if(req.headers.host!==`127.0.0.1:${port}`)return send(403,{error:'Недопустимый Host'});const u=new URL(req.url,origin);
  if(req.method==='POST'&&(req.headers.origin!==origin||req.headers['x-studio-token']!==token))return send(403,{error:'Обновите страницу студии.'});
  if(req.method==='GET'&&u.pathname==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});return res.end(await readFile(path.join(root,'index.html')));}
  if(req.method==='GET'&&u.pathname==='/app.mjs'){res.writeHead(200,{'Content-Type':'text/javascript; charset=utf-8','Cache-Control':'no-store'});return res.end(await readFile(path.join(root,'app.mjs')));}
  const media=u.pathname.match(/^\/media\/([\da-f-]{36})\/(result(?:-\d+)?\.(png|jpeg|webp))$/);
  if(req.method==='GET'&&media){const j=jobs.get(media[1]);if(!j?.files?.includes(media[2]))return send(404,{error:'Файл не найден'});res.writeHead(200,{'Content-Type':'image/'+media[3],'X-Content-Type-Options':'nosniff','Content-Disposition':`${u.searchParams.has('download')?'attachment':'inline'}; filename="${j.model}-${media[2]}"`});return res.end(await readFile(path.join(data,media[1],media[2])));}
  if(req.method==='GET'&&u.pathname==='/api/config')return send(200,{token,models,nativeAutoStart:true,workers:slots,dispatch:'long-poll'});
  if(req.method==='POST'&&u.pathname==='/api/worker/wait'){const b=await json(req);if(!slots[b.worker])throw Error('Неизвестный исполнитель.');const next=await waitJob(b.worker,res);if(!res.destroyed)return send(200,next);return;}
  if(req.method==='GET'&&u.pathname==='/api/draft')return send(200,await loadDraft());
  if(req.method==='POST'&&u.pathname==='/api/draft'){const b=await json(req);validateDraft(b);await saveDraft(b);return send(200,{saved:true});}
  if(req.method==='GET'&&u.pathname==='/api/history')return send(200,[...jobs.values()].sort((a,b)=>b.created.localeCompare(a.created)).slice(0,100).map(view));
  if(req.method==='POST'&&u.pathname==='/api/check'){const r=await kie('/api/v1/chat/credit');return send(200,{credits:r.data});}
  if(req.method==='POST'&&u.pathname==='/api/prepare'){const b=await json(req);validatePrepare(b);return send(200,Object.fromEntries(['imagegen','seedream','qwen'].map(m=>[m,preparePrompt(m,b)])));}
  if(req.method==='POST'&&u.pathname==='/api/generate'){
   const b=await json(req);validate(b);if(!models[b.model])throw Error('Выберите Seedream или Qwen.');
   makeInput(b.model,b,[]);
   const job={id:randomUUID(),model:b.model,prompt:b.prompt,preparedPrompt:b.preparedPrompt||preparePrompt(b.model,b),ratio:b.ratio,resolution:b.resolution,state:'queued',workerThreadId:slots[b.model].threadId,created:new Date().toISOString()};jobs.set(job.id,job);await save(job);send(202,view(job));bg(run(job,b),'run');return;
  }
  if(req.method==='POST'&&u.pathname==='/api/imagegen'){
   const b=await json(req);validate(b,true);const id=randomUUID(),dir=path.join(data,id),prompt=b.preparedPrompt||preparePrompt('imagegen',b);
   const job={id,model:'imagegen',prompt:b.prompt,preparedPrompt:prompt,ratio:b.ratio,state:'native_queued',workerThreadId:slots['imagegen-1'].threadId,created:new Date().toISOString()};
   await mkdir(dir);
   try{
    await saveDraft(b);
    const files=[];for(let i=0;i<b.images.length;i++){const file=path.join(dir,`reference-${i+1}.`+b.images[i].data.match(/^data:image\/(\w+)/)[1]);await writeFile(file,Buffer.from(b.images[i].data.split(',')[1],'base64'));files.push(file);}
    const resultPath=path.join(dir,'result.png');
    const text=`Сгенерируй одно изображение встроенным imagegen по локальному заданию Model Studio ${id}. Сначала просмотри референсы, затем передай их в imagegen. Не заменяй imagegen другим API.\n\nРеференсы:\n${files.join('\n')}\n\n${prompt}\n\nПосле генерации сохрани или скопируй итоговый PNG в файл:\n${resultPath}\nИспользуй файловые инструменты для копирования готового файла. Если результат пришёл только inline и локального файла нет, сообщи об этом; не выдумывай путь. Студия автоматически обнаружит result.png и покажет его рядом с Seedream и Qwen. Не запускай другие генерации.`;
    job.handoff=text;await writeFile(path.join(dir,'task.txt'),text);
    // Задача становится видна исполнителям только сейчас, когда референсы и task.txt уже на диске.
    await save(job);
    return send(200,{...view(job),text,path:path.join(dir,'task.txt')});
   }catch(e){jobs.delete(id);await rm(dir,{recursive:true,force:true});throw e;}
  }
  if(req.method==='POST'&&u.pathname==='/api/poll'){const b=await json(req),j=jobs.get(b.id);if(!j)throw Error('Задача не найдена.');return send(200,view(j));}
  send(404,{error:'Не найдено'});
 }catch(e){send(400,{error:e.message});}
}).listen(port,'127.0.0.1',()=>console.log('Model Studio: '+origin));
