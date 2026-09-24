# larch-preview 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 本機伺服器用 Larch 自己的前端播放專案 JSON，外層回饋面板把使用者的回饋（台詞、語音、演出、截圖）寫成 agent 讀得懂的檔案。

**Architecture:** `serve.py`（Python 標準庫）供應 `vendor/larch/` 裡的 Larch 前端快取，把 `GET /api/marketplace/local` 換成本機專案。純轉換邏輯放 `lp/rewrite.py`，回饋檔讀寫放 `lp/feedback.py`。外層頁面 `shell/` 用 iframe 包住播放器，截圖串流與回饋面板都在外層。`sync.py` 加上每日 Action 更新快取，`smoke.mjs` 用真 Chrome 驗證。

**Tech Stack:** Python 3.12 標準庫（unittest）、原生 ES module JS（node:test）、playwright-core＋系統 Chrome、GitHub Actions。

**Spec:** `docs/specs/2026-09-24-larch-preview-design.md`

## Global Constraints

- repo 是 private，不開 GitHub Pages。
- Python 端零第三方相依；JS 端唯一相依是 `playwright-core`（只給 smoke 用）。
- 不改寫使用者的專案 JSON：所有改寫只發生在 HTTP 回應裡。回饋檔是唯一寫入的東西。
- 預設 port `8790`；smoke 用 `8799`。
- 回饋檔在「專案 JSON 所在資料夾」底下的 `feedback/feedback.jsonl`，截圖 `feedback/<id>.png`，`screenshot` 欄位存相對於專案資料夾的路徑 `feedback/<id>.png`。
- 回饋 id 格式 `fb-YYYYMMDD-HHMMSS-xxxx`（台灣時間，4 位 hex）。
- 對外文字一律正體中文、全形標點、不用 emoji。
- fixture 只放自製內容（`fixtures/demo/`，已在 2026-09-24 用真播放器驗過能播、本機 SVG 背景能顯示）。
- 市集回應外殼只放驗證過的欄位：`id, title, description, startBoardId, publishedBoardIds, chapterMode, project`。
- 播放器 DOM（2026-09-24 量的）：對話框 `.vn2-box`、講者 `.vn2-nameplate b`、內文 `.vn2-text`（裡面的 `.typing-caret` 要排除）、開始鈕文字「開始遊戲」、結束畫面文字「故事暫告一段落」。

## Review Focus

1. **agent 在 `feedback.jsonl` 改狀態的同時，面板剛好寫入一筆**：兩邊都走 `lp.feedback` 的檔案鎖，不能掉任何一行。→ Task 3 測 `set_status` 與 `append` 交錯。
2. **專案 JSON 還沒有版子（剛 `POST /projects` 建出來的）或沒有 `start` 卡**：要回清楚的錯誤訊息，不能 500 一片白。→ Task 1、Task 4 測。
3. **本機素材檔名是中文或放在子資料夾**：`/files/img/角色.webp` 要能讀到（URL 會被瀏覽器編碼）。`../` 一律擋。→ Task 4 測。
4. **larch.ink 擋 GitHub runner 或改版後爬不到某些 chunk**：同步不能把壞掉的快取 commit 上去，也不能每天開一張新 issue。→ Task 5 的 workflow 先跑 smoke 才 commit，開 issue 前先查有沒有同標籤的 open issue。
5. **按 F 時焦點在播放器 iframe 裡，而且播放器自己可能也綁了鍵盤**：面板要打得開，打字時（input、textarea）按 F 不能觸發。→ Task 6 的 smoke 在 iframe 取得焦點後按 f。

---

### Task 1：專案轉換（unwrap、本機素材、市集外殼）

**Files:**
- Create: `lp/__init__.py`（空檔）
- Create: `lp/rewrite.py`
- Create: `tests/test_rewrite.py`
- Create: `.gitignore`
- 既有: `fixtures/demo/project.json`、`bg-a.svg`、`bg-b.svg`（已放好）

**Interfaces:**
- Produces:
  - `rewrite.unwrap(doc: dict) -> dict`
  - `rewrite.localize_urls(value) -> 同型別的新結構`
  - `rewrite.all_nodes(project) -> Iterator[tuple[str, dict]]`（boardId, node）
  - `rewrite.find_start(project) -> tuple[str, str]`（boardId, nodeId）；沒有版子時 `ValueError('專案沒有任何版子')`
  - `rewrite.wrap_market(project: dict, board_id: str | None = None) -> dict`

- [ ] **Step 1：寫 `.gitignore`**

```
__pycache__/
node_modules/
vendor/larch.new/
larch-*/
```

- [ ] **Step 2：寫失敗的測試** `tests/test_rewrite.py`

```python
import copy, json, os, unittest
from lp import rewrite

FIX = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'demo', 'project.json')

def demo():
    with open(FIX, encoding='utf-8') as f:
        return json.load(f)

class Unwrap(unittest.TestCase):
    def test_three_shapes(self):
        p = demo()
        self.assertIs(rewrite.unwrap(p), p)
        self.assertIs(rewrite.unwrap({'project': p}), p)
        self.assertIs(rewrite.unwrap({'id': 'x', 'title': 't', 'project': p}), p)

class Localize(unittest.TestCase):
    def test_relative_paths_go_to_files(self):
        self.assertEqual(rewrite.localize_urls('bg-a.svg'), '/files/bg-a.svg')
        self.assertEqual(rewrite.localize_urls('./img/角色.webp'), '/files/img/角色.webp')
        self.assertEqual(rewrite.localize_urls({'a': ['voice/l0.MP3']}), {'a': ['/files/voice/l0.MP3']})

    def test_leaves_everything_else(self):
        for s in ['https://x.dev/a.png', '/sfx/rain.mp3', 'data:image/png;base64,AAA',
                  'blob:abc', '../secret.png', 'img/../../x.png', '你好。', 'a b.png', 'notes.txt']:
            self.assertEqual(rewrite.localize_urls(s), s, s)

    def test_does_not_mutate(self):
        p = demo(); before = copy.deepcopy(p)
        rewrite.localize_urls(p)
        self.assertEqual(p, before)

class Market(unittest.TestCase):
    def test_wrap_uses_start_board(self):
        w = rewrite.wrap_market(demo())
        self.assertEqual(w['id'], 'local')
        self.assertEqual(w['startBoardId'], 'board-main')
        self.assertEqual([n['id'] for n in w['project']['nodes']], ['s1', 'd1', 's2', 'd2'])
        self.assertEqual(len(w['project']['edges']), 3)
        self.assertEqual(set(w), {'id', 'title', 'description', 'startBoardId', 'publishedBoardIds', 'chapterMode', 'project'})

    def test_find_start(self):
        self.assertEqual(rewrite.find_start(demo()), ('board-main', 's1'))

    def test_no_start_flag_falls_back_to_first_node(self):
        p = demo(); p['boards'][0]['nodes'][0]['data'].pop('start')
        self.assertEqual(rewrite.find_start(p), ('board-main', 's1'))

    def test_no_boards_is_clear_error(self):
        with self.assertRaisesRegex(ValueError, '專案沒有任何版子'):
            rewrite.wrap_market({'id': 'p', 'name': 'x'})

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3：跑，確認失敗**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'lp'` 或 `rewrite` 沒有屬性。

- [ ] **Step 4：實作** `lp/rewrite.py`

```python
"""把作者手上的專案 JSON 轉成 Larch 播放器吃的形狀。全部是純函式，不碰檔案。"""
import copy
import re
from collections import deque

_MEDIA = r'(?:png|jpe?g|webp|gif|svg|avif|mp3|wav|ogg|m4a|mp4|webm)'
# 沒有 scheme、不以 / 開頭、沒有空白與 ?#，副檔名是媒體 → 視為專案資料夾裡的本機素材
_LOCAL = re.compile(r'^(?![a-zA-Z][\w+.-]*:)(?!/)[^\s?#]+\.' + _MEDIA + r'$', re.I)


def unwrap(doc):
    """吃裸專案、agent API 的 {"project": …}、市集回應三種形狀。"""
    return doc['project'] if isinstance(doc.get('project'), dict) else doc


def localize_urls(value):
    """相對路徑的媒體改寫成 /files/<路徑>；含 .. 的一律不動（伺服器那邊也會擋）。"""
    if isinstance(value, dict):
        return {k: localize_urls(v) for k, v in value.items()}
    if isinstance(value, list):
        return [localize_urls(v) for v in value]
    if isinstance(value, str) and _LOCAL.match(value) and '..' not in value.split('/'):
        return '/files/' + value.removeprefix('./')
    return value


def all_nodes(project):
    for b in project.get('boards') or []:
        for n in b.get('nodes') or []:
            yield b['id'], n


def find_start(project):
    boards = project.get('boards') or []
    if not boards:
        raise ValueError('專案沒有任何版子')
    active = project.get('activeBoardId')
    starts = [(b, n['id']) for b, n in all_nodes(project) if (n.get('data') or {}).get('start')]
    for s in starts:
        if s[0] == active:
            return s
    if starts:
        return starts[0]
    for b in boards:
        if b.get('nodes'):
            return b['id'], b['nodes'][0]['id']
    raise ValueError('專案沒有任何卡片')


def wrap_market(project, board_id=None):
    """包成 GET /api/marketplace/<id>?play=1 的回應形狀。"""
    p = copy.deepcopy(project)
    board_id = board_id or find_start(p)[0]
    board = next(b for b in p['boards'] if b['id'] == board_id)
    p['activeBoardId'] = board_id
    p['nodes'] = board.get('nodes') or []
    p['edges'] = board.get('edges') or []
    return {
        'id': 'local',
        'title': p.get('name') or 'local',
        'description': p.get('description') or '',
        'startBoardId': board_id,
        'publishedBoardIds': [b['id'] for b in p['boards']],
        'chapterMode': False,
        'project': p,
    }
```

（`deque` 給 Task 2 用，先 import 著。）

- [ ] **Step 5：跑，確認通過**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS。

- [ ] **Step 6：Commit**

```bash
git add .gitignore lp/__init__.py lp/rewrite.py tests/test_rewrite.py fixtures/demo
git commit -m "feat: 專案轉換（unwrap、本機素材路徑、市集外殼）"
```

---

### Task 2：跳卡與延續狀態

**Files:**
- Modify: `lp/rewrite.py`（加在檔尾）
- Modify: `tests/test_rewrite.py`（加一個 class）

**Interfaces:**
- Consumes: `all_nodes`、`find_start`（Task 1）
- Produces:
  - `rewrite.path_to(project, node_id) -> list[tuple[str, dict]] | None`（從起點到目標，含兩端）
  - `rewrite.carried_state(nodes: list[dict]) -> dict`（鍵：`background`、`bgm`〔dict，含 bgm/bgmVolume/bgmLoop〕、`stage`、`characterLayers`）
  - `rewrite.jump_to_card(project, node_id) -> tuple[dict, str, bool]`（新專案、目標版子 id、是否從起點走得到）；卡不存在 `KeyError`

- [ ] **Step 1：寫失敗的測試**（加進 `tests/test_rewrite.py`，`if __name__` 之前）

```python
def card(nid, **data):
    return {'id': nid, 'type': 'story', 'position': {'x': 0, 'y': 0}, 'data': data}

class Jump(unittest.TestCase):
    def test_jump_carries_background_from_previous_scene(self):
        p, board, ok = rewrite.jump_to_card(demo(), 'd2')
        self.assertTrue(ok)
        self.assertEqual(board, 'board-main')
        nodes = dict((n['id'], n) for _, n in rewrite.all_nodes(p))
        self.assertEqual(nodes['d2']['data']['background'], 'bg-b.svg')
        self.assertEqual([i for i, n in nodes.items() if n['data'].get('start')], ['d2'])
        self.assertFalse(p['settings']['titleScreenEnabled'])

    def test_jump_does_not_mutate_input(self):
        p = demo(); before = copy.deepcopy(p)
        rewrite.jump_to_card(p, 'd2')
        self.assertEqual(p, before)

    def test_bgm_line_level_and_stop(self):
        p = {'activeBoardId': 'b', 'settings': {}, 'boards': [{'id': 'b', 'nodes': [
            card('a', type='scene', start=True, background='x.png', bgm='m1.mp3', bgmVolume=0.3),
            card('b1', type='dialogue', stage={'actors': [{'url': 'mori.png'}]},
                 dialogueLines=[{'text': '一'}, {'text': '二', 'background': 'y.png', 'bgm': 'm2.mp3'}]),
            card('c', type='dialogue', dialogueLines=[{'text': '三'}]),
            card('d', type='dialogue', bgmAction='stop', dialogueLines=[{'text': '四'}]),
            card('e', type='dialogue', dialogueLines=[{'text': '五'}]),
        ], 'edges': [{'source': 'a', 'target': 'b1'}, {'source': 'b1', 'target': 'c'},
                     {'source': 'c', 'target': 'd'}, {'source': 'd', 'target': 'e'}]}]}
        q, _, _ = rewrite.jump_to_card(p, 'c')
        c = next(n for _, n in rewrite.all_nodes(q) if n['id'] == 'c')['data']
        self.assertEqual(c['background'], 'y.png')
        self.assertEqual(c['bgm'], 'm2.mp3')
        self.assertEqual(c['stage'], {'actors': [{'url': 'mori.png'}]})
        q, _, _ = rewrite.jump_to_card(p, 'e')
        e = next(n for _, n in rewrite.all_nodes(q) if n['id'] == 'e')['data']
        self.assertNotIn('bgm', e)

    def test_own_values_win(self):
        p = demo(); p['boards'][0]['nodes'][3]['data']['background'] = 'own.png'
        q, _, _ = rewrite.jump_to_card(p, 'd2')
        self.assertEqual(q['boards'][0]['nodes'][3]['data']['background'], 'own.png')

    def test_scene_target_gets_no_stage(self):
        p = demo(); p['boards'][0]['nodes'][1]['data']['stage'] = {'actors': [{'url': 'g.png'}]}
        q, _, _ = rewrite.jump_to_card(p, 's2')
        self.assertNotIn('stage', q['boards'][0]['nodes'][2]['data'])

    def test_board_jump(self):
        p = demo()
        p['boards'][0]['nodes'].append(card('j', type='boardJump', jumpBoardId='b2', jumpNodeId='x1'))
        p['boards'][0]['edges'].append({'source': 'd2', 'target': 'j'})
        p['boards'].append({'id': 'b2', 'nodes': [card('x1', type='dialogue', dialogueLines=[{'text': '二章'}])], 'edges': []})
        q, board, ok = rewrite.jump_to_card(p, 'x1')
        self.assertEqual((board, ok), ('b2', True))
        self.assertEqual(q['boards'][1]['nodes'][0]['data']['background'], 'bg-b.svg')
        self.assertEqual(rewrite.wrap_market(q, board)['startBoardId'], 'b2')

    def test_unreachable_card_still_starts(self):
        p = demo(); p['boards'][0]['nodes'].append(card('island', type='dialogue', text='孤島'))
        q, _, ok = rewrite.jump_to_card(p, 'island')
        self.assertFalse(ok)
        self.assertTrue(q['boards'][0]['nodes'][-1]['data']['start'])

    def test_unknown_card(self):
        with self.assertRaises(KeyError):
            rewrite.jump_to_card(demo(), 'nope')
```

- [ ] **Step 2：跑，確認失敗**

Run: `python3 -m unittest discover -s tests -v`
Expected: `Jump` 全部 FAIL（`AttributeError: ... jump_to_card`）。

- [ ] **Step 3：實作**（加到 `lp/rewrite.py` 檔尾）

```python
_BGM = ('bgm', 'bgmVolume', 'bgmLoop')


def _board_entry(project, board_id):
    nodes = next((b.get('nodes') or [] for b in project['boards'] if b['id'] == board_id), [])
    start = next((n['id'] for n in nodes if (n.get('data') or {}).get('start')), None)
    return start or (nodes[0]['id'] if nodes else None)


def path_to(project, node_id):
    """起點沿邊 BFS 到目標卡的最短路徑；boardJump 卡視為接到目標版子。走不到回 None。"""
    index = {(b, n['id']): n for b, n in all_nodes(project)}
    out = {}
    for b in project['boards']:
        for e in b.get('edges') or []:
            out.setdefault((b['id'], e['source']), []).append((b['id'], e['target']))
    for key, n in index.items():
        d = n.get('data') or {}
        if d.get('type') == 'boardJump' and d.get('jumpBoardId'):
            out.setdefault(key, []).append(
                (d['jumpBoardId'], d.get('jumpNodeId') or _board_entry(project, d['jumpBoardId'])))
    start = find_start(project)
    prev = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur[1] == node_id:
            path = []
            while cur:
                path.append((cur[0], index[cur]))
                cur = prev[cur]
            return path[::-1]
        for nxt in out.get(cur, []):
            if nxt in index and nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    return None


def carried_state(nodes):
    """照播放器的延續規則，累積走過這些卡之後還留在畫面上的背景、BGM、舞台。"""
    state = {}
    for n in nodes:
        d = n.get('data') or {}
        for layer in [d] + list(d.get('dialogueLines') or []):
            if layer.get('background'):
                state['background'] = layer['background']
            if layer.get('bgm'):
                state['bgm'] = {k: layer[k] for k in _BGM if k in layer}
            if layer.get('bgmAction') == 'stop':
                state.pop('bgm', None)
        for k in ('stage', 'characterLayers'):
            if k in d:
                state[k] = d[k]
    return state


def jump_to_card(project, node_id):
    """讓播放器直接從 node_id 開始：設 start、關標題畫面、補上延續下來的狀態。"""
    p = copy.deepcopy(project)
    hit = next(((b, n) for b, n in all_nodes(p) if n['id'] == node_id), None)
    if not hit:
        raise KeyError(f'找不到卡片 {node_id}')
    board_id, target = hit
    path = path_to(p, node_id)
    d = target.setdefault('data', {})
    if path:
        state = carried_state([n for _, n in path[:-1]])
        if state.get('background') and not d.get('background'):
            d['background'] = state['background']
        if state.get('bgm') and not d.get('bgm'):
            d.update(state['bgm'])
        if d.get('type') == 'dialogue':
            for k in ('stage', 'characterLayers'):
                if k in state and k not in d:
                    d[k] = state[k]
    for _, n in all_nodes(p):
        (n.get('data') or {}).pop('start', None)
    d['start'] = True
    p.setdefault('settings', {})['titleScreenEnabled'] = False
    p['activeBoardId'] = board_id
    return p, board_id, path is not None
```

- [ ] **Step 4：跑，確認通過**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS。

- [ ] **Step 5：Commit**

```bash
git add lp/rewrite.py tests/test_rewrite.py
git commit -m "feat: 跳卡並補上延續的背景、BGM、舞台"
```

---

### Task 3：回饋檔讀寫

**Files:**
- Create: `lp/feedback.py`
- Create: `tests/test_feedback.py`

**Interfaces:**
- Produces:
  - `feedback.read_all(fb_dir: str) -> list[dict]`
  - `feedback.append(fb_dir: str, entry: dict, png: bytes | None = None) -> dict`（回傳寫入的完整一筆）
  - `feedback.set_status(fb_dir: str, fid: str, status: str, resolution: str | None) -> dict`；找不到 `KeyError`
  - CLI：`python3 -m lp.feedback list <專案資料夾>`、`python3 -m lp.feedback done <專案資料夾> <id> "<處理說明>"`
  - `feedback.ALLOWED = ('at', 'text', 'voice', 'staging', 'note')`

- [ ] **Step 1：寫失敗的測試** `tests/test_feedback.py`

```python
import json, os, re, tempfile, threading, unittest
from lp import feedback

class Feedback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, 'feedback')

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty(self):
        self.assertEqual(feedback.read_all(self.dir), [])

    def test_append_with_screenshot(self):
        e = feedback.append(self.dir, {'at': {'nodeId': 'd1', 'lineIndex': 0}, 'note': '太長'}, b'\x89PNG')
        self.assertRegex(e['id'], r'^fb-\d{8}-\d{6}-[0-9a-f]{4}$')
        self.assertEqual(e['status'], 'open')
        self.assertIsNone(e['resolution'])
        self.assertEqual(e['screenshot'], f"feedback/{e['id']}.png")
        with open(os.path.join(self.dir, e['id'] + '.png'), 'rb') as f:
            self.assertEqual(f.read(), b'\x89PNG')
        self.assertEqual(feedback.read_all(self.dir), [e])

    def test_unknown_and_reserved_keys_dropped(self):
        e = feedback.append(self.dir, {'note': 'x', 'status': 'done', 'id': 'evil', 'screenshot': '/etc/passwd', 'junk': 1})
        self.assertEqual(e['status'], 'open')
        self.assertNotIn('junk', e)
        self.assertNotIn('screenshot', e)
        self.assertNotEqual(e['id'], 'evil')

    def test_chinese_kept_readable(self):
        feedback.append(self.dir, {'note': '質地唸錯'})
        with open(os.path.join(self.dir, 'feedback.jsonl'), encoding='utf-8') as f:
            self.assertIn('質地唸錯', f.read())

    def test_set_status_keeps_other_lines(self):
        a = feedback.append(self.dir, {'note': 'a'})
        b = feedback.append(self.dir, {'note': 'b'})
        feedback.set_status(self.dir, a['id'], 'done', '改成短句')
        rows = feedback.read_all(self.dir)
        self.assertEqual([r['id'] for r in rows], [a['id'], b['id']])
        self.assertEqual((rows[0]['status'], rows[0]['resolution']), ('done', '改成短句'))
        self.assertEqual(rows[1]['status'], 'open')
        with self.assertRaises(KeyError):
            feedback.set_status(self.dir, 'fb-nope', 'done', None)

    def test_concurrent_append_and_set_status_lose_nothing(self):
        first = feedback.append(self.dir, {'note': 'first'})
        def writer(i):
            feedback.append(self.dir, {'note': f'n{i}'})
        def updater():
            for _ in range(20):
                feedback.set_status(self.dir, first['id'], 'done', 'ok')
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)] + [threading.Thread(target=updater)]
        for t in threads: t.start()
        for t in threads: t.join()
        rows = feedback.read_all(self.dir)
        self.assertEqual(len(rows), 21)
        self.assertEqual(rows[0]['status'], 'done')

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2：跑，確認失敗**

Run: `python3 -m unittest tests.test_feedback -v`
Expected: FAIL（`cannot import name 'feedback'`）。

- [ ] **Step 3：實作** `lp/feedback.py`

```python
"""回饋檔：<專案資料夾>/feedback/feedback.jsonl，一行一筆。面板與 agent 共用這支，靠檔案鎖避免互相蓋掉。"""
import datetime
import fcntl
import json
import os
import secrets
import sys
from contextlib import contextmanager

ALLOWED = ('at', 'text', 'voice', 'staging', 'note')
TZ = datetime.timezone(datetime.timedelta(hours=8))


def _file(fb_dir):
    return os.path.join(fb_dir, 'feedback.jsonl')


@contextmanager
def _locked(fb_dir):
    os.makedirs(fb_dir, exist_ok=True)
    with open(os.path.join(fb_dir, '.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def read_all(fb_dir):
    try:
        with open(_file(fb_dir), encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def _write(fb_dir, rows):
    tmp = _file(fb_dir) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, _file(fb_dir))


def append(fb_dir, entry, png=None):
    now = datetime.datetime.now(TZ)
    fid = f'fb-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}'
    row = {'id': fid, 'createdAt': now.isoformat(timespec='seconds'), 'status': 'open', 'resolution': None}
    row.update({k: entry[k] for k in ALLOWED if k in entry})
    with _locked(fb_dir):
        if png:
            with open(os.path.join(fb_dir, fid + '.png'), 'wb') as f:
                f.write(png)
            row['screenshot'] = f'feedback/{fid}.png'
        _write(fb_dir, read_all(fb_dir) + [row])
    return row


def set_status(fb_dir, fid, status, resolution):
    with _locked(fb_dir):
        rows = read_all(fb_dir)
        hit = next((r for r in rows if r['id'] == fid), None)
        if not hit:
            raise KeyError(f'找不到回饋 {fid}')
        hit['status'], hit['resolution'] = status, resolution
        _write(fb_dir, rows)
    return hit


def main(argv):
    if len(argv) >= 2 and argv[0] == 'list':
        for r in read_all(os.path.join(argv[1], 'feedback')):
            if r['status'] == 'open':
                print(json.dumps(r, ensure_ascii=False))
    elif len(argv) == 4 and argv[0] == 'done':
        set_status(os.path.join(argv[1], 'feedback'), argv[2], 'done', argv[3])
    else:
        sys.exit('用法：python3 -m lp.feedback list <專案資料夾>\n'
                 '　　　python3 -m lp.feedback done <專案資料夾> <id> "<處理說明>"')


if __name__ == '__main__':
    main(sys.argv[1:])
```

- [ ] **Step 4：跑，確認通過**

Run: `python3 -m unittest tests.test_feedback -v`
Expected: 全部 PASS。

- [ ] **Step 5：CLI 手動冒煙**

Run: `d=$(mktemp -d) && python3 -c "from lp import feedback; print(feedback.append('$d/feedback', {'note':'x'})['id'])" | xargs -I{} python3 -m lp.feedback done $d {} "已處理" && python3 -m lp.feedback list $d; cat $d/feedback/feedback.jsonl`
Expected: `list` 沒有輸出（唯一一筆已經是 done），jsonl 那一行 `"status": "done", "resolution": "已處理"`。

- [ ] **Step 6：Commit**

```bash
git add lp/feedback.py tests/test_feedback.py
git commit -m "feat: 回饋檔讀寫與 agent 用的 CLI"
```

---

### Task 4：serve.py

**Files:**
- Create: `serve.py`
- Create: `shell/index.html`（先放最小版，Task 6 會補完）
- Create: `tests/test_serve.py`

**Interfaces:**
- Consumes: `rewrite.unwrap / localize_urls / jump_to_card / wrap_market`、`feedback.append / read_all`
- Produces:
  - `serve.Preview(project_path)`：屬性 `path`、`dir`、`card`；方法 `load()`、`market() -> (dict, bool)`、`state() -> {'mtime','card','error','reachable'}`
  - `serve.make_server(preview, port, vendor=VENDOR) -> ThreadingHTTPServer`
  - HTTP：見 spec 路由表，另加 `GET /api/lp/project`（回 unwrap 後、未改寫的專案，給面板比對台詞用）
  - `POST /api/lp/feedback` body：`{"entry": {...}, "screenshot": "data:image/png;base64,…" | null}` → 回寫入的那筆
  - `POST /api/lp/card` body：`{"card": "<nodeId>" | null}` → 回 `state()`

- [ ] **Step 1：最小外層頁面** `shell/index.html`

```html
<!doctype html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><title>Larch 預覽</title></head>
<body><iframe id="player" src="/play/market/local"></iframe></body>
</html>
```

- [ ] **Step 2：寫失敗的測試** `tests/test_serve.py`

```python
import base64, json, os, shutil, tempfile, threading, time, unittest, urllib.request, urllib.error
from urllib.parse import quote
import serve

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Serve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(os.path.join(ROOT, 'fixtures', 'demo'), os.path.join(self.tmp, 'proj'))
        os.makedirs(os.path.join(self.tmp, 'proj', 'img'))
        with open(os.path.join(self.tmp, 'proj', 'img', '角色.svg'), 'w') as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.vendor = os.path.join(self.tmp, 'vendor')
        os.makedirs(os.path.join(self.vendor, 'assets'))
        with open(os.path.join(self.vendor, 'index.html'), 'w') as f:
            f.write('<!doctype html><title>larch</title>')
        with open(os.path.join(self.vendor, 'assets', 'index-abc.js'), 'w') as f:
            f.write('console.log(1)')
        self.pj = os.path.join(self.tmp, 'proj', 'project.json')
        self.srv = serve.make_server(serve.Preview(self.pj), 0, self.vendor)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp)

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.headers.get('Content-Type'), r.read()

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, json.dumps(body).encode(), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    def status_of(self, path):
        try:
            return self.get(path)[0]
        except urllib.error.HTTPError as e:
            return e.code

    def test_market_is_localized(self):
        _, ct, body = self.get('/api/marketplace/local?play=1')
        w = json.loads(body)
        self.assertIn('application/json', ct)
        self.assertEqual(w['project']['nodes'][0]['data']['background'], '/files/bg-a.svg')
        self.assertTrue(w['project']['settings']['titleScreenEnabled'])

    def test_files(self):
        self.assertEqual(self.get('/files/bg-a.svg')[1], 'image/svg+xml')
        self.assertEqual(self.get('/files/' + quote('img/角色.svg'))[0], 200)
        self.assertEqual(self.status_of('/files/../project.json'), 404)
        self.assertEqual(self.status_of('/files/%2e%2e/%2e%2e/serve.py'), 404)
        self.assertEqual(self.status_of('/files/nope.png'), 404)

    def test_spa_assets_and_shell(self):
        self.assertIn(b'<title>larch</title>', self.get('/play/market/local')[2])
        self.assertIn('javascript', self.get('/assets/index-abc.js')[1])
        self.assertEqual(self.status_of('/assets/missing.js'), 404)
        self.assertIn(b'id="player"', self.get('/')[2])
        self.assertEqual(json.loads(self.get('/api/emojis')[2]), {})
        self.assertEqual(self.post('/api/presence/beat', {}), {})

    def test_card_jump(self):
        s = self.post('/api/lp/card', {'card': 'd2'})
        self.assertEqual((s['card'], s['reachable'], s['error']), ('d2', True, None))
        w = json.loads(self.get('/api/marketplace/local')[2])
        d2 = w['project']['nodes'][3]['data']
        self.assertEqual((d2['start'], d2['background']), (True, '/files/bg-b.svg'))
        self.assertFalse(w['project']['settings']['titleScreenEnabled'])
        self.assertIsNone(self.post('/api/lp/card', {'card': None})['card'])

    def test_state_reports_changes_and_errors(self):
        s1 = json.loads(self.get('/api/lp/state')[2])
        time.sleep(0.02)
        with open(self.pj, 'a') as f:
            f.write('\n{broken')
        s2 = json.loads(self.get('/api/lp/state')[2])
        self.assertNotEqual(s1['mtime'], s2['mtime'])
        self.assertIn('line', s2['error'])
        self.assertEqual(self.status_of('/api/marketplace/local'), 500)

    def test_unknown_card_and_no_boards_are_errors_not_crashes(self):
        self.assertIn('nope', self.post('/api/lp/card', {'card': 'nope'})['error'])
        self.post('/api/lp/card', {'card': None})
        with open(self.pj, 'w') as f:
            json.dump({'id': 'p', 'name': '空'}, f)
        self.assertIn('專案沒有任何版子', json.loads(self.get('/api/lp/state')[2])['error'])

    def test_project_and_feedback(self):
        self.assertEqual(json.loads(self.get('/api/lp/project')[2])['boards'][0]['nodes'][0]['data']['background'], 'bg-a.svg')
        png = 'data:image/png;base64,' + base64.b64encode(b'\x89PNGfake').decode()
        e = self.post('/api/lp/feedback', {'entry': {'at': {'nodeId': 'd1', 'lineIndex': 1}, 'note': '太長'}, 'screenshot': png})
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'proj', e['screenshot'])))
        self.assertEqual([r['id'] for r in json.loads(self.get('/api/lp/feedback')[2])], [e['id']])

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3：跑，確認失敗**

Run: `python3 -m unittest tests.test_serve -v`
Expected: FAIL（`No module named 'serve'`）。

- [ ] **Step 4：實作** `serve.py`

```python
#!/usr/bin/env python3
"""larch-preview：用 Larch 自己的播放器在本機預覽專案 JSON。

  python3 serve.py <project.json> [--port 8790]
  python3 serve.py --market <發佈id>
  python3 serve.py --project <專案id>     # 金鑰讀 ~/.config/larch/key，只做 GET
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from lp import feedback, rewrite

ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(ROOT, 'vendor', 'larch')
SHELL = os.path.join(ROOT, 'shell')
MAX_BODY = 30 * 1024 * 1024
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('image/webp', '.webp')


class Preview:
    def __init__(self, project_path):
        self.path = os.path.abspath(project_path)
        self.dir = os.path.dirname(self.path)
        self.card = None
        self.lock = threading.Lock()

    def load(self):
        with open(self.path, encoding='utf-8') as f:
            return rewrite.unwrap(json.load(f))

    def market(self):
        project, board, reachable = self.load(), None, True
        if self.card:
            project, board, reachable = rewrite.jump_to_card(project, self.card)
        return rewrite.wrap_market(rewrite.localize_urls(project), board), reachable

    def state(self):
        s = {'mtime': os.stat(self.path).st_mtime, 'card': self.card, 'error': None, 'reachable': True}
        try:
            _, s['reachable'] = self.market()
        except (ValueError, KeyError) as e:   # JSONDecodeError 是 ValueError，訊息帶行號
            s['error'] = str(e)
        return s


def safe_join(base, rel):
    base = os.path.realpath(base)
    full = os.path.realpath(os.path.join(base, rel))
    return full if os.path.commonpath([base, full]) == base and os.path.isfile(full) else None


def make_server(preview, port, vendor=VENDOR):
    class H(BaseHTTPRequestHandler):
        def send(self, code, body, ctype='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def send_file(self, path):
            if not path:
                return self.send(404, {'error': 'not found'})
            with open(path, 'rb') as f:
                self.send(200, f.read(), mimetypes.guess_type(path)[0] or 'application/octet-stream')

        def body(self):
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAX_BODY:
                raise ValueError('內容太大')
            return json.loads(self.rfile.read(n) or b'{}')

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            try:
                if path.startswith('/api/marketplace/local'):
                    return self.send(200, preview.market()[0])
                if path == '/api/lp/state':
                    return self.send(200, preview.state())
                if path == '/api/lp/project':
                    return self.send(200, preview.load())
                if path == '/api/lp/feedback':
                    return self.send(200, feedback.read_all(os.path.join(preview.dir, 'feedback')))
            except (ValueError, KeyError) as e:
                return self.send(500, {'error': str(e)})
            if path.startswith('/api/'):
                return self.send(200, {})
            if path.startswith('/files/'):
                return self.send_file(safe_join(preview.dir, path[len('/files/'):]))
            if path.startswith('/shell/'):
                return self.send_file(safe_join(SHELL, path[len('/shell/'):]))
            if path == '/':
                return self.send_file(os.path.join(SHELL, 'index.html'))
            if path.startswith(('/assets/', '/sfx/')):
                return self.send_file(safe_join(vendor, path.lstrip('/')))
            if '.' in os.path.basename(path):
                return self.send(404, {'error': 'not found'})
            return self.send_file(os.path.join(vendor, 'index.html'))   # SPA 萬用路由

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                if path == '/api/lp/card':
                    with preview.lock:
                        preview.card = self.body().get('card') or None
                    return self.send(200, preview.state())
                if path == '/api/lp/feedback':
                    b = self.body()
                    if not isinstance(b.get('entry'), dict):
                        raise ValueError('entry 要是物件')
                    shot = b.get('screenshot') or ''
                    png = base64.b64decode(shot.split(',', 1)[1]) if shot.startswith('data:image/png;base64,') else None
                    return self.send(200, feedback.append(os.path.join(preview.dir, 'feedback'), b['entry'], png))
            except (ValueError, KeyError) as e:
                return self.send(400, {'error': str(e)})
            return self.send(200, {})

        def log_message(self, fmt, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), H)


def fetch(url, key=None):
    headers = {'User-Agent': 'Mozilla/5.0'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180) as r:
        return json.load(r)


def download(kind, ident):
    if kind == 'market':
        doc = fetch(f'https://larch.ink/api/marketplace/{ident}?play=1')
    else:
        with open(os.path.expanduser('~/.config/larch/key')) as f:
            doc = fetch(f'https://larch.ink/api/agent/projects/{ident}', f.read().strip())
    out = os.path.join(os.getcwd(), f'larch-{ident}', 'project.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rewrite.unwrap(doc), f, ensure_ascii=False, indent=1)
    print(f'已存到 {out}')
    return out


def main():
    ap = argparse.ArgumentParser(description='用 Larch 自己的播放器在本機預覽專案 JSON')
    ap.add_argument('project', nargs='?')
    ap.add_argument('--market')
    ap.add_argument('--project', dest='project_id')
    ap.add_argument('--port', type=int, default=8790)
    a = ap.parse_args()
    if not os.path.exists(os.path.join(VENDOR, 'index.html')):
        sys.exit('找不到 Larch 前端快取，先跑：python3 sync.py')
    path = a.project or (a.market and download('market', a.market)) or (a.project_id and download('project', a.project_id))
    if not path:
        ap.error('要給專案 JSON 路徑、--market 或 --project 其中一個')
    srv = make_server(Preview(path), a.port)
    print(f'預覽：http://127.0.0.1:{a.port}/　回饋：{os.path.join(os.path.dirname(os.path.abspath(path)), "feedback")}')
    srv.serve_forever()


if __name__ == '__main__':
    main()
```

- [ ] **Step 5：跑，確認通過**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS（包含 Task 1–3 的）。

- [ ] **Step 6：Commit**

```bash
git add serve.py shell/index.html tests/test_serve.py
git commit -m "feat: 本機伺服器（真播放器＋本機專案＋回饋 API）"
```

---

### Task 5：Larch 前端同步與每日 Action

**Files:**
- Create: `sync.py`
- Create: `tests/test_sync.py`
- Create: `.github/workflows/sync.yml`
- Create: `vendor/larch/`（跑 sync 產生後 commit）

**Interfaces:**
- Produces:
  - `sync.extract_refs(text: str) -> list[str]`（`assets/` 底下的檔名，已排序去重）
  - `sync.version(html: str) -> str`（`index-<hash>.js`）
  - CLI：`python3 sync.py [--force]`；有 `GITHUB_OUTPUT` 時寫 `changed=true|false`
  - `vendor/larch/VERSION`（內容是 `version()` 的值）

- [ ] **Step 1：寫失敗的測試** `tests/test_sync.py`

```python
import unittest
import sync

HTML = '<script type="module" crossorigin src="/assets/index-lg9nGv1N.js"></script><link rel="stylesheet" href="/assets/index-Ab_c.css">'
JS = 'const __vite__mapDeps=(i,m,d=(m.f||(m.f=["assets/pixi-engine-BjJSJWAc.js","assets/Preview-QqNq3ynq.css"])));import{r}from"./react-core-CuKebU_E.js";const x="./not-a-thing"'
CSS = '@font-face{src:url(/assets/noto-a.woff2) format("woff2")}.x{background:url(./bg-1.webp)}'

class Sync(unittest.TestCase):
    def test_refs(self):
        self.assertEqual(sync.extract_refs(HTML), ['index-Ab_c.css', 'index-lg9nGv1N.js'])
        self.assertEqual(sync.extract_refs(JS), ['Preview-QqNq3ynq.css', 'pixi-engine-BjJSJWAc.js', 'react-core-CuKebU_E.js'])
        self.assertEqual(sync.extract_refs(CSS), ['bg-1.webp', 'noto-a.woff2'])

    def test_version(self):
        self.assertEqual(sync.version(HTML), 'index-lg9nGv1N.js')

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2：跑，確認失敗**

Run: `python3 -m unittest tests.test_sync -v`
Expected: FAIL（`No module named 'sync'`）。

- [ ] **Step 3：實作** `sync.py`

```python
#!/usr/bin/env python3
"""把 larch.ink 的前端抓成本機快取 vendor/larch/。index 的 hash 沒變就不動。"""
import argparse
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

BASE = 'https://larch.ink'
ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(ROOT, 'vendor', 'larch')
SFX = ['rain', 'thunder', 'wind', 'waves', 'fire', 'footsteps', 'knock', 'whoosh', 'sting', 'heartbeat', 'chime']
REF = re.compile(r'(?:/?assets/|\./)([A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*'
                 r'\.(?:js|mjs|css|woff2?|ttf|otf|png|svg|webp|jpe?g|gif|wasm|json|mp3))')


def extract_refs(text):
    return sorted(set(REF.findall(text)))


def version(html):
    m = re.search(r'assets/(index-[A-Za-z0-9_\-]+\.js)', html)
    if not m:
        raise ValueError('larch.ink 首頁找不到 index-*.js，平台可能改了打包方式')
    return m.group(1)


def get(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError:
            raise
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3)


def crawl(dest, html):
    os.makedirs(os.path.join(dest, 'assets'))
    os.makedirs(os.path.join(dest, 'sfx'))
    with open(os.path.join(dest, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    queue, seen, missing = extract_refs(html), set(), []
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            data = get(f'{BASE}/assets/{name}')
        except urllib.error.HTTPError as e:
            missing.append(f'{name}（{e.code}）')
            continue
        with open(os.path.join(dest, 'assets', name), 'wb') as f:
            f.write(data)
        if name.endswith(('.js', '.mjs', '.css')):
            queue += extract_refs(data.decode('utf-8', 'replace'))
    for s in SFX:
        with open(os.path.join(dest, 'sfx', s + '.mp3'), 'wb') as f:
            f.write(get(f'{BASE}/sfx/{s}.mp3'))
    print(f'抓了 {len(seen) - len(missing)} 個檔案＋{len(SFX)} 個音效')
    if missing:
        print('抓不到（多半是字串裡碰巧長得像檔名）：' + '、'.join(missing))


def output(changed):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'changed={"true" if changed else "false"}\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    html = get(BASE + '/').decode('utf-8')
    ver = version(html)
    vfile = os.path.join(VENDOR, 'VERSION')
    old = open(vfile).read().strip() if os.path.exists(vfile) else None
    if ver == old and not a.force:
        print(f'已是最新：{ver}')
        return output(False)
    tmp = VENDOR + '.new'
    shutil.rmtree(tmp, ignore_errors=True)
    crawl(tmp, html)
    with open(os.path.join(tmp, 'VERSION'), 'w') as f:
        f.write(ver + '\n')
    shutil.rmtree(VENDOR, ignore_errors=True)
    os.rename(tmp, VENDOR)
    print(f'已更新：{old} → {ver}')
    output(True)


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4：跑，確認通過**

Run: `python3 -m unittest tests.test_sync -v`
Expected: PASS。

- [ ] **Step 5：真的同步一次**

Run: `python3 sync.py && cat vendor/larch/VERSION && du -sh vendor/larch && ls vendor/larch/assets | grep -c . && ls vendor/larch/assets | grep '^Preview-'`
Expected: 印出「已更新：None → index-….js」，assets 超過 150 個檔案，看得到 `Preview-*.js` 與 `Preview-*.css`。記下總大小（預期幾十 MB 以內；超過 100 MB 要停下來回報）。

- [ ] **Step 6：用真播放器手動確認一次**

Run: `python3 serve.py fixtures/demo/project.json`，瀏覽器開 `http://127.0.0.1:8790/`
Expected: iframe 裡出現標題「示範：兩個房間」，按開始遊戲後綠色背景、第一句「你走進一個綠色的房間。」。看完 Ctrl+C 關掉。

- [ ] **Step 7：寫 workflow** `.github/workflows/sync.yml`

```yaml
name: sync-larch
on:
  schedule:
    - cron: '17 22 * * *'   # 台灣時間 06:17
  workflow_dispatch:
    inputs:
      force:
        description: 版本沒變也重抓並跑 smoke
        type: boolean
        default: false
permissions:
  contents: write
  issues: write
jobs:
  sync:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm ci
      - id: sync
        run: python3 sync.py ${{ inputs.force && '--force' || '' }}
      - if: steps.sync.outputs.changed == 'true'
        run: xvfb-run -a node smoke.mjs
        env:
          CHROME: /usr/bin/google-chrome
      - if: steps.sync.outputs.changed == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add vendor/larch
          git diff --cached --quiet || { git commit -m "chore: 同步 Larch 前端 $(cat vendor/larch/VERSION)" && git push; }
      - if: failure()
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh label create sync-failure --color B60205 2>/dev/null || true
          if [ -z "$(gh issue list --label sync-failure --state open --json number -q '.[].number')" ]; then
            gh issue create --label sync-failure --title "Larch 前端同步失敗" \
              --body "舊快取照用，本機預覽不受影響。紀錄：${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          fi
```

（smoke 與 `package.json` 在 Task 6 建立，workflow 要等 Task 6 完成才跑得動。）

- [ ] **Step 8：Commit**

```bash
git add sync.py tests/test_sync.py .github/workflows/sync.yml vendor/larch
git commit -m "feat: 同步 Larch 前端快取與每日 Action"
```

---

### Task 6：外層頁面、回饋面板、冒煙測試

**Files:**
- Modify: `shell/index.html`（整份換掉）
- Create: `shell/match.js`
- Create: `shell/match.test.mjs`
- Create: `shell/panel.js`
- Create: `shell/panel.css`
- Create: `package.json`、`package-lock.json`（`npm install` 產生）
- Create: `smoke.mjs`

**Interfaces:**
- Consumes: Task 4 的 HTTP API；Global Constraints 的播放器 DOM 選擇器
- Produces:
  - `match.norm(s) -> string`、`match.lines(project) -> Line[]`、`match.locate(project, speaker, shown) -> Line[]`
    （`Line = {boardId, nodeId, lineIndex, speaker, text, title, type, matched?}`）
  - 面板元素 id（smoke 用）：`#player`、`#banner`、`#fb-open`、`#fb`（`<dialog>`）、`#fb-at`、`#fb-text`、`#fb-voice-kind`、`#fb-voice-chars`、`#fb-voice-should`、`#fb-voice-note`、`#fb-staging input[type=checkbox]`、`#fb-staging-note`、`#fb-note`、`#fb-submit`、`#fb-cancel`、`#fb-here`、`#fb-restart`、`#fb-regrant`、`#fb-history`、`#fb-shot-status`

- [ ] **Step 1：寫比對的失敗測試** `shell/match.test.mjs`

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { locate, lines, norm } from './match.js';

const demo = JSON.parse(readFileSync(new URL('../fixtures/demo/project.json', import.meta.url)));

test('norm 去掉所有空白', () => assert.equal(norm(' 你 好\n。'), '你好。'));

test('lines 包含場景卡文字與每一句', () => {
  const ls = lines(demo).map(l => `${l.nodeId}#${l.lineIndex}`);
  assert.deepEqual(ls, ['s1#0', 'd1#0', 'd1#1', 's2#0', 'd2#0']);
});

test('完全相同', () => {
  const [hit, ...rest] = locate(demo, '旁白', '嚮導指了指另一扇門。');
  assert.equal(rest.length, 0);
  assert.deepEqual([hit.nodeId, hit.lineIndex, hit.matched], ['d1', 1, 'exact']);
});

test('打字效果還沒打完用前綴', () => {
  const [hit] = locate(demo, '嚮導', '歡迎來到');
  assert.deepEqual([hit.nodeId, hit.lineIndex, hit.matched], ['d1', 0, 'prefix']);
});

test('同一句出現在兩張卡，用講者分', () => {
  const p = structuredClone(demo);
  p.boards[0].nodes[3].data.dialogueLines.push({ id: 'l1', speaker: '旁白', text: '歡迎來到示範專案。' });
  assert.equal(locate(p, '', '歡迎來到示範專案。').length, 2);
  const only = locate(p, '旁白', '歡迎來到示範專案。');
  assert.deepEqual(only.map(l => l.nodeId), ['d2']);
});

test('找不到回空陣列', () => {
  assert.deepEqual(locate(demo, '', ''), []);
  assert.deepEqual(locate(demo, '嚮導', '不存在的句子'), []);
});
```

- [ ] **Step 2：跑，確認失敗**

Run: `node --test shell/*.test.mjs`
Expected: FAIL（找不到 `./match.js`）。

- [ ] **Step 3：實作** `shell/match.js`

```js
// 對話框上的字 → 專案裡是哪張卡的第幾句。瀏覽器與 node 共用。
export const norm = s => (s || '').replace(/\s+/g, '');

export function lines(project) {
  const out = [];
  for (const b of project.boards || []) {
    for (const n of b.nodes || []) {
      const d = n.data || {};
      const ls = d.dialogueLines?.length ? d.dialogueLines : (d.text ? [{ speaker: d.speaker, text: d.text }] : []);
      ls.forEach((l, i) => out.push({
        boardId: b.id, nodeId: n.id, lineIndex: i, speaker: l.speaker || '', text: l.text || '',
        title: d.title || '', type: d.type || '',
      }));
    }
  }
  return out;
}

export function locate(project, speaker, shown) {
  const s = norm(shown);
  if (!s) return [];
  const all = lines(project);
  const exact = all.filter(l => norm(l.text) === s).map(l => ({ ...l, matched: 'exact' }));
  const pool = exact.length ? exact : all.filter(l => norm(l.text).startsWith(s)).map(l => ({ ...l, matched: 'prefix' }));
  const same = pool.filter(l => l.speaker === speaker);
  return same.length ? same : pool;
}
```

- [ ] **Step 4：跑，確認通過**

Run: `node --test shell/*.test.mjs`
Expected: 6 個全部 PASS。

- [ ] **Step 5：外層頁面** `shell/index.html`（整份換掉）

```html
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Larch 預覽</title>
  <link rel="stylesheet" href="/shell/panel.css">
</head>
<body>
  <iframe id="player" src="/play/market/local" allow="autoplay; fullscreen"></iframe>
  <div id="banner" hidden></div>
  <button id="fb-open" type="button" title="回饋（F）">回饋</button>

  <dialog id="fb">
    <form method="dialog" id="fb-form">
      <header>
        <strong>回饋</strong>
        <span id="fb-shot-status"></span>
        <button type="button" id="fb-regrant" hidden>重新授權截圖</button>
      </header>

      <label>位置
        <select id="fb-at"></select>
      </label>
      <div class="row">
        <button type="button" id="fb-here">從這張卡開始</button>
        <button type="button" id="fb-restart">從頭播</button>
      </div>

      <details open>
        <summary>台詞</summary>
        <textarea id="fb-text" rows="3"></textarea>
      </details>

      <details>
        <summary>語音</summary>
        <select id="fb-voice-kind">
          <option value="">（沒有問題）</option>
          <option value="misread">唸錯字</option>
          <option value="tone">語氣不對</option>
          <option value="redo">重配</option>
          <option value="other">其他</option>
        </select>
        <input id="fb-voice-chars" placeholder="哪個字（例：質地）">
        <input id="fb-voice-should" placeholder="應該怎麼唸（例：ㄓˊ ㄉㄧˋ）">
        <input id="fb-voice-note" placeholder="備註">
      </details>

      <details>
        <summary>演出</summary>
        <div id="fb-staging">
          <label><input type="checkbox" value="actor">立繪</label>
          <label><input type="checkbox" value="expression">表情</label>
          <label><input type="checkbox" value="background">背景</label>
          <label><input type="checkbox" value="bgm">BGM</label>
          <label><input type="checkbox" value="effect">特效</label>
          <label><input type="checkbox" value="transition">轉場</label>
          <label><input type="checkbox" value="other">其他</label>
        </div>
        <textarea id="fb-staging-note" rows="2" placeholder="哪裡不對"></textarea>
      </details>

      <label>其他備註
        <textarea id="fb-note" rows="2"></textarea>
      </label>

      <ul id="fb-history"></ul>
      <p id="fb-error" hidden></p>

      <footer>
        <button type="button" id="fb-cancel">取消</button>
        <button type="button" id="fb-submit">送出</button>
      </footer>
    </form>
  </dialog>

  <script type="module" src="/shell/panel.js"></script>
</body>
</html>
```

- [ ] **Step 6：樣式** `shell/panel.css`

```css
:root {
  --bg: #111316; --panel: #1b1e23; --line: #33373e; --text: #e8e6e1; --muted: #9a9890;
  --accent: #d9b56b; --danger: #e07a6b;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: var(--bg); color: var(--text);
  font: 14px/1.6 system-ui, "Noto Sans TC", sans-serif; }
#player { position: fixed; inset: 0; width: 100%; height: 100%; border: 0; }
#banner { position: fixed; top: 8px; left: 50%; transform: translateX(-50%); max-width: calc(100% - 32px);
  padding: 6px 12px; border-radius: 6px; background: rgba(20,20,20,.85); border: 1px solid var(--accent);
  z-index: 10; pointer-events: none; }
#banner.error { border-color: var(--danger); }
#fb-open { position: fixed; right: 16px; bottom: 72px; z-index: 10; padding: 8px 14px; border-radius: 999px;
  border: 1px solid var(--accent); background: rgba(20,20,20,.8); color: var(--accent); cursor: pointer; }
body.grabbing #fb-open, body.grabbing #banner { visibility: hidden; }
dialog#fb { width: min(520px, calc(100% - 32px)); max-height: calc(100% - 32px); overflow: auto;
  background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 10px; padding: 16px; }
dialog#fb::backdrop { background: rgba(0,0,0,.35); }
#fb-form { display: grid; gap: 10px; }
#fb-form header, #fb-form footer, .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
#fb-form footer { justify-content: flex-end; }
#fb-shot-status { color: var(--muted); font-size: 12px; margin-left: auto; }
label { display: grid; gap: 4px; }
#fb-staging { display: flex; flex-wrap: wrap; gap: 4px 12px; }
#fb-staging label { display: flex; gap: 4px; align-items: center; }
details { border: 1px solid var(--line); border-radius: 6px; padding: 6px 10px; }
details > * + * { margin-top: 6px; }
summary { cursor: pointer; color: var(--accent); }
input, select, textarea, button { font: inherit; color: var(--text); background: var(--bg);
  border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; width: 100%; }
button { width: auto; cursor: pointer; }
#fb-submit { border-color: var(--accent); color: var(--accent); }
#fb-history { margin: 0; padding-left: 18px; color: var(--muted); font-size: 12px; }
#fb-history .done { color: var(--text); }
#fb-error { color: var(--danger); margin: 0; }
```

- [ ] **Step 7：面板邏輯** `shell/panel.js`

```js
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
```

- [ ] **Step 8：安裝 smoke 用的相依**

Run: `npm init -y >/dev/null && npm pkg set name=larch-preview private=true type=module scripts.smoke="node smoke.mjs" scripts.test="python3 -m unittest discover -s tests && node --test shell/*.test.mjs" && npm pkg delete main keywords author license description version && npm install --save-dev playwright-core`
Expected: `package.json` 裡有 `devDependencies.playwright-core`，產生 `package-lock.json`，`node_modules/` 被 gitignore。

- [ ] **Step 9：冒煙測試** `smoke.mjs`

```js
// 用真 Chrome 驗：真播放器播得動、跳卡帶背景、F 開回饋並附截圖、改檔自動重整停在同一張卡。
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import { cpSync, existsSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = process.env.CHROME || ['/opt/google/chrome/chrome', '/usr/bin/google-chrome'].find(existsSync);
const PORT = 8799;
const BASE = `http://127.0.0.1:${PORT}`;
const dir = mkdtempSync(join(tmpdir(), 'larch-preview-'));
cpSync('fixtures/demo', dir, { recursive: true });
const pj = join(dir, 'project.json');

const server = spawn('python3', ['serve.py', pj, '--port', String(PORT)], { stdio: ['ignore', 'pipe', 'inherit'] });
await new Promise((ok, bad) => {
  server.stdout.on('data', d => d.toString().includes('預覽：') && ok());
  server.on('exit', c => bad(new Error(`serve.py 結束了（${c}）`)));
});

const browser = await chromium.launch({ executablePath: CHROME, headless: false, args: ['--auto-accept-this-tab-capture'] });
const fail = async msg => { console.error('FAIL', msg); await browser.close(); server.kill(); rmSync(dir, { recursive: true }); process.exit(1); };
const step = msg => console.log('ok  ', msg);

try {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
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

  for (let i = 0; i < 6 && !await until('歡迎來到示範專案。', 800); i++) await frame.locator('.vn2-box').click();
  if (!await until('歡迎來到示範專案。', 1000)) await fail('點對話框翻不到第二句');
  step('點對話框會前進');

  await page.request.post(BASE + '/api/lp/card', { data: { card: 'd2' } });
  if (!await until('這裡就是終點。')) await fail('跳卡之後沒出現 d2 的台詞');
  const bg = await page.frame({ url: /play\/market/ }).evaluate(() =>
    [...document.querySelectorAll('*')].some(e => getComputedStyle(e).backgroundImage.includes('/files/bg-b.svg')));
  if (!bg) await fail('跳卡之後背景不是延續下來的 bg-b.svg');
  step('跳卡從 d2 開始，背景延續 bg-b.svg');

  await frame.locator('.vn2-box').click();   // 讓焦點在 iframe 裡
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
```

- [ ] **Step 10：跑 smoke**

Run: `node smoke.mjs`
Expected: 五行 `ok` 加「smoke 全部通過」。會短暫開一個 Chrome 視窗。
若 `F 開回饋` 那步失敗：先確認是 F 被播放器吃掉（在瀏覽器手動按 F 看面板開不開），再看位置判斷；不要放寬斷言。

- [ ] **Step 11：Commit**

```bash
git add shell package.json package-lock.json smoke.mjs
git commit -m "feat: 回饋面板、分頁截圖、自動重整與冒煙測試"
```

---

### Task 7：README 與建立私有 GitHub repo

**Files:**
- Create: `README.md`

- [ ] **Step 1：寫 `README.md`**

````markdown
# larch-preview

在本機用 Larch 自己的播放器預覽專案 JSON，不必推上平台。預覽畫面上可以直接留回饋，回饋寫成檔案，agent 讀了就能修。

**這個 repo 是私有的。**`vendor/larch/` 是 larch.ink 前端程式的快取，版權屬於 Larch，只供本機預覽使用，不可公開散布。

## 用法

```bash
python3 serve.py path/to/project.json      # 開 http://127.0.0.1:8790/
python3 serve.py --market <發佈id>          # 抓市集那份存成 ./larch-<id>/project.json 再預覽
python3 serve.py --project <專案id>         # 用 ~/.config/larch/key 抓自己的專案（只讀）
```

- 專案 JSON 吃三種形狀：裸專案、agent API 的 `{"project": …}`、市集回應。
- 素材可以寫相對路徑（`bg/night.webp`、`voice/l0.mp3`），會從專案 JSON 所在資料夾讀。檔名不要有空白；`..` 一律擋掉。
- 改了專案 JSON，畫面一秒內自動重整並停在原本那張卡。
- 右下角「回饋」或按 `F`。第一次會請你允許分享這個分頁，之後每筆回饋都自動附截圖。
- 回饋面板裡「從這張卡開始」會跳過標題畫面、直接從那張卡播，並補上前面延續下來的背景、BGM、立繪。**變數不會補**，條件分支在跳卡模式下可能跟實際路線不同。

## 給 agent：修回饋的迴圈

1. 開著 `python3 serve.py <project.json>`，請使用者看。
2. 讀待處理的回饋：`python3 -m lp.feedback list <專案資料夾>`（一行一筆 JSON）。
3. 每筆的 `at` 告訴你是哪一張卡（`boardId`、`nodeId`）的第幾句（`lineIndex`）；`matched` 是 `none` 時位置不確定，要看 `note` 與截圖。
   - `text.from → text.to`：照改。**如果專案 JSON 是從劇本產生的，改劇本再重新產生**，不要只改 JSON。
   - `voice`：`kind` 是 `misread`（唸錯，`chars` 是哪個字、`should` 是該怎麼唸）／`tone`／`redo`／`other`。
   - `staging.tags`：`actor` `expression` `background` `bgm` `effect` `transition` `other`，細節在 `staging.note`。
   - `screenshot`：相對於專案資料夾的 PNG 路徑，打開看使用者當下看到什麼。
4. 修完標記：`python3 -m lp.feedback done <專案資料夾> <id> "改了什麼"`。面板上會顯示「已處理」。

**不要直接改寫 `feedback.jsonl`**，要走上面那支 CLI。面板可能正好在寫入，CLI 有檔案鎖。

回饋一筆長這樣：

```json
{"id": "fb-20260924-141903-a1b2", "createdAt": "2026-09-24T14:19:03+08:00",
 "status": "open", "resolution": null,
 "at": {"boardId": "board-main", "nodeId": "n12-spar", "lineIndex": 1,
        "speaker": "森", "text": "終於。這才是一個問題。", "matched": "exact"},
 "text": {"from": "終於。這才是一個問題。", "to": "終於。這才像一個問題。"},
 "voice": {"kind": "misread", "chars": "質地", "should": "ㄓˊ ㄉㄧˋ", "note": ""},
 "staging": {"tags": ["bgm"], "note": "這裡音樂太吵"},
 "screenshot": "feedback/fb-20260924-141903-a1b2.png"}
```

## Larch 前端快取

`.github/workflows/sync.yml` 每天台灣時間 06:17 跑 `sync.py`：larch.ink 首頁的 `index-*.js` 換了就重抓整份前端與內建音效，跑過 `smoke.mjs` 才 commit。失敗會開一張 `sync-failure` issue，舊快取照用。本機要立刻更新：`python3 sync.py`，然後 `git pull` 別人（Action）同步好的版本也行。

## 測試

```bash
npm install          # 只為了 smoke 用的 playwright-core
npm test             # Python unittest + node:test
node smoke.mjs       # 真 Chrome，會開一個視窗
```

## 做不到的事

- 平台自己的 AI 卡（AI 對話、AI 導演）、存檔同步、彈幕、登入相關功能：那些要打 larch.ink 的 API，本機一律回空。
- 播放器用 `new Audio()` 播的語音與音效，開回饋面板時暫停不了（在 DOM 裡的 BGM 會暫停）。
- 插件卡在 sandbox iframe 裡，回饋判斷不出那一刻在插件的哪一步，要自己寫在備註。
````

- [ ] **Step 2：跑全部測試**

Run: `npm test && node smoke.mjs`
Expected: 全部通過。

- [ ] **Step 3：Commit**

```bash
git add README.md
git commit -m "docs: README（用法、agent 修回饋的迴圈、快取同步）"
```

- [ ] **Step 4：建立私有 repo 並推上去**（對外動作，執行前向作者確認一次）

Run: `gh repo create yazelin/larch-preview --private --source . --push`
然後：`gh workflow run sync-larch && sleep 5 && gh run list --workflow sync-larch --limit 1`
Expected: repo 是 private；workflow 成功，輸出「已是最新」。
再跑一次完整管線：`gh workflow run sync-larch -f force=true`，等跑完看 `gh run view --log`，要看到 smoke 的五行 `ok`，而且因為內容沒變，不會多出 commit。
