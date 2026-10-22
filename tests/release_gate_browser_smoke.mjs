/*
 * Браузерный smoke экрана «Выпуск» (GA-03, MiniMax).
 * Платных вызовов нет, данные временные, рабочая SQLite не трогается.
 *
 * Запуск из корня репозитория (нужны ffmpeg и playwright с chromium):
 *   node tests/release_gate_browser_smoke.mjs
 *
 * Стенд. Backend поднимается на отдельном порту (по умолчанию 8001) со своим
 * STUDIO_DATA_DIR — рабочая студия на 8000/5173 не трогается, чужие процессы
 * не останавливаются. Интерфейс отдаёт временный vite на своём порту (по
 * умолчанию 5174): порты 8000/5173 заняты рабочей студией, стенд их не берёт.
 * Список разрешённых Origin в backend/security.py фиксирован (127.0.0.1/localhost
 * на 5173 и 8000), поэтому прокси vite снимает заголовки origin и sec-fetch-site
 * — иначе стенд на своём порту получил бы 403. Backend слушает 8001, vite
 * проксирует /api на него.
 *
 * Переменные окружения:
 *   API_PORT=8001     порт временного backend
 *   PLAYWRIGHT_MODULE путь к модулю playwright, если он не в node_modules проекта
 *   CHROMIUM          путь к исполняемому файлу chromium, если нужен нестандартный
 *
 * Скрипт сам перезапускает backend (проверка сохранения решения после рестарта) и
 * дописывает байты в файл библиотеки (проверка снятия утверждения).
 */
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {execFileSync, spawn} from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const API_PORT = Number(process.env.API_PORT || 8001);
const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const NODE = process.execPath;
const OWNER = 'owner-e2e';
// порты рабочей студии (8000/5173) не занимаем: стенд живёт на своих
const UI_PORTS = (process.env.UI_PORTS || '5174,5175,5176,8081')
  .split(',')
  .map(port => Number(port.trim()))
  .filter(Boolean);

/** playwright может стоять локально, глобально или по явному пути. */
function loadPlaywright() {
  const candidates = [
    process.env.PLAYWRIGHT_MODULE,
    'playwright',
    process.env.APPDATA ? path.join(process.env.APPDATA, 'npm-global', 'node_modules', 'playwright') : null,
    '/usr/local/lib/node_modules/playwright',
    '/usr/lib/node_modules/playwright',
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch {
      /* ищем дальше */
    }
  }
  throw new Error('playwright не найден: установите его (npm i playwright) или задайте PLAYWRIGHT_MODULE');
}
const {chromium} = loadPlaywright();

const results = [];
const check = (name, ok, extra = '') => {
  results.push([name, ok]);
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra ? ' :: ' + extra : ''));
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function waitFor(url, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return true;
    } catch {
      /* сервер ещё не поднялся */
    }
    await sleep(400);
  }
  return false;
}

/** Порт свободен? Чужой процесс не трогаем — просто выбираем другой порт. */
function portFree(port) {
  return new Promise(resolve => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => server.close(() => resolve(true)));
    server.listen(port, '127.0.0.1');
  });
}

/** Остановить процесс вместе с потомками (Windows: taskkill, POSIX: группа процессов). */
function killTree(pid) {
  if (!pid) return;
  try {
    if (process.platform === 'win32')
      execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], {stdio: 'ignore'});
    else process.kill(-pid, 'SIGKILL');
  } catch {
    /* уже умер */
  }
}

let backend = null;
let frontend = null;

function startBackend(dataDir) {
  const child = spawn(
    PYTHON,
    ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(API_PORT)],
    {
      cwd: ROOT,
      detached: process.platform !== 'win32',
      stdio: 'ignore',
      windowsHide: true,
      env: {...process.env, STUDIO_DATA_DIR: dataDir, GREMOVOD_OWNER_ID: OWNER, PYTHONIOENCODING: 'utf-8'},
    }
  );
  child.unref();
  return child;
}

async function stopBackend() {
  if (!backend) return;
  killTree(backend.pid);
  backend = null;
  await sleep(1500); // порт должен освободиться перед следующим стартом
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'gremovod-ga03-'));
const dataDir = path.join(tmp, 'data');
const fxDir = path.join(tmp, 'fx');
fs.mkdirSync(dataDir, {recursive: true});
fs.mkdirSync(fxDir, {recursive: true});

function ffmpeg(args) {
  execFileSync('ffmpeg', ['-y', ...args], {stdio: 'ignore'});
}
ffmpeg([
  '-f',
  'lavfi',
  '-i',
  'testsrc=size=320x240:rate=10:duration=2',
  '-f',
  'lavfi',
  '-i',
  'sine=duration=2',
  '-c:v',
  'libx264',
  '-pix_fmt',
  'yuv420p',
  '-c:a',
  'aac',
  '-shortest',
  path.join(fxDir, 'ok.mp4'),
]);
ffmpeg([
  '-f',
  'lavfi',
  '-i',
  'testsrc=size=320x240:rate=10:duration=2',
  '-c:v',
  'libx264',
  '-pix_fmt',
  'yuv420p',
  path.join(fxDir, 'silent.mp4'),
]);
fs.writeFileSync(path.join(fxDir, 'bad.mp4'), Buffer.alloc(2048, 7));

let uiPort = 0;
for (const port of UI_PORTS) {
  if (await portFree(port)) {
    uiPort = port;
    break;
  }
}
if (!uiPort) {
  console.error(`FAIL свободный порт для интерфейса не найден (проверены ${UI_PORTS.join(', ')})`);
  process.exit(1);
}
const viteConfig = path.join(tmp, 'vite.stand.config.mjs');
fs.writeFileSync(
  viteConfig,
  `const target = 'http://127.0.0.1:${API_PORT}';
// стенд живёт на своём порту: Origin и sec-fetch-site снимаем, иначе
// backend/security.py отклонит запрос как «с постороннего сайта»
const stripSiteHeaders = proxy => {
  proxy.on('proxyReq', proxyReq => {
    proxyReq.removeHeader('origin');
    proxyReq.removeHeader('sec-fetch-site');
  });
};
export default {
  root: ${JSON.stringify(path.join(ROOT, 'frontend'))},
  server: {
    host: '127.0.0.1',
    port: ${uiPort},
    strictPort: true,
    proxy: {
      '/api': {target, changeOrigin: false, configure: stripSiteHeaders},
      '/login': {target, changeOrigin: false, configure: stripSiteHeaders},
    },
  },
};
`
);

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  args: ['--no-sandbox'],
});
const page = await browser.newPage({viewport: {width: 1440, height: 1400}});
const consoleErrors = [];
page.on('console', message => {
  if (message.type() === 'error') consoleErrors.push(message.text());
});
page.on('pageerror', error => consoleErrors.push('PAGE ' + error.message));
const requests = [];
page.on('request', request => {
  const url = request.url();
  if (url.includes('/decision') || url.includes('/qc/'))
    requests.push(request.method() + ' ' + url.split('release-artifacts')[1]);
});
const uploads = [];
page.on('request', request => {
  const pathname = new URL(request.url()).pathname;
  if (request.method() === 'POST' && /\/api\/projects\/[^/]+\/release-artifacts$/.test(pathname))
    uploads.push(pathname);
});

try {
  backend = startBackend(dataDir);
  check(
    `временный backend поднялся (127.0.0.1:${API_PORT})`,
    await waitFor(`http://127.0.0.1:${API_PORT}/api/health`, 90000)
  );

  frontend = spawn(
    NODE,
    [path.join(ROOT, 'frontend', 'node_modules', 'vite', 'bin', 'vite.js'), '--config', viteConfig],
    {
      cwd: path.join(ROOT, 'frontend'),
      detached: process.platform !== 'win32',
      stdio: 'ignore',
      windowsHide: true,
    }
  );
  frontend.unref();
  check(
    `временный интерфейс поднялся (127.0.0.1:${uiPort})`,
    await waitFor(`http://127.0.0.1:${uiPort}/`, 90000)
  );

  // проект создаётся заранее на временном сервере: экран выпуска работает с сохранённым проектом
  const token = (await (await fetch(`http://127.0.0.1:${API_PORT}/api/session`)).json()).token;
  const created = await (
    await fetch(`http://127.0.0.1:${API_PORT}/api/projects`, {
      method: 'POST',
      headers: {'content-type': 'application/json', 'x-studio-session': token},
      body: JSON.stringify({title: 'E2E выпуск', state: {}}),
    })
  ).json();
  const projectId = created.id;

  /** Смена состояния проекта двигает ревизию — так получаем честный конфликт импорта. */
  async function bumpRevision() {
    const current = await (
      await fetch(`http://127.0.0.1:${API_PORT}/api/projects/${projectId}`, {
        headers: {'x-studio-session': token},
      })
    ).json();
    await fetch(`http://127.0.0.1:${API_PORT}/api/projects`, {
      method: 'POST',
      headers: {'content-type': 'application/json', 'x-studio-session': token},
      body: JSON.stringify({
        id: projectId,
        title: current.title,
        state: {...(current.state || {}), smoke: Date.now()},
        base_revision: current.revision,
      }),
    });
  }

  // задержка загрузки: пока запрос импорта висит, ревизия проекта меняется — получаем 409
  let delayUpload = false;
  await page.route(
    url => /\/api\/projects\/[^/]+\/release-artifacts$/.test(url.pathname),
    async route => {
      if (route.request().method() === 'POST' && delayUpload) {
        delayUpload = false;
        await sleep(900);
        await bumpRevision();
      }
      await route.continue();
    }
  );

  async function openRelease() {
    await page.goto(`http://127.0.0.1:${uiPort}/`);
    await page.waitForTimeout(1500);
    await page
      .getByLabel('Текущий рабочий проект')
      .selectOption({label: 'E2E выпуск'})
      .catch(() => {});
    await page.waitForTimeout(800);
    await page.locator('nav button', {hasText: 'Выпуск'}).first().click();
    await page.waitForTimeout(1000);
  }
  await openRelease();
  const panel = page.locator('.rg');
  check('экран выпуска показан', (await panel.count()) === 1);
  check('финальных 0, пока ничего нет', (await page.getByTestId('final-count').innerText()) === '0');

  async function upload(file, title) {
    await panel.locator('input[type=file]').setInputFiles(file);
    if (title) await panel.getByPlaceholder('Название (необязательно)').fill(title);
    await panel.getByRole('button', {name: 'Загрузить MP4'}).click();
    await page.waitForTimeout(1500);
  }

  // 1. битый файл: русская ошибка, артефакт не создан
  await upload(path.join(fxDir, 'bad.mp4'), 'bad');
  const errorText = await panel
    .locator('.rg-error')
    .first()
    .innerText()
    .catch(() => '');
  check(
    'повреждённый файл: русская ошибка, артефакта нет',
    /MP4|прочитать|видео/i.test(errorText),
    errorText
  );

  // 2. конфликт ревизии: 409 по-русски и без автоматического повтора
  delayUpload = true;
  const uploadsBefore = uploads.length;
  await upload(path.join(fxDir, 'ok.mp4'), 'conflict');
  const conflictText = await panel
    .locator('.rg-error')
    .first()
    .innerText()
    .catch(() => '');
  check('конфликт ревизии: русская ошибка 409', /изменил|ревизи/i.test(conflictText), conflictText);
  check(
    '409 не повторяется автоматически: один POST',
    uploads.length - uploadsBefore === 1,
    `${uploads.length - uploadsBefore}`
  );
  check('после 409 артефакт не создан', (await page.getByTestId('final-count').innerText()) === '0');
  check('после 409 ожидают приёмки 0', (await page.getByTestId('pending-count').innerText()) === '0');

  // 3. нормальный файл: импорт — ещё не финальный
  await upload(path.join(fxDir, 'ok.mp4'), 'e2e-master');
  await page.waitForTimeout(1500);
  const afterImport = await panel.innerText();
  check(
    'после повторной загрузки: состояние «не пройдена»',
    /Загружен, проверка не пройдена/.test(afterImport)
  );
  check('импорт не назван финальным', (await page.getByTestId('final-count').innerText()) === '0');
  check('импорт ждёт приёмки', (await page.getByTestId('pending-count').innerText()) === '1');
  const approve = panel.getByTestId('approve');
  check('утвердить недоступно без N34', await approve.isDisabled());
  const sha = (await panel.locator('.rg-sha code').innerText()).trim();
  check('виден полный SHA-256', /^[0-9a-f]{64}$/.test(sha), sha.slice(0, 12));
  check('видна ревизия проекта', /Ревизия проекта/.test(afterImport));
  await page.screenshot({path: path.join(tmp, 'shot1_imported.png'), fullPage: true});

  // 4. N34: вердикт сервера
  await panel.getByRole('button', {name: 'Проверить N34'}).click();
  await page.waitForTimeout(2500);
  const afterQc = await panel.innerText();
  check('N34 пройдена, состояние TECHNICAL_PASS', /Пройдена/.test(afterQc) && /PASS_TECHNICAL/.test(afterQc));
  check('ждёт решения владельца', /ждёт решения владельца/.test(afterQc));

  // 5. неверный owner_id: ошибка сервера, решение не принято
  await panel.getByLabel('Идентификатор владельца').fill('wrong');
  await panel.getByLabel(/подтверждаю право/).check();
  await approve.click();
  await page.waitForTimeout(1500);
  check('неверный owner_id: ошибка сервера показана', /не совпадает/.test(await panel.innerText()));
  check('финальных всё ещё 0', (await page.getByTestId('final-count').innerText()) === '0');

  // 6. утверждение + двойной клик
  await panel.getByLabel('Идентификатор владельца').fill(OWNER);
  const before = requests.filter(r => r.startsWith('POST') && r.includes('/decision')).length;
  await approve.dblclick();
  await page.waitForTimeout(2500);
  const after = requests.filter(r => r.startsWith('POST') && r.includes('/decision')).length;
  check('двойной клик отправил одно решение', after - before === 1, `${after - before}`);
  check('утверждено владельцем', /Утверждён владельцем/.test(await panel.innerText()));
  check('финальных 1', (await page.getByTestId('final-count').innerText()) === '1');
  await page.screenshot({path: path.join(tmp, 'shot2_approved.png'), fullPage: true});

  // 7. рестарт backend: решение сохранилось
  await stopBackend();
  backend = startBackend(dataDir);
  check('backend перезапущен', await waitFor(`http://127.0.0.1:${API_PORT}/api/health`, 90000));
  await openRelease();
  await page.waitForTimeout(2000);
  const afterRestart = await panel.innerText();
  check(
    'после рестарта backend утверждение сохранилось',
    /Утверждён владельцем/.test(afterRestart) && (await page.getByTestId('final-count').innerText()) === '1',
    afterRestart.slice(0, 80).replace(/\n/g, ' | ')
  );

  // 8. байты изменены на диске: утверждение снимается
  const library = path.join(dataDir, 'library');
  const master = fs.readdirSync(library).find(name => name.endsWith('.mp4'));
  fs.appendFileSync(path.join(library, master), Buffer.from('tail-bytes'));
  await panel.getByRole('button', {name: 'Обновить'}).click();
  await page.waitForTimeout(2500);
  const afterChange = await panel.innerText();
  check('файл изменён: утверждение снято', !/Утверждён владельцем/.test(afterChange));
  check('финальных 0 после изменения байтов', (await page.getByTestId('final-count').innerText()) === '0');
  check('показано, что решение не действует', /не действует/.test(afterChange));
  check('показано, что нужна новая проверка N34', /изменён после проверки/.test(afterChange));
  await page.screenshot({path: path.join(tmp, 'shot3_changed.png'), fullPage: true});

  // 9. отклонение: причина обязательна
  const reject = panel.getByTestId('reject');
  check('отклонить недоступно без причины', await reject.isDisabled());
  await panel.getByLabel('Причина отклонения').fill('плохой звук');
  await reject.click();
  await page.waitForTimeout(2000);
  const afterReject = await panel.innerText();
  check('отклонено', /Отклонён владельцем/.test(afterReject));
  check('финальных 0 после отклонения', (await page.getByTestId('final-count').innerText()) === '0');
  check('история решений видна', /История решений/.test(afterReject));
  await page.screenshot({path: path.join(tmp, 'shot4_rejected.png'), fullPage: true});

  // 10. второй MP4 без звука: N34 с требованием аудио — BLOCKED, утверждать нельзя
  await upload(path.join(fxDir, 'silent.mp4'), 'silent-master');
  await page.waitForTimeout(2000);
  check(
    'после второй загрузки выбран новый MP4',
    /silent-master/.test(await panel.locator('.rg-card').first().innerText())
  );
  await panel.getByRole('button', {name: 'Проверить N34'}).click();
  await page.waitForTimeout(2500);
  const blockedText = await panel.innerText();
  check('без аудио при требовании: «Измерить нельзя»', /Измерить нельзя/.test(blockedText));
  check('утвердить недоступно с причиной', await panel.getByTestId('approve').isDisabled());
  check('счётчик: 0 финальных', (await page.getByTestId('final-count').innerText()) === '0');
  check('ожидают приёмки 2', (await page.getByTestId('pending-count').innerText()) === '2');
  await page.screenshot({path: path.join(tmp, 'shot5_second.png'), fullPage: true});

  // 11. требование аудио при утверждении: мастер без звука, измеренный без требования,
  //     но утверждаемый с требованием — сервер не пропустит (покрытие N35)
  await panel.getByLabel(/требовать аудиодорожку/).uncheck();
  await panel.getByRole('button', {name: 'Проверить N34'}).click();
  await page.waitForTimeout(2500);
  const afterNoAudio = await panel.innerText();
  check('без требования аудио мастер без звука проходит N34', /Пройдена/.test(afterNoAudio));
  check('экран показывает, чем мерили', /без требования аудиодорожки/.test(afterNoAudio));
  await panel.getByLabel(/требовать аудиодорожку/).check();
  await page.waitForTimeout(400);
  check(
    'предупреждение о смене требования после проверки',
    /изменилось после проверки/.test(await panel.innerText())
  );
  await panel.getByLabel('Идентификатор владельца').fill(OWNER);
  await panel.getByLabel(/подтверждаю право/).check();
  await panel.getByTestId('approve').click();
  await page.waitForTimeout(2000);
  const afterDeny = await panel.innerText();
  check(
    'сервер не пропускает мастер без звука при требовании аудио',
    /не покрывает требуемые модальности/.test(afterDeny),
    afterDeny.slice(0, 120).replace(/\n/g, ' | ')
  );
  check('причина от сервера показана', /в мастере нет аудиодорожки/.test(afterDeny));
  check(
    'финальных всё ещё 0 после отказа сервера',
    (await page.getByTestId('final-count').innerText()) === '0'
  );
  await page.screenshot({path: path.join(tmp, 'shot6_audio_required.png'), fullPage: true});

  const real = consoleErrors.filter(text => !/404|Failed to load resource/.test(text));
  check(
    'нет JS-ошибок в консоли (4xx на негативных сценариях ожидаемы)',
    real.length === 0,
    real.join(' | ')
  );
} finally {
  await browser.close();
  if (backend) killTree(backend.pid);
  if (frontend) killTree(frontend.pid);
  console.log(`Временные данные: ${tmp}`);
}

const failed = results.filter(r => !r[1]).length;
console.log(`ИТОГО: ${results.length - failed} PASS, ${failed} FAIL`);
process.exit(failed ? 1 : 0);
