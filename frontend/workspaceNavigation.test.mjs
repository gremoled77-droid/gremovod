import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
async function module(file){const source=await readFile(new URL(file,import.meta.url),'utf8');const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2020,target:ts.ScriptTarget.ES2020}}).outputText;return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))}
const {readWorkspaceRoute,workspaceHash}=await module('./src/workspaceRoute.ts');
const {startActivityFeed}=await module('./src/activityFeed.ts');
test('workspace route keeps the chosen project and separate media pages',()=>{
 for(const mode of ['create','video','audio','storyboard'])assert.deepEqual(readWorkspaceRoute(workspaceHash('frame_project-1',mode)),{projectId:'frame_project-1',mode,frameId:''});
 for(const hash of ['#/project/a/unknown','#/project/../../x/create','#https://evil.test','#/project/a/create?pay=true','#/project/a/storyboard/frame/','#/project/a/storyboard/frame/../x','#/project/a/storyboard/scene/f1'])assert.equal(readWorkspaceRoute(hash),null);
});
test('frame focus survives switching tools and ignores unsafe ids',()=>{
 const hash=workspaceHash('p1','storyboard','f_2-a');
 assert.equal(hash,'#/project/p1/storyboard/frame/f_2-a');
 assert.deepEqual(readWorkspaceRoute(hash),{projectId:'p1',mode:'storyboard',frameId:'f_2-a'});
 assert.deepEqual(readWorkspaceRoute(workspaceHash('p1','audio','f_2-a')),{projectId:'p1',mode:'audio',frameId:'f_2-a'});
 assert.equal(workspaceHash('p1','storyboard','../x'),'#/project/p1/storyboard');
 assert.equal(workspaceHash('p1','storyboard'),'#/project/p1/storyboard');
});
test('a late response cannot deliver results after leaving the project',async()=>{
 let resolve;const received=[];
 const feed=startActivityFeed('/api/activity?project_id=old',()=>new Promise(done=>{resolve=done}),items=>received.push(items),()=>{});
 feed.stop();resolve(new Response(JSON.stringify({version:'1',changed:true,items:[{id:'old-job'}]})));
 await new Promise(done=>setImmediate(done));assert.deepEqual(received,[]);
});
test('refresh cancels the waiting GET and immediately fetches new results',async()=>{
 const requests=[];const received=[];let resolveInitial;
 const first=new Promise(done=>{resolveInitial=done});
 const feed=startActivityFeed('/api/productions/p/activity',async(url,{signal})=>{
  requests.push(url);
  if(requests.length===1)return first;
  if(requests.length===2)return new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));
  return new Response(JSON.stringify({version:'new',changed:true,items:[{id:'ready'}]}));
 },items=>{received.push(items);if(items[0]?.id==='ready')feed.stop()},()=>{});
 resolveInitial(new Response(JSON.stringify({version:'old',changed:true,items:[]})));
 await new Promise(done=>setImmediate(done));
 assert.equal(requests[0],'/api/productions/p/activity?since=&wait=0');
 assert.match(requests[1],/since=old&wait=20/);
 feed.refresh();await new Promise(done=>setImmediate(done));
 assert.match(requests[2],/since=&wait=0/);
 assert.deepEqual(received.at(-1),[{id:'ready'}]);feed.stop();
});
