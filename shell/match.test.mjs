import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { follow, locate, lines, norm, plainText } from './match.js';

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

test('重載時優先停在目前那張卡，重複台詞不會跳去別張', () => {
  const p = structuredClone(demo);
  p.boards[0].nodes[1].data.dialogueLines[0].text = '……';
  p.boards[0].nodes[3].data.dialogueLines[0] = { id: 'l0', speaker: '嚮導', text: '……' };
  const cands = locate(p, '嚮導', '……');
  assert.deepEqual(cands.map(c => c.nodeId), ['d1', 'd2']);
  assert.equal(follow(cands, 'd2').nodeId, 'd2');
  assert.equal(follow(cands, null).nodeId, 'd1');
  assert.equal(follow([], 'd2'), undefined);
});

test('讀對話框文字時跳過小標註（<rt>）與打字游標', () => {
  const t = s => ({ nodeType: 3, textContent: s });
  const el = (tagName, kids, cls = '') => ({ nodeType: 1, tagName, classList: { contains: c => cls.split(' ').includes(c) }, childNodes: kids });
  const box = el('P', [t('他說'), el('RUBY', [t('漢字'), el('RT', [t('かんじ')])]), t('很難。'), el('SPAN', [], 'typing-caret done')]);
  assert.equal(plainText(box), '他說漢字很難。');
});

test('只有 runs 的台詞也比對得到（標註不算本文）', () => {
  const p = structuredClone(demo);
  p.boards[0].nodes[3].data.dialogueLines[0] = { id: 'l0', speaker: '嚮導', runs: [{ text: '這裡是' }, { text: '終點', marks: [{ type: 'ruby', value: 'ㄓㄨㄥ ㄉㄧㄢˇ' }] }, { text: '。' }] };
  const [hit] = locate(p, '嚮導', '這裡是終點。');
  assert.deepEqual([hit.nodeId, hit.matched], ['d2', 'exact']);
});
