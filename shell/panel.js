import { follow, locate, lines } from './match.js';

const $ = s => document.querySelector(s);
const player = $('#player');
const dialog = $('#fb');
let project = null;
let last = null;          // 上一次的 /api/lp/state
let stream = null;        // 分頁擷取串流，整個工作階段共用
let captureDenied = false;
let shot = null;          // 這次回饋的截圖 data URL
let paused = [];          // 開面板時暫停的 <audio>/<video>
let trail = [];
let urlError = null;      // 網址帶了找不到的卡片：常駐顯示，直到下一次跳卡           // 走過的位置 {nodeId, lineIndex}，按 ← 回上一張卡時用

const api = async (path, body) => (await fetch(path, body === undefined ? {} : {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})).json();

// 跳到某張卡的第幾句，並把位置寫進網址（?card=&line=），重新整理或存書籤都會回到這裡
async function go(card, line = 0) {
  urlError = null;
  const u = new URL(location.href);
  if (card) { u.searchParams.set('card', card); u.searchParams.set('line', line); }
  else { u.searchParams.delete('card'); u.searchParams.delete('line'); }
  history.replaceState(null, '', u);
  return api('/api/lp/card', { card: card || null, line });
}

function fillJump() {
  const sel = $('#jump');
  const keep = sel.value;
  sel.replaceChildren(new Option('跳到…（從頭播）', ''));
  for (const b of project?.boards || []) {
    const g = document.createElement('optgroup');
    g.label = b.name || b.id;
    for (const n of b.nodes || []) {
      const d = n.data || {};
      if (d.type === 'group') continue;
      g.append(new Option(d.title || n.id, n.id));
    }
    sel.append(g);
  }
  sel.value = keep;
}

async function refreshProject() {
  const r = await fetch('/api/lp/project');
  if (r.ok) { project = await r.json(); fillJump(); }
}

function banner(text, isError = false) {
  const b = $('#banner');
  b.hidden = !text;
  b.textContent = text || '';
  b.classList.toggle('error', isError);
}

function shownLine() {
  const doc = player.contentDocument;
  const textEl = doc?.querySelector('.vn2-text');
  if (!textEl) return null;
  const text = [...textEl.childNodes]
    .filter(n => !n.classList?.contains('typing-caret'))
    .map(n => n.textContent).join('').trim();
  const speaker = doc.querySelector('.vn2-nameplate b')?.textContent.trim() || '';
  return { speaker, text };
}

function here() {
  const s = shownLine();
  return s && project ? locate(project, s.speaker, s.text) : [];
}

function reloadPlayer() {
  player.contentWindow.location.reload();
  refreshProject();
}

async function poll() {
  try {
    const s = await api('/api/lp/state');
    if (urlError) banner(urlError, true);
    else if (s.error) banner(`專案 JSON 有錯，畫面停在上一版：${s.error}`, true);
    else if (s.notice) banner(s.notice);
    else if (s.card && !s.reachable) banner('這張卡從起點走不到，背景與音樂可能與實際不同。');
    else if (s.card) banner('跳卡模式：變數與條件分支不會照實際路線。');
    else banner('');
    if (!s.error && last) {
      if (s.mtime !== last.mtime) {
        const cur = follow(here(), s.card);
        if (cur && (cur.nodeId !== s.card || cur.lineIndex !== s.line)) {   // 改檔重整後停在同一句
          await go(cur.nodeId, cur.lineIndex);
          s.card = cur.nodeId; s.line = cur.lineIndex;
        }
        reloadPlayer();
      } else if (s.card !== last.card || s.line !== last.line) {
        reloadPlayer();
      }
    }
    if (!s.error) last = s;
    if (document.activeElement !== $('#jump')) $('#jump').value = s.card || '';
    remember();
  } catch { /* 伺服器關了：保持畫面 */ }
  setTimeout(poll, 1000);
}

async function grab() {
  if (captureDenied) return null;
  try {
    if (!stream) {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false, preferCurrentTab: true });
      stream.getVideoTracks()[0].addEventListener('ended', () => { stream = null; });
    }
    document.body.classList.add('grabbing');
    const v = document.createElement('video');
    v.srcObject = stream;
    v.muted = true;
    await v.play();
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    const c = document.createElement('canvas');
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    v.srcObject = null;
    return c.toDataURL('image/png');
  } catch (e) {
    if (e.name === 'NotAllowedError') captureDenied = true;
    return null;
  } finally {
    document.body.classList.remove('grabbing');
  }
}

function shotStatus() {
  $('#fb-shot-status').textContent = shot ? '已附截圖' : (captureDenied ? '截圖：未授權' : '截圖：失敗');
  $('#fb-regrant').hidden = !!shot;
}

function option(line, label) {
  const o = document.createElement('option');
  o.value = JSON.stringify(line);
  o.textContent = label;
  return o;
}

function fillAt(cands) {
  const sel = $('#fb-at');
  sel.replaceChildren();
  const short = l => `${l.nodeId} #${l.lineIndex}　${l.speaker ? l.speaker + '：' : ''}${l.text.slice(0, 24)}`;
  for (const c of cands) sel.append(option(c, short(c)));
  sel.append(option({ matched: 'none', nodeId: null }, '（不指定位置）'));
  const all = document.createElement('optgroup');
  all.label = '全部台詞';
  for (const l of lines(project || {})) all.append(option({ ...l, matched: 'picked' }, short(l)));
  sel.append(all);
  sel.selectedIndex = 0;
}

function selectedAt() {
  return JSON.parse($('#fb-at').value);
}

async function showHistory() {
  const at = selectedAt();
  const rows = (await api('/api/lp/feedback')).filter(r => at.nodeId && r.at?.nodeId === at.nodeId);
  const ul = $('#fb-history');
  ul.replaceChildren(...rows.map(r => {
    const li = document.createElement('li');
    li.className = r.status;
    li.textContent = `${r.status === 'done' ? '已處理' : '待處理'}　${r.text?.to || r.voice?.chars || r.staging?.note || r.note || ''}`
      + (r.resolution ? `　→ ${r.resolution}` : '');
    return li;
  }));
}

function onAtChange() {
  $('#fb-text').value = selectedAt().text || '';
  showHistory();
}

function resetForm() {
  $('#fb-form').reset();
  $('#fb-error').hidden = true;
}

async function openPanel() {
  if (dialog.open) return;
  shot = await grab();
  const doc = player.contentDocument;
  paused = doc ? [...doc.querySelectorAll('audio, video')].filter(m => !m.paused) : [];
  paused.forEach(m => m.pause());
  resetForm();
  fillAt(here());
  onAtChange();
  shotStatus();
  dialog.showModal();
}

function closePanel() {
  dialog.close();
  paused.forEach(m => m.play().catch(() => {}));
  paused = [];
  player.focus();
}

async function submit() {
  const at = selectedAt();
  const entry = { at };
  const to = $('#fb-text').value;
  if (at.nodeId && to.trim() && to !== at.text) entry.text = { from: at.text, to };
  const kind = $('#fb-voice-kind').value;
  if (kind) {
    entry.voice = { kind, chars: $('#fb-voice-chars').value, should: $('#fb-voice-should').value, note: $('#fb-voice-note').value };
  }
  const tags = [...document.querySelectorAll('#fb-staging input:checked')].map(i => i.value);
  const stNote = $('#fb-staging-note').value.trim();
  if (tags.length || stNote) entry.staging = { tags, note: stNote };
  const note = $('#fb-note').value.trim();
  if (note) entry.note = note;
  if (!entry.text && !entry.voice && !entry.staging && !entry.note) {
    $('#fb-error').textContent = '沒有填任何內容。';
    $('#fb-error').hidden = false;
    return;
  }
  const r = await fetch('/api/lp/feedback', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ entry, screenshot: shot }),
  });
  if (!r.ok) {
    $('#fb-error').textContent = `寫入失敗：${(await r.json()).error || r.status}`;
    $('#fb-error').hidden = false;
    return;
  }
  closePanel();
}

function remember() {
  const cur = follow(here(), last?.card);
  const top = trail[trail.length - 1];
  if (cur && !(top && top.nodeId === cur.nodeId && top.lineIndex === cur.lineIndex)) trail = [...trail.slice(-200), cur];
}

// 播放器沒有「回上一句」：同一張卡就從上一句重播，已經在第一句就回上一張卡的最後一句
async function back() {
  remember();
  const cur = follow(here(), last?.card);
  if (!cur) return;
  let to = null;
  if (cur.lineIndex > 0) to = { card: cur.nodeId, line: cur.lineIndex - 1 };
  else {
    // 走過的紀錄優先（有分支時才回得到真的走過的那張）；沒有紀錄（例如直接跳卡進來）就照連線往回找
    const edge = (project.boards || []).flatMap(bd => bd.edges || []).find(e => e.target === cur.nodeId);
    const prev = [...trail].reverse().find(t => t.nodeId !== cur.nodeId) || (edge && { nodeId: edge.source });
    if (!prev) return;
    const n = lines(project).filter(l => l.nodeId === prev.nodeId).length;
    to = { card: prev.nodeId, line: Math.max(0, n - 1) };
    trail = trail.slice(0, trail.lastIndexOf(prev) + 1);
  }
  await go(to.card, to.line);
}

function onKey(e) {
  if (e.key === 'ArrowLeft' && !dialog.open && !(e.ctrlKey || e.metaKey || e.altKey)
      && !e.target.closest?.('input, textarea, select, [contenteditable="true"]')
      && player.contentDocument?.querySelector('.vn2-text')) {
    e.preventDefault();
    e.stopImmediatePropagation();
    back();
    return;
  }
  if (e.key !== 'f' && e.key !== 'F') return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  openPanel();
}

document.addEventListener('keydown', onKey, true);
const hookPlayerKeys = () => player.contentWindow.addEventListener('keydown', onKey, true);
player.addEventListener('load', hookPlayerKeys);
if (player.contentDocument?.readyState === 'complete') hookPlayerKeys();
$('#fb-open').addEventListener('click', openPanel);
$('#fb-cancel').addEventListener('click', closePanel);
$('#fb-submit').addEventListener('click', submit);
$('#fb-at').addEventListener('change', onAtChange);
$('#fb-here').addEventListener('click', async () => {
  const at = selectedAt();
  if (at.nodeId) { await go(at.nodeId); closePanel(); }
});
$('#fb-restart').addEventListener('click', async () => { await go(null); closePanel(); });
$('#jump').addEventListener('change', e => { go(e.target.value || null); e.target.blur(); player.focus(); });
$('#fb-regrant').addEventListener('click', async () => { captureDenied = false; dialog.close(); shot = await grab(); dialog.showModal(); shotStatus(); });
dialog.addEventListener('cancel', e => { e.preventDefault(); closePanel(); });

await refreshProject();
{ // 網址帶 ?card=<卡片id>&line=<第幾句> 就直接從那裡開始
  const q = new URLSearchParams(location.search);
  if (q.get('card')) {
    const r = await go(q.get('card'), Number(q.get('line')) || 0);
    if (r.error) { await go(null); urlError = `網址裡的卡片：${r.error}，改成從頭播。`; }
  }
}
poll();
