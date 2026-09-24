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
