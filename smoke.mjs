// 用真 Chrome 驗：真播放器播得動、跳卡帶背景、F 開回饋並附截圖、改檔自動重整停在同一張卡。
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import { cpSync, existsSync, mkdtempSync, readFileSync, statSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = process.env.CHROME || ['/opt/google/chrome/chrome', '/usr/bin/google-chrome'].find(existsSync);
const dir = mkdtempSync(join(tmpdir(), 'larch-preview-'));
cpSync('fixtures/demo', dir, { recursive: true });
const pj = join(dir, 'project.json');

const server = spawn('python3', ['serve.py', pj, '--port', '0'],   // 0＝讓系統挑空的 port，不會打到別條線開著的預覽
 { stdio: ['ignore', 'pipe', 'inherit'] });
const BASE = await new Promise((ok, bad) => {
  server.stdout.on('data', d => { const m = d.toString().match(/預覽：(http:\/\/127\.0\.0\.1:\d+)/); if (m) ok(m[1]); });
  server.on('exit', c => bad(new Error(`serve.py 結束了（${c}）`)));
});

const trouble = [];   // 失敗時印出來：console 錯誤、頁面例外、4xx/5xx
const browser = await chromium.launch({ executablePath: CHROME, headless: false, args: ['--auto-accept-this-tab-capture'] });
let page;
const fail = async msg => {
  console.error('FAIL', msg);
  for (const t of trouble.filter(t => !t.startsWith('console: Failed to load resource')).slice(-30)) console.error('  ', t);
  await page?.screenshot({ path: 'smoke-fail.png' }).catch(() => {});
  await browser.close(); server.kill(); rmSync(dir, { recursive: true }); process.exit(1); };
const step = msg => console.log('ok  ', msg);

try {
  page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: process.env.SMOKE_LOCALE || 'zh-TW' })).newPage();
  page.on('console', m => m.type() === 'error' && trouble.push('console: ' + m.text()));
  page.on('pageerror', e => trouble.push('pageerror: ' + e.message));
  page.on('response', r => r.status() >= 400 && trouble.push(`${r.status()} ${r.url()}`));
  await page.goto(BASE + '/');
  const frame = page.frameLocator('#player');
  const text = frame.locator('.vn2-text');
  const until = async (want, ms = 15000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) {
      if (((await text.textContent({ timeout: 1000 }).catch(() => '')) || '').includes(want)) return true;
      await page.waitForTimeout(300);
    }
    return false;
  };

  await frame.getByRole('button', { name: /開始遊戲/ }).click({ timeout: 30000 });
  if (!await until('你走進一個綠色的房間。')) await fail('標題畫面按開始後沒看到第一句');
  step('真播放器從標題畫面開始播');

  const visible = await page.evaluate(() => {
    const r = document.querySelector('#fb-open').getBoundingClientRect();
    return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)?.id;
  });
  if (visible !== 'fb-open') await fail(`開始播之後回饋按鈕被蓋住了（最上層是 ${visible}）`);
  step('開始播之後回饋按鈕還看得到');

  for (let i = 0; i < 6 && !await until('歡迎來到示範專案。', 800); i++) await frame.locator('.vn2-box').click();
  if (!await until('歡迎來到示範專案。', 1000)) await fail('點對話框翻不到第二句');
  step('點對話框會前進');

  const edit = f => { const p = JSON.parse(readFileSync(pj, 'utf-8')); f(p); writeFileSync(pj, JSON.stringify(p)); };
  edit(p => { p.boards[0].nodes[1].data.dialogueLines[0].text = '歡迎改過了。'; });
  if (!await until('歡迎改過了。')) await fail('從頭播放中改檔，沒有自動重整停在 d1');
  const st = await (await page.request.get(BASE + '/api/lp/state')).json();
  if (st.card !== 'd1') await fail(`改檔後應該記住 d1，實際是 ${st.card}`);
  step('從頭播放中改檔，自動重整停在 d1');

  await page.request.post(BASE + '/api/lp/card', { data: { card: 'd2' } });
  if (!await until('這裡就是終點。')) await fail('跳卡之後沒出現 d2 的台詞');
  const bg = await page.frame({ url: /play\/market/ }).evaluate(() =>
    [...document.querySelectorAll('*')].some(e => getComputedStyle(e).backgroundImage.includes('/files/bg-b.svg')));
  if (!bg) await fail('跳卡之後背景不是延續下來的 bg-b.svg');
  step('跳卡從 d2 開始，背景延續 bg-b.svg');

  await page.locator('#player').focus();   // 焦點進 iframe；點對話框會翻頁，不能用點的
  if (!await until('這裡就是終點。', 1000)) await fail('按 F 之前畫面已經不在 d2');
  await page.keyboard.press('f');
  await page.locator('#fb[open]').waitFor({ timeout: 10000 });
  const at = JSON.parse(await page.locator('#fb-at').inputValue());
  if (at.nodeId !== 'd2' || at.lineIndex !== 0) await fail(`回饋位置判斷錯：${JSON.stringify(at)}`);
  await page.fill('#fb-note', 'smoke 測試');
  await page.click('#fb-submit');
  await page.locator('#fb[open]').waitFor({ state: 'detached', timeout: 5000 }).catch(() => {});
  const rows = await (await page.request.get(BASE + '/api/lp/feedback')).json();
  const row = rows.at(-1);
  if (row?.note !== 'smoke 測試' || row.at.nodeId !== 'd2') await fail('回饋沒有寫進 feedback.jsonl');
  if (!row.screenshot || !existsSync(join(dir, row.screenshot))) await fail('回饋沒有附截圖');
  if (statSync(join(dir, row.screenshot)).size < 20000) await fail('截圖太小，多半是空白畫面');
  if (process.env.KEEP_SHOT) cpSync(join(dir, row.screenshot), process.env.KEEP_SHOT);
  step('F 開回饋、位置判斷正確、附截圖');

  const p = JSON.parse(readFileSync(pj, 'utf-8'));
  p.boards[0].nodes[3].data.dialogueLines[0].text = '終點改過了。';
  writeFileSync(pj, JSON.stringify(p));
  if (!await until('終點改過了。')) await fail('改檔之後沒有自動重整');
  step('改檔自動重整，停在同一張卡');
} catch (e) {
  await fail(e.stack || String(e));
}

await browser.close();
server.kill();
rmSync(dir, { recursive: true });
console.log('smoke 全部通過');
