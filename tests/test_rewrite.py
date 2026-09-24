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

class JumpStageOwnership(unittest.TestCase):
    def proj(self, target):
        return {'activeBoardId': 'b', 'settings': {}, 'boards': [{'id': 'b', 'nodes': [
            card('a', type='dialogue', start=True, stage={'actors': [{'id': 'OLD'}]}, dialogueLines=[{'text': '一'}]),
            card('t', **target),
        ], 'edges': [{'source': 'a', 'target': 't'}]}]}

    def target(self, q):
        return next(n for _, n in rewrite.all_nodes(q) if n['id'] == 't')['data']

    def test_character_layers_only_target_keeps_its_own(self):
        q, _, _ = rewrite.jump_to_card(self.proj(dict(type='dialogue', characterLayers=[{'url': 'new.png'}], dialogueLines=[{'text': '二'}])), 't')
        self.assertNotIn('stage', self.target(q))

    def test_legacy_character_target_keeps_its_own(self):
        q, _, _ = rewrite.jump_to_card(self.proj(dict(type='dialogue', character='c.png', dialogueLines=[{'text': '二'}])), 't')
        self.assertNotIn('stage', self.target(q))

    def test_line_zero_stage_counts_as_owned(self):
        q, _, _ = rewrite.jump_to_card(self.proj(dict(type='dialogue', dialogueLines=[{'text': '二', 'stage': {'actors': []}}])), 't')
        self.assertNotIn('stage', self.target(q))

    def test_bare_target_gets_whole_carried_stage(self):
        q, _, _ = rewrite.jump_to_card(self.proj(dict(type='dialogue', dialogueLines=[{'text': '二'}])), 't')
        self.assertEqual(self.target(q)['stage'], {'actors': [{'id': 'OLD'}]})

    def test_carry_follows_line_level_stage_and_legacy_character(self):
        p = self.proj(dict(type='dialogue', dialogueLines=[{'text': '三'}]))
        p['boards'][0]['nodes'][0]['data']['dialogueLines'].append({'text': '一b', 'stage': {'actors': [{'id': 'LINE'}]}})
        q, _, _ = rewrite.jump_to_card(p, 't')
        self.assertEqual(self.target(q)['stage'], {'actors': [{'id': 'LINE'}]})
        p = self.proj(dict(type='dialogue', dialogueLines=[{'text': '三'}]))
        d = p['boards'][0]['nodes'][0]['data']; d.pop('stage'); d['character'] = 'legacy.png'; d['characterPosition'] = 'left'
        q, _, _ = rewrite.jump_to_card(p, 't')
        t = self.target(q)
        self.assertNotIn('stage', t)
        self.assertEqual((t['character'], t['characterPosition']), ('legacy.png', 'left'))

    def test_fade_out_ends_carried_bgm(self):
        p = self.proj(dict(type='dialogue', dialogueLines=[{'text': '二'}]))
        d = p['boards'][0]['nodes'][0]['data']; d['bgm'] = 'm.mp3'
        d['dialogueLines'].append({'text': '一b', 'bgmAction': 'fadeOut'})
        q, _, _ = rewrite.jump_to_card(p, 't')
        self.assertNotIn('bgm', self.target(q))

if __name__ == '__main__':
    unittest.main()
