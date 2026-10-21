const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const delay = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const root = process.env.MONITOR_TEST_ROOT;
  const snapshot = JSON.parse(await fs.readFile(path.join(root, '.test-host', 'snapshot.json'), 'utf8'));
  const browser = await chromium.connectOverCDP('http://127.0.0.1:19358');
  try {
    let frame, page;
    for (let i = 0; i < 80 && !frame; i++) {
      for (const p of browser.contexts().flatMap(c => c.pages()))
        for (const f of p.frames()) {
          if (
            await f
              .locator('#timeline')
              .count()
              .catch(() => 0)
          ) {
            frame = f;
            page = p;
            break;
          }
        }
      if (!frame) await delay(250);
    }
    assert.ok(frame, 'Webview rendered inside actual VS Code');
    await frame.locator('button.event').first().waitFor();
    await frame.locator('#search').fill('unique-filter-no-events');
    await frame.getByText('Событий по выбранным фильтрам нет.', {exact: true}).waitFor();
    await frame.locator('#search').fill('');
    await frame.locator('button.event').first().waitFor();
    await frame.locator('button.event').first().click();
    await delay(300);
    assert.equal(await frame.locator('#copy').isEnabled(), true);
    const hostile = {
      event_id: 'f'.repeat(64),
      timestamp: '2026-10-21T12:00:00Z',
      source: 'github',
      agent: 'Codex GitHub',
      task_id: 'GA-01',
      pr_number: 58,
      commit_sha: 'a'.repeat(40),
      event_type: 'finding',
      severity: 'P1',
      status: 'Observed',
      summary: '<img src=x onerror="globalThis.INJECTED=true"><script>globalThis.INJECTED=true</script>',
      payload_ref: null,
      correlation_id: 'test',
    };
    await frame.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: path.join(root, 'evidence', 'vscode-live-pr58.png')});
    await frame.locator('#timeline').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(root, 'evidence', 'vscode-live-timeline.png')});
    await frame.evaluate(s => window.dispatchEvent(new MessageEvent('message', {data: s})), {
      ...snapshot,
      type: 'snapshot',
      events: [hostile],
      count: 1,
      shown: 1,
      observed: 1,
      retained: 1,
      choices: {agent: ['Codex GitHub'], task: ['GA-01'], pr: [58], status: ['Observed']},
    });
    assert.equal(await frame.locator('#timeline img,#timeline script').count(), 0);
    assert.equal(await frame.evaluate(() => globalThis.INJECTED), undefined);
    assert.ok((await frame.locator('#timeline').innerText()).includes('<script>'));
    await frame.locator('#refresh').click();
    await frame.waitForFunction(
      () => !document.getElementById('timeline').textContent.includes('globalThis.INJECTED'),
      null,
      {timeout: 30000}
    );
    assert.ok(!(await frame.locator('#timeline').innerText()).includes('globalThis.INJECTED'));
    console.log('UI PASS: real VS Code Webview, filtering, Handoff selection, HTML injection inert, refresh');
  } finally {
    await browser.close();
  }
})().catch(e => {
  console.error(e);
  process.exitCode = 1;
});
