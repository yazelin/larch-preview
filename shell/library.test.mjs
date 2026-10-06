import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mediaUrl, usage, library } from './library.js';

test('mediaUrl：相對路徑轉 /files/，網址與 .. 不動', () => {
  assert.equal(mediaUrl('bg-a.svg'), '/files/bg-a.svg');
  assert.equal(mediaUrl('./art/a.webp'), '/files/art/a.webp');
  assert.equal(mediaUrl('https://cdn.jsdelivr.net/gh/a/b@main/c.webp'), 'https://cdn.jsdelivr.net/gh/a/b@main/c.webp');
  assert.equal(mediaUrl('../secret.png'), '../secret.png');
  assert.equal(mediaUrl(undefined), '');
});

test('usage 數卡片裡用到幾次，沒用到是 0', () => {
  const p = { boards: [{ nodes: [{ data: { background: 'a.webp' } }, { data: { stage: { actors: [{ url: 'a.webp' }] } } }] }] };
  assert.equal(usage(p, 'a.webp'), 2);
  assert.equal(usage(p, 'b.webp'), 0);
});

test('library 帶出角色差分與素材', () => {
  const p = { boards: [], media: [{ id: 'm1', url: 'x.png', type: 'image' }],
    characters: [{ id: 'c1', name: '甲', portraitUrl: 'p.png', expressions: [{ name: '笑', imageUrl: 'e.png' }] }] };
  const lib = library(p);
  assert.equal(lib.media[0].src, '/files/x.png');
  assert.equal(lib.characters[0].expressions[0].src, '/files/e.png');
  assert.equal(lib.characters[0].portrait, '/files/p.png');
});
