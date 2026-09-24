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
