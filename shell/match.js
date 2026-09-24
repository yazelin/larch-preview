// 對話框上的字 → 專案裡是哪張卡的第幾句。瀏覽器與 node 共用。
export const norm = s => (s || '').replace(/\s+/g, '');

export function lines(project) {
  const out = [];
  for (const b of project.boards || []) {
    for (const n of b.nodes || []) {
      const d = n.data || {};
      const ls = d.dialogueLines?.length ? d.dialogueLines : (d.text ? [{ speaker: d.speaker, text: d.text }] : []);
      ls.forEach((l, i) => out.push({
        boardId: b.id, nodeId: n.id, lineIndex: i, speaker: l.speaker || '', text: l.text || '',
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
