import base64, json, os, shutil, tempfile, threading, time, unittest, urllib.request, urllib.error
from urllib.parse import quote
import serve
from unittest import mock
from urllib.parse import quote as q

Defaults_MINI = {'boards': [{'id': 'main', 'nodes': [{'id': 'a', 'data': {'type': 'dialogue', 'start': True, 'text': '你好'}}], 'edges': []}]}
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
        os.makedirs(os.path.join(self.vendor, 'root'))
        with open(os.path.join(self.vendor, 'root', 'larch-mark.png'), 'wb') as f:
            f.write(b'\x89PNG')
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
        self.assertEqual(self.get('/larch-mark.png?v=4')[1], 'image/png')
        self.assertEqual(self.status_of('/nope.png'), 404)
        self.assertIn(b'id="player"', self.get('/')[2])
        self.assertEqual(self.status_of('/api/emojis'), 404)   # 回 {} 會讓播放器以為已登入、有存檔
        self.assertEqual(self.post('/api/presence/beat', {}), {})

    def test_card_jump_to_line(self):
        s = self.post('/api/lp/card', {'card': 'd2', 'line': 1})
        self.assertEqual((s['card'], s['line']), ('d2', 1))
        s = self.post('/api/lp/card', {'card': None, 'line': 3})
        self.assertEqual((s['card'], s['line']), (None, 0))

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

    def raw(self, path, data=None, headers=None):
        req = urllib.request.Request(self.base + path, data, headers or {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_missing_card_falls_back_to_start_with_notice(self):
        self.post('/api/lp/card', {'card': 'd2'})
        p = json.load(open(self.pj, encoding='utf-8'))
        p['boards'][0]['nodes'][3]['id'] = 'd2-renamed'
        p['boards'][0]['edges'][2]['target'] = 'd2-renamed'
        json.dump(p, open(self.pj, 'w', encoding='utf-8'))
        s = json.loads(self.get('/api/lp/state')[2])
        self.assertIsNone(s['error'])
        self.assertIsNone(s['card'])
        self.assertEqual(s['notice'], '原本那張卡（d2）不見了，改成從頭播。')
        w = json.loads(self.get('/api/marketplace/local')[2])
        self.assertTrue(w['project']['settings']['titleScreenEnabled'])
        self.assertEqual(self.post('/api/lp/card', {'card': 'nope'})['error'], '找不到卡片 nope')

    def test_structurally_wrong_json_reports_error(self):
        for bad in ([], {'boards': {'x': 1}}, {'boards': ['x']}):
            json.dump(bad, open(self.pj, 'w'))
            s = json.loads(self.get('/api/lp/state')[2])
            self.assertTrue(s['error'], bad)
            self.assertEqual(self.status_of('/api/marketplace/local'), 500)

    def test_cross_origin_and_non_json_posts_rejected(self):
        body = json.dumps({'entry': {'note': 'x'}}).encode()
        self.assertEqual(self.raw('/api/lp/feedback', body, {'Content-Type': 'text/plain'}), 403)
        self.assertEqual(self.raw('/api/lp/feedback', body, {'Content-Type': 'application/json', 'Origin': 'https://evil.example'}), 403)
        self.assertEqual(self.raw('/api/lp/card', json.dumps({'card': 'd2'}).encode(), {'Content-Type': 'text/plain'}), 403)
        self.assertEqual(json.loads(self.get('/api/lp/feedback')[2]), [])
        self.assertEqual(self.raw('/api/lp/feedback', body, {'Content-Type': 'application/json', 'Origin': self.base}), 200)

    def test_foreign_host_rejected(self):
        self.assertEqual(self.raw('/api/lp/project', headers={'Host': 'evil.example'}), 403)
        self.assertEqual(self.raw('/files/bg-a.svg', headers={'Host': f'rebind.evil:{self.srv.server_address[1]}'}), 403)
        self.assertEqual(self.raw('/api/lp/project', headers={'Host': f'localhost:{self.srv.server_address[1]}'}), 200)

    def test_minimal_project_gets_defaults(self):
        json.dump(Defaults_MINI, open(self.pj, 'w', encoding='utf-8'))
        w = json.loads(self.get('/api/marketplace/local')[2])
        self.assertEqual(w['project']['settings'], {})
        self.assertEqual(w['project']['nodes'][0]['position'], {'x': 0, 'y': 0})

    def test_media_proxy_only_fetches_larch_assets(self):
        seen = []
        class R:
            headers = {'Content-Type': 'image/png'}
            def read(self): return b'\x89PNGremote'
            def __enter__(self): return self
            def __exit__(self, *a): pass
        real = urllib.request.urlopen
        def urlopen(req, timeout=None):
            url = getattr(req, 'full_url', req)
            if url.startswith(self.base):          # 測試自己打本機伺服器的請求照常送出
                return real(req) if timeout is None else real(req, timeout=timeout)
            seen.append(url)
            return R()
        ok = 'https://pub-4b20b43f5acf4dfaa3f6ab842daa51cf.r2.dev/x/tiles.png'
        with mock.patch.object(serve.urllib.request, 'urlopen', urlopen):
            status, ctype, body = self.get('/api/media/proxy?url=' + q(ok, safe=''))
            self.assertEqual((status, ctype, body), (200, 'image/png', b'\x89PNGremote'))
            self.assertEqual(self.get('/api/media/proxy?url=' + q('https://larch.ink/plugins/rpg/a.png', safe=''))[0], 200)
            for bad in ('https://evil.example/a.png', 'http://pub-1.r2.dev/a.png', 'file:///etc/passwd',
                        'https://pub-1.r2.dev.evil.example/a.png', 'http://127.0.0.1:22/'):
                self.assertEqual(self.status_of('/api/media/proxy?url=' + q(bad, safe='')), 403, bad)
        self.assertEqual(seen, [ok, 'https://larch.ink/plugins/rpg/a.png'])

    def test_media_proxy_serves_local_files(self):
        status, ctype, _ = self.get('/api/media/proxy?url=' + q('/files/bg-a.svg', safe=''))
        self.assertEqual((status, ctype), (200, 'image/svg+xml'))
        self.assertEqual(self.status_of('/api/media/proxy?url=' + q('/files/../project.json', safe='')), 404)

    def test_busy_port_moves_to_next(self):
        used = self.srv.server_address[1]
        srv, port = serve.bind(serve.Preview(self.pj), used)
        try:
            self.assertNotEqual(port, used)
            self.assertEqual(srv.server_address[1], port)
        finally:
            srv.server_close()

if __name__ == '__main__':
    unittest.main()
