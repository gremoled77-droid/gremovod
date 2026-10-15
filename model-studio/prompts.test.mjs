import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {makeInput,preparePrompt} from './prompts.mjs';
const brief={prompt:'Замени фон на серую студию. Текст «Привет» сохранить.',images:[{role:'base'},{role:'identity'},{role:'style'}],ratio:'3:4',resolution:'2K'};
test('provider inputs obey the verified KIE schemas',async()=>{
 for(const model of ['seedream','qwen']){
  const doc=JSON.parse((await readFile(new URL(`./${model}-schema.json`,import.meta.url),'utf8')).replace(/^\uFEFF/,''));
  const schema=doc.data.openapi.paths['/api/v1/jobs/createTask'].post.requestBody.content['application/json'].schema.properties.input;
  const input=makeInput(model,brief,['https://example.com/a.png','https://example.com/b.png','https://example.com/c.png']);
  for(const key of schema.required)assert.ok(key in input,`${model}: required ${key}`);
  for(const [key,value] of Object.entries(input)){assert.ok(key in schema.properties,`${model}: unsupported ${key}`);const p=schema.properties[key];if(p.enum)assert.ok(p.enum.includes(value));}
  assert.ok(input.prompt.length<=schema.properties.prompt.maxLength);
 }
});
test('adaptation preserves exact brief and reference order without hidden rewriting',()=>{
 for(const model of ['imagegen','seedream','qwen']){const p=preparePrompt(model,brief);assert.ok(p.includes(brief.prompt));assert.ok(p.indexOf('Изображение 1:')<p.indexOf('Изображение 2:'));assert.match(p,/идентичность/);assert.match(p,/только стиль/);}
 assert.equal(makeInput('qwen',brief,[]).enhance_prompt,false);
 assert.notEqual(preparePrompt('seedream',brief),preparePrompt('qwen',brief));
 assert.equal(makeInput('seedream',{...brief,preparedPrompt:'Пользовательский итоговый промпт'},[]).prompt,'Пользовательский итоговый промпт');
 assert.throws(()=>makeInput('qwen',{...brief,preparedPrompt:'a'.repeat(5001)},[]),/5000/);
});
