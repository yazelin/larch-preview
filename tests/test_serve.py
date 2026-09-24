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
