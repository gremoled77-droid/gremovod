import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source=await readFile(new URL('./src/projectMerge.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2020,target:ts.ScriptTarget.ES2020}}).outputText;
const {mergeProject}=await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));

test('server prompt survives saving a local brief from an older tab',()=>{
  const base={brief:'Original',prompts:{},characters:[]};
  const local={...base,brief:'User edit'};
  const remote={...base,prompts:{'gpt-image-2.5':'New generated prompt'}};
  const result=mergeProject(base,local,remote);
  assert.deepEqual(result.conflicts,[]);
  assert.equal(result.value.brief,'User edit');
  assert.equal(result.value.prompts['gpt-image-2.5'],'New generated prompt');
});
test('competing edits stop and retain the local text for recovery',()=>{
  const result=mergeProject({brief:'Original'},{brief:'Local'},{brief:'Remote'});
  assert.deepEqual(result.conflicts,['brief']);
  assert.equal(result.value.brief,'Local');
});
test('character replacement is preserved when only the brief changed locally',()=>{
  const base={brief:'Original',characters:[{id:'grem',working_asset_id:'old'}]};
  const remote={...base,characters:[{id:'grem',working_asset_id:'new'}]};
  const result=mergeProject(base,{...base,brief:'User edit'},remote);
  assert.deepEqual(result.conflicts,[]);
  assert.equal(result.value.characters[0].working_asset_id,'new');
});
