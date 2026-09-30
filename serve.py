#!/usr/bin/env python3
"""larch-preview：用 Larch 自己的播放器在本機預覽專案 JSON。

  python3 serve.py <project.json> [--port 8790]
  python3 serve.py --market <發佈id>
  python3 serve.py --project <專案id>     # 金鑰讀 ~/.config/larch/key，只做 GET
"""
import argparse
import base64
import errno
import json
import mimetypes
import os
import re
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

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
        self.line = 0          # 從那張卡的第幾句開始（按 ← 回上一句用）
        self.notice = None
        self.lock = threading.Lock()

    def load(self):
        with open(self.path, encoding='utf-8') as f:
            return rewrite.fill_defaults(rewrite.unwrap(json.load(f)))

    def market(self):
        project, board, reachable = self.load(), None, True
        if self.card and not any(n['id'] == self.card for _, n in rewrite.all_nodes(project)):
            # agent 把這張卡拆掉或改名了：退回從頭播，不要把畫面卡在錯誤訊息
            self.notice = f'原本那張卡（{self.card}）不見了，改成從頭播。'
            self.card, self.line = None, 0
        if self.card:
            project, board, reachable = rewrite.jump_to_card(project, self.card, self.line)
        return rewrite.wrap_market(rewrite.localize_urls(project), board), reachable

    def state(self):
        s = {'mtime': None, 'card': self.card, 'line': self.line, 'error': None, 'reachable': True, 'notice': None}
        try:
            s['mtime'] = os.stat(self.path).st_mtime
            _, s['reachable'] = self.market()
        except Exception as e:   # 專案壞成什麼樣子都要回得出一句話，不能讓連線斷掉
            s['error'] = describe(e)
        s['card'], s['line'], s['notice'] = self.card, self.line, self.notice
        return s

    def set_card(self, card, line=0):
        """設定下次從哪張卡（第幾句）開始；卡不存在就回錯誤訊息、不改。"""
        if card and not any(n['id'] == card for _, n in rewrite.all_nodes(self.load())):
            return f'找不到卡片 {card}'
        self.card, self.notice = card or None, None
        self.line = max(0, int(line or 0)) if card else 0
        return None


def describe(e):
    """給人看的錯誤訊息。JSONDecodeError 是 ValueError，訊息本身帶行號。"""
    if isinstance(e, KeyError) and e.args:
        return str(e.args[0])
    if isinstance(e, ValueError):
        return str(e)
    return f'專案格式不對（{type(e).__name__}: {e}）'


# /api/media/proxy 只替 Larch 自己的素材網址代抓（RPG 引擎的圖都走這支），其他網址一律拒絕
MEDIA_HOSTS = re.compile(r'^(pub-[0-9a-f]+\.r2\.dev|larch\.ink|[a-z0-9-]+\.larch\.ink)$')
_media_cache = {}   # ponytail: 不設上限的記憶體快取，一次預覽一個專案、素材量有限；真的吃太多記憶體再改 LRU


def fetch_media(url):
    if url not in _media_cache:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            _media_cache[url] = (r.read(), r.headers.get('Content-Type') or 'application/octet-stream')
    return _media_cache[url]


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

        def host_ok(self):
            port = self.server.server_address[1]
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def origin_ok(self):
            """擋掉別的網站對本機 API 發的寫入（回饋檔是 agent 會照著做的指令來源）。"""
            origin = self.headers.get('Origin')
            port = self.server.server_address[1]
            return (self.headers.get('Content-Type') or '').startswith('application/json') and \
                origin in (None, f'http://127.0.0.1:{port}', f'http://localhost:{port}')

        def do_GET(self):
            if not self.host_ok():
                return self.send(403, {'error': 'host not allowed'})
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
            except Exception as e:
                return self.send(500, {'error': describe(e)})
            if path == '/api/media/proxy':
                return self.media_proxy(parse_qs(urlparse(self.path).query).get('url', [''])[0])
            if path.startswith('/api/'):
                # 不認得的 API 回 404，跟播放器在未登入、離線時看到的一樣；回 {} 會被當成已登入、有存檔
                return self.send(404, {'error': 'not available offline'})
            if path.startswith('/files/'):
                return self.send_file(safe_join(preview.dir, path[len('/files/'):]))
            if path.startswith('/shell/'):
                return self.send_file(safe_join(SHELL, path[len('/shell/'):]))
            if path == '/':
                return self.send_file(os.path.join(SHELL, 'index.html'))
            if path.startswith(('/assets/', '/sfx/')):
                return self.send_file(safe_join(vendor, path.lstrip('/')))
            if '.' in os.path.basename(path):   # 根目錄的 logo、favicon
                return self.send_file(safe_join(os.path.join(vendor, 'root'), path.lstrip('/')))
            return self.send_file(os.path.join(vendor, 'index.html'))   # SPA 萬用路由

        def media_proxy(self, url):
            if url.startswith('/files/'):
                return self.send_file(safe_join(preview.dir, url[len('/files/'):]))
            u = urlparse(url)
            if u.scheme != 'https' or not MEDIA_HOSTS.match(u.hostname or ''):
                return self.send(403, {'error': 'only Larch media URLs'})
            try:
                data, ctype = fetch_media(url)
            except urllib.error.HTTPError as e:
                return self.send(e.code, {'error': str(e)})
            except OSError as e:
                return self.send(502, {'error': str(e)})
            return self.send(200, data, ctype)

        def do_POST(self):
            path = urlparse(self.path).path
            if not self.host_ok() or (path.startswith('/api/lp/') and not self.origin_ok()):
                return self.send(403, {'error': 'forbidden'})
            try:
                if path == '/api/lp/card':
                    with preview.lock:
                        b = self.body()
                        err = preview.set_card(b.get('card'), b.get('line', 0))
                    return self.send(200, {**preview.state(), **({'error': err} if err else {})})
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


def bind(preview, port, tries=20):
    """port 被別條工作線佔著就往後找空的，回傳 (server, 實際的 port)。"""
    for p in range(port, port + tries):
        try:
            srv = make_server(preview, p)
            return srv, srv.server_address[1]
        except OSError as e:
            if e.errno != errno.EADDRINUSE:
                raise
    sys.exit(f'{port}–{port + tries - 1} 都被佔用了，用 --port 指定別的')


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
    srv, port = bind(Preview(path), a.port)
    if a.port and port != a.port:
        print(f'{a.port} 已被佔用，改用 {port}', flush=True)
    print(f'預覽：http://127.0.0.1:{port}/　回饋：{os.path.join(os.path.dirname(os.path.abspath(path)), "feedback")}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
