import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,rm,stat} from 'node:fs/promises';
import path from 'node:path';
import {startStudio,tempDir,pngData} from './support/studio.mjs';
const meta={ratio:'3:4',resolution:'1K'};
test('текст черновика сохраняется отдельно от картинок и не стирает их',{timeout:20000},async()=>{
 const dir=await tempDir(),s=await startStudio({port:4319,dir});
 try{
  assert.equal(await s.get('/api/draft'),null);
  // Пустой промпт и картинки: раньше такой черновик отклонялся.
  assert.equal((await s.post('/api/draft',{prompt:'',...meta,images:[{data:pngData,role:'base'}]})).status,200);
  // Правка текста без поля images не трогает картинки.
  assert.equal((await s.post('/api/draft',{prompt:'привет',...meta})).status,200);
  let d=await s.get('/api/draft');assert.equal(d.prompt,'привет');assert.equal(d.images.length,1);assert.equal(d.images[0].role,'base');
  assert.ok((await stat(path.join(dir,'draft.json'))).size<200,'draft.json остаётся маленьким');
  // Пустой список очищает картинки.
  assert.equal((await s.post('/api/draft',{prompt:'привет',...meta,images:[]})).status,200);
  assert.deepEqual((await s.get('/api/draft')).images,[]);
  // Валидация.
  assert.equal((await s.post('/api/draft',{prompt:'x',ratio:'7:7',resolution:'1K'})).status,400);
  assert.equal((await s.post('/api/draft',{prompt:'x',...meta,images:[{data:'data:text/html;base64,AAAA',role:'base'}]})).status,400);
  assert.equal((await s.post('/api/draft',{prompt:'x',...meta,images:Array(11).fill({data:pngData,role:'base'})})).status,400);
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
test('старый формат черновика (картинки внутри draft.json) переносится при запуске',{timeout:20000},async()=>{
 const dir=await tempDir();
 await writeFile(path.join(dir,'draft.json'),JSON.stringify({prompt:'старый',...meta,images:[{data:pngData,role:'style'}]}));
 const s=await startStudio({port:4319,dir});
 try{
  const d=await s.get('/api/draft');assert.equal(d.prompt,'старый');assert.equal(d.images.length,1);assert.equal(d.images[0].role,'style');
  assert.equal(JSON.parse(await readFile(path.join(dir,'draft.json'),'utf8')).images,undefined);
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
test('«Подготовить промпты» принимает только роли без картинок',{timeout:20000},async()=>{
 const dir=await tempDir(),s=await startStudio({port:4319,dir});
 try{
  const r=await s.post('/api/prepare',{prompt:'Замени фон на студию',images:[{role:'base'},{role:'style'}],...meta});
  assert.equal(r.status,200);const p=await r.json();assert.ok(p.imagegen&&p.seedream&&p.qwen);assert.match(p.seedream,/Изображение 2: только стиль/);
  assert.equal((await s.post('/api/prepare',{prompt:'коротко',images:[],...meta})).status,400);
 }finally{await s.stop();await rm(dir,{recursive:true,force:true});}
});
