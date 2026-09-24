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
