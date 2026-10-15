// Подмена KIE для тестов: STUDIO_KIE_MOCK=support/mock-kie.mjs. Платных запросов нет.
// Сценарий задаёт MOCK_SCENARIO: success | fail | hang | create-error. MOCK_LOG — файл журнала вызовов.
import {appendFile} from 'node:fs/promises';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7m8AAAAASUVORK5CYII=','base64');
const log=line=>process.env.MOCK_LOG?appendFile(process.env.MOCK_LOG,line+'\n'):undefined;
let uploads=0,polls=0;
export async function kie(api){
 await log(api.split('?')[0]);
 const scenario=process.env.MOCK_SCENARIO||'success';
 if(api==='/api/v1/chat/credit')return {code:200,data:Number(process.env.MOCK_CREDITS||100)};
 if(api==='/api/file-base64-upload'){uploads++;return {code:200,data:{downloadUrl:`https://files.example.test/ref-${uploads}.png`}};}
 if(api==='/api/v1/jobs/createTask'){
  if(scenario==='create-error')throw Error('KIE API error 402: Insufficient credits');
  return {code:200,data:{taskId:'task-mock-1'}};
 }
 if(api.startsWith('/api/v1/jobs/recordInfo')){
  polls++;
  if(scenario==='hang'||polls<2)return {code:200,data:{state:'generating'}};
  if(scenario==='fail')return {code:200,data:{state:'fail',failMsg:'Content policy violation'}};
  return {code:200,data:{state:'success',resultJson:JSON.stringify({resultUrls:['https://files.example.test/out.png']})}};
 }
 throw Error('mock: неожиданный путь '+api);
}
export async function download(url){await log('download '+url);return {bytes:png,ext:'png'};}
