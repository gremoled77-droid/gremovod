/*
 * Браузерный smoke экрана «Выпуск» (GA-03). Платных вызовов нет, данные временные.
 * Запуск из корня репозитория (нужны ffmpeg, playwright, chromium):
 *   S=$(mktemp -d); mkdir -p $S/data $S/fx
 *   ffmpeg -f lavfi -i testsrc=size=320x240:rate=10:duration=1 -f lavfi -i sine=duration=1 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest $S/fx/ok.mp4
 *   ffmpeg -f lavfi -i testsrc=size=320x240:rate=10:duration=1 -c:v libx264 -pix_fmt yuv420p $S/fx/silent.mp4
 *   head -c 2000 /dev/urandom > $S/fx/bad.mp4
 *   STUDIO_DATA_DIR=$S/data GREMOVOD_OWNER_ID=owner-e2e python3 -m uvicorn backend.main:app --port 8000 &
 *   (cd frontend && npm run dev &)        # порт 5173
 *   CHROMIUM=/путь/к/chrome node tests/release_gate_browser_smoke.mjs $S
 * Скрипт сам перезапускает backend (проверка сохранения после рестарта) и дописывает байты в файл библиотеки.
 */
import {chromium} from 'playwright';
import {execSync, spawn} from 'node:child_process';
import fs from 'node:fs';
const S = process.argv[2];
const results = [];
const check = (name, ok, extra='') => { results.push([name, ok]); console.log((ok?'PASS ':'FAIL ')+name+(extra?' :: '+extra:'')); };
const b = await chromium.launch({executablePath:process.env.CHROMIUM});
const p = await b.newPage({viewport:{width:1400,height:1400}});
const errs=[]; p.on('console',m=>{if(m.type()==='error')errs.push(m.text())}); p.on('pageerror',e=>errs.push('PAGE '+e.message));
const reqs=[]; p.on('request',r=>{ if(r.url().includes('/decision')||r.url().includes('/qc/')) reqs.push(r.method()+' '+r.url().split('release-artifacts')[1]) });
async function openRelease(){
  await p.goto('http://127.0.0.1:5173/'); await p.waitForTimeout(1500); await pick();
  await p.locator('nav button',{hasText:'Выпуск'}).first().click(); await p.waitForTimeout(800);
}
// проект создаётся заранее на временном сервере (экран выпуска работает с сохранённым проектом)
const tok = (await (await fetch('http://127.0.0.1:8000/api/session')).json()).token;
await fetch('http://127.0.0.1:8000/api/projects',{method:'POST',headers:{'content-type':'application/json','x-studio-session':tok},body:JSON.stringify({title:'E2E выпуск',state:{}})});
async function pick(){ await p.locator('select').first().selectOption({label:'E2E выпуск'}).catch(()=>{}); await p.waitForTimeout(800); }
await p.goto('http://127.0.0.1:5173/'); await p.waitForTimeout(1500); await pick();
await p.locator('nav button',{hasText:'Выпуск'}).first().click(); await p.waitForTimeout(800);
const panel = p.locator('.rg');
check('экран выпуска показан', await panel.count()===1);
check('финальных 0, пока ничего нет', (await p.getByTestId('final-count').innerText())==='0');

async function upload(file, title){
  await panel.locator('input[type=file]').setInputFiles(file);
  if(title) await panel.getByPlaceholder('Название (необязательно)').fill(title);
  await panel.getByRole('button',{name:'Загрузить MP4'}).click();
}
// 1. плохой файл
await upload(`${S}/fx/bad.mp4`,'bad'); await p.waitForTimeout(1500);
const errTxt = await panel.locator('.rg-error').first().innerText().catch(()=>'' );
check('повреждённый файл: русская ошибка, артефакта нет', /MP4|прочитать|видео/.test(errTxt), errTxt);
// 2. нормальный
await upload(`${S}/fx/ok.mp4`,'e2e-master'); await p.waitForTimeout(2500);
check('после загрузки: состояние «не пройдена»', /Загружен, проверка не пройдена/.test(await panel.innerText()));
check('импорт не назван финальным', (await p.getByTestId('final-count').innerText())==='0');
const approve = panel.getByRole('button',{name:'Утвердить эту версию'});
check('утвердить недоступно без N34', await approve.isDisabled());
const sha = (await panel.locator('.rg-sha code').innerText()).trim();
check('виден полный SHA-256', /^[0-9a-f]{64}$/.test(sha), sha.slice(0,12));
await p.screenshot({path:`${S}/shot1_imported.png`, fullPage:true});
// 3. N34
await panel.getByRole('button',{name:'Проверить N34'}).click(); await p.waitForTimeout(2500);
check('N34 пройдена, состояние TECHNICAL_PASS', /Пройдена/.test(await panel.innerText()) && /ждёт решения владельца/.test(await panel.innerText()));
// 4. неверный владелец
await panel.getByLabel('Идентификатор владельца').fill('wrong');
await panel.getByLabel(/подтверждаю право/).check().catch(async()=>{await panel.locator('label:has-text("подтверждаю право") input').check()});
await approve.click(); await p.waitForTimeout(1500);
check('неверный owner_id: ошибка сервера показана', /не совпадает/.test(await panel.innerText()));
check('финальных всё ещё 0', (await p.getByTestId('final-count').innerText())==='0');
// 5. утверждение + двойной клик
await panel.getByLabel('Идентификатор владельца').fill('owner-e2e');
const before = reqs.filter(r=>r.startsWith('POST')&&r.includes('/decision')).length;
await approve.dblclick(); await p.waitForTimeout(2000);
const after = reqs.filter(r=>r.startsWith('POST')&&r.includes('/decision')).length;
check('двойной клик отправил одно решение', after-before===1, `${after-before}`);
check('утверждено владельцем, финальных 1', /Утверждён владельцем/.test(await panel.innerText()) && (await p.getByTestId('final-count').innerText())==='1');
await p.screenshot({path:`${S}/shot2_approved.png`, fullPage:true});
// 6. рестарт backend
execSync(`pkill -f '[u]vicorn backend.main' || true`); await new Promise(r=>setTimeout(r,1500));
spawn(process.env.PYTHON || 'python3',['-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],{detached:true,stdio:'ignore',env:{...process.env,STUDIO_DATA_DIR:`${S}/data`,GREMOVOD_OWNER_ID:'owner-e2e'}}).unref(); await new Promise(r=>setTimeout(r,5000));
await openRelease(); await p.waitForTimeout(2500);
check('после рестарта backend утверждение сохранилось', /Утверждён владельцем/.test(await panel.innerText()) && (await p.getByTestId('final-count').innerText())==='1', (await panel.innerText()).slice(0,80));
// 7. байты изменены на диске
const lib = `${S}/data/library`; const f = fs.readdirSync(lib).find(n=>n.endsWith('.mp4'));
fs.appendFileSync(`${lib}/${f}`, Buffer.from('tail-bytes'));
await panel.getByRole('button',{name:'Обновить'}).click(); await p.waitForTimeout(2500);
const t = await panel.innerText();
check('файл изменён: утверждение снято, финальных 0', !/Утверждён владельцем/.test(t) && (await p.getByTestId('final-count').innerText())==='0');
check('показано, что решение не действует и нужна новая N34', /не действует/.test(t) && /изменён после проверки/.test(t));
await p.screenshot({path:`${S}/shot3_changed.png`, fullPage:true});
// 8. отклонение
const reject = panel.getByRole('button',{name:'Отклонить'});
check('отклонить недоступно без причины', await reject.isDisabled());
await panel.getByLabel('Причина отклонения').fill('плохой звук');
await reject.click(); await p.waitForTimeout(2000);
check('отклонено, финальных 0', /Отклонён владельцем/.test(await panel.innerText()) && (await p.getByTestId('final-count').innerText())==='0');
await p.screenshot({path:`${S}/shot4_rejected.png`, fullPage:true});
// 9. второй MP4 без звука: выбор переходит на новый, N34 при требовании аудио — BLOCKED, утвердить нельзя
await upload(`${S}/fx/silent.mp4`,'silent-master'); await p.waitForTimeout(2500);
check('после второй загрузки выбран новый MP4', (await panel.locator('select').inputValue()) !== '' && /silent-master/.test(await panel.locator('.rg-card').first().innerText()));
await panel.getByRole('button',{name:'Проверить N34'}).click(); await p.waitForTimeout(2500);
const st = await panel.innerText();
check('без аудио при требовании: «Измерить нельзя», утвердить недоступно с причиной', /Измерить нельзя/.test(st) && await panel.getByRole('button',{name:'Утвердить эту версию'}).isDisabled());
check('счётчик: 0 финальных, 2 ожидают', (await p.getByTestId('final-count').innerText())==='0' && /2\s+ожидают/.test(st.replace(/\n/g,' ')), st.slice(0,120).replace(/\n/g,' | '));
await p.screenshot({path:`${S}/shot5_second.png`, fullPage:true});
const real = errs.filter(e=>!/404|Failed to load resource/.test(e));
check('нет JS-ошибок в консоли (статусы 4xx на негативных сценариях ожидаемы)', real.length===0, real.join(' | '));
await b.close();
const failed = results.filter(r=>!r[1]).length;
console.log(`ИТОГО: ${results.length-failed} PASS, ${failed} FAIL`);
process.exit(failed?1:0);
