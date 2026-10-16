import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
async function module(file){const source=await readFile(new URL(file,import.meta.url),'utf8');const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2020,target:ts.ScriptTarget.ES2020}}).outputText;return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))}
const {readWorkspaceRoute,workspaceHash}=await module('./src/workspaceRoute.ts');
const {startActivityFeed}=await module('./src/activityFeed.ts');
test('workspace route keeps the chosen project and separate media pages',()=>{
 for(const mode of ['create','video','audio','storyboard'])assert.deepEqual(readWorkspaceRoute(workspaceHash('frame_project-1',mode)),{projectId:'frame_project-1',mode});
 for(const hash of ['#/project/a/unknown','#/project/../../x/create','#https://evil.test','#/project/a/create?pay=true'])assert.equal(readWorkspaceRoute(hash),null);
});
test('a late response cannot deliver results after leaving the project',async()=>{
 let resolve;const received=[];
 const feed=startActivityFeed('old',()=>new Promise(done=>{resolve=done}),items=>received.push(items),()=>{});
 feed.stop();resolve(new Response(JSON.stringify({version:'1',changed:true,items:[{id:'old-job'}]})));
 await new Promise(done=>setImmediate(done));assert.deepEqual(received,[]);
});
test('refresh cancels the waiting GET and immediately fetches new results',async()=>{
 const requests=[];const received=[];let resolveInitial;
 const first=new Promise(done=>{resolveInitial=done});
 const feed=startActivityFeed('project',async(url,{signal})=>{
  requests.push(url);
  if(requests.length===1)return first;
  if(requests.length===2)return new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));
  return new Response(JSON.stringify({version:'new',changed:true,items:[{id:'ready'}]}));
 },items=>{received.push(items);if(items[0]?.id==='ready')feed.stop()},()=>{});
 resolveInitial(new Response(JSON.stringify({version:'old',changed:true,items:[]})));
 await new Promise(done=>setImmediate(done));
 assert.match(requests[1],/since=old&wait=20/);
 feed.refresh();await new Promise(done=>setImmediate(done));
 assert.match(requests[2],/since=&wait=0/);
 assert.deepEqual(received.at(-1),[{id:'ready'}]);feed.stop();
});
