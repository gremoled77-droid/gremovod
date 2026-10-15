// Превращает сбой вызова kie-access/request.ps1 в понятное сообщение.
// Текст ответа KIE (msg) сохраняется; ключ и пути не попадают в сообщение.
const clip=(s,n=300)=>s.length>n?s.slice(0,n-1)+'…':s;
export function describeKieError(e){
 const stderr=String(e?.stderr||'').trim(),lines=stderr?stderr.split(/\r?\n/):[];
 const apiAt=lines.findIndex(l=>/KIE API error \d+/.test(l));
 if(apiAt>=0){
  // PowerShell может перенести длинное сообщение на несколько строк: берём до служебных строк.
  const out=[];
  for(let i=apiAt;i<lines.length;i++){const l=lines[i].trim();if(!l||/^(At |\+|CategoryInfo|FullyQualifiedErrorId)/.test(l))break;out.push(l);}
  return clip(out.join(' ').replace(/^.*?(KIE API error)/,'$1'));
 }
 const http=stderr.match(/KIE HTTP request failed \([^\r\n]+\)/)?.[0];
 if(http)return clip(http);
 if(e?.code==='ENOENT'&&/spawn/.test(String(e.syscall||'')))return 'Не найден powershell.exe. Студия рассчитана на Windows PowerShell.';
 if(e?.killed||e?.signal||e?.code==='ETIMEDOUT')return 'KIE не ответил за 150 секунд. Если это была отправка задачи, проверьте кабинет KIE перед повтором.';
 if(/connect\.ps1|KIE_API_KEY/.test(stderr))return 'Ключ KIE не настроен: запустите kie-access\\connect.ps1.';
 if(/not valid for use in specified state/i.test(stderr))return 'Не удалось расшифровать ключ KIE: запускайте студию тем же Windows-пользователем, который его сохранил.';
 if(e?.code==='ENOENT')return 'KIE-обёртка не создала файл ответа.';
 if(e instanceof SyntaxError)return 'KIE вернул нечитаемый ответ.';
 const first=lines.find(l=>l.trim());
 return first?clip('Не удалось выполнить запрос к KIE: '+first.trim()):'Не удалось выполнить запрос к KIE. Проверьте ключ и сеть.';
}
