import { locate, lines } from './match.js';

const $ = s => document.querySelector(s);
const player = $('#player');
const dialog = $('#fb');
let project = null;
let last = null;          // 上一次的 /api/lp/state
let stream = null;        // 分頁擷取串流，整個工作階段共用
let captureDenied = false;
let shot = null;          // 這次回饋的截圖 data URL
let paused = [];          // 開面板時暫停的 <audio>/<video>

const api = async (path, body) => (await fetch(path, body === undefined ? {} : {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})).json();

async function refreshProject() {
  const r = await fetch('/api/lp/project');
  if (r.ok) project = await r.json();
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
    if (s.error) banner(`專案 JSON 有錯，畫面停在上一版：${s.error}`, true);
    else if (s.card && !s.reachable) banner('這張卡從起點走不到，背景與音樂可能與實際不同。');
    else if (s.card) banner('跳卡模式：變數與條件分支不會照實際路線。');
    else banner('');
    if (!s.error && last) {
      if (s.mtime !== last.mtime) {
        const [cur] = here();
        if (cur && cur.nodeId !== s.card) {
          await api('/api/lp/card', { card: cur.nodeId });
          s.card = cur.nodeId;
        }
        reloadPlayer();
      } else if (s.card !== last.card) {
        reloadPlayer();
      }
    }
    if (!s.error) last = s;
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

function onKey(e) {
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
  if (at.nodeId) { await api('/api/lp/card', { card: at.nodeId }); closePanel(); }
});
$('#fb-restart').addEventListener('click', async () => { await api('/api/lp/card', { card: null }); closePanel(); });
$('#fb-regrant').addEventListener('click', async () => { captureDenied = false; dialog.close(); shot = await grab(); dialog.showModal(); shotStatus(); });
dialog.addEventListener('cancel', e => { e.preventDefault(); closePanel(); });

await refreshProject();
poll();
