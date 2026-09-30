// 對話框上的字 → 專案裡是哪張卡的第幾句。瀏覽器與 node 共用。
export const norm = s => (s || '').replace(/\s+/g, '');

export function lines(project) {
  const out = [];
  for (const b of project.boards || []) {
    for (const n of b.nodes || []) {
      const d = n.data || {};
      const ls = d.dialogueLines?.length ? d.dialogueLines : ((d.text || d.runs) ? [{ speaker: d.speaker, text: d.text, runs: d.runs }] : []);
      ls.forEach((l, i) => out.push({
        boardId: b.id, nodeId: n.id, lineIndex: i, speaker: l.speaker || '',
        text: l.text || (l.runs || []).map(r => r.text || '').join(''),
        title: d.title || '', type: d.type || '',
      }));
    }
  }
  return out;
}

export function locate(project, speaker, shown) {
  const s = norm(shown);
  if (!s) return [];
  const all = lines(project);
  const exact = all.filter(l => norm(l.text) === s).map(l => ({ ...l, matched: 'exact' }));
  const pool = exact.length ? exact : all.filter(l => norm(l.text).startsWith(s)).map(l => ({ ...l, matched: 'prefix' }));
  const same = pool.filter(l => l.speaker === speaker);
  return same.length ? same : pool;
}

// 自動重載要停在哪張卡：候選裡有目前那張就用它，「……」這種重複台詞才不會跳到別張。
export function follow(cands, card) {
  return cands.find(c => c.nodeId === card) || cands[0];
}

// 對話框裡的字：跳過小標註（<rt>，1.9.0 起台詞可以加上方標註）與打字游標，否則比對不到專案裡的台詞。
export function plainText(node) {
  if (node.nodeType === 3) return node.textContent;
  if (node.tagName === 'RT' || node.classList?.contains('typing-caret')) return '';
  return [...node.childNodes].map(plainText).join('');
}
