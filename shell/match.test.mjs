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
