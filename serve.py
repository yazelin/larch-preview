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
        self.notice = None
        self.lock = threading.Lock()

    def load(self):
        with open(self.path, encoding='utf-8') as f:
            return rewrite.unwrap(json.load(f))

    def market(self):
        project, board, reachable = self.load(), None, True
        if self.card and not any(n['id'] == self.card for _, n in rewrite.all_nodes(project)):
            # agent 把這張卡拆掉或改名了：退回從頭播，不要把畫面卡在錯誤訊息
            self.notice = f'原本那張卡（{self.card}）不見了，改成從頭播。'
            self.card = None
        if self.card:
            project, board, reachable = rewrite.jump_to_card(project, self.card)
        return rewrite.wrap_market(rewrite.localize_urls(project), board), reachable

    def state(self):
        s = {'mtime': None, 'card': self.card, 'error': None, 'reachable': True, 'notice': None}
        try:
            s['mtime'] = os.stat(self.path).st_mtime
            _, s['reachable'] = self.market()
        except Exception as e:   # 專案壞成什麼樣子都要回得出一句話，不能讓連線斷掉
            s['error'] = describe(e)
        s['card'], s['notice'] = self.card, self.notice
        return s

    def set_card(self, card):
        """設定下次從哪張卡開始；卡不存在就回錯誤訊息、不改。"""
        if card and not any(n['id'] == card for _, n in rewrite.all_nodes(self.load())):
            return f'找不到卡片 {card}'
        self.card, self.notice = card or None, None
        return None


def describe(e):
    """給人看的錯誤訊息。JSONDecodeError 是 ValueError，訊息本身帶行號。"""
    if isinstance(e, KeyError) and e.args:
        return str(e.args[0])
    if isinstance(e, ValueError):
        return str(e)
    return f'專案格式不對（{type(e).__name__}: {e}）'


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
            if '.' in os.path.basename(path):   # 根目錄的 logo、favicon
                return self.send_file(safe_join(os.path.join(vendor, 'root'), path.lstrip('/')))
            return self.send_file(os.path.join(vendor, 'index.html'))   # SPA 萬用路由

        def do_POST(self):
            path = urlparse(self.path).path
            if not self.host_ok() or (path.startswith('/api/lp/') and not self.origin_ok()):
                return self.send(403, {'error': 'forbidden'})
            try:
                if path == '/api/lp/card':
                    with preview.lock:
                        err = preview.set_card(self.body().get('card'))
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
    print(f'預覽：http://127.0.0.1:{a.port}/　回饋：{os.path.join(os.path.dirname(os.path.abspath(path)), "feedback")}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
