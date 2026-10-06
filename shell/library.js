// 唯讀素材庫：把專案 JSON 的 media 與 characters 排成一頁看。只讀不寫。

// 相對路徑的素材走 serve.py 的 /files/，跟播放器看到的一樣；含 .. 的不轉（伺服器那邊也會擋）
export function mediaUrl(u) {
  if (!u || /^(https?:|data:|blob:)/.test(u) || u.split('/').includes('..')) return u || '';
  return '/files/' + u.replace(/^\.\//, '');
}

// 每個網址在卡片裡出現幾次。ponytail: 拿整份 boards 的字串去數，網址剛好是別的網址前綴時會多算，真的遇到再改成逐欄比對
export function usage(project, url) {
  if (!url) return 0;
  const hay = JSON.stringify(project.boards || []);
  return hay.split(JSON.stringify(url).slice(1, -1)).length - 1;
}

export function library(project) {
  const media = (project.media || []).map(m => ({ ...m, src: mediaUrl(m.url), used: usage(project, m.url) }));
  const characters = (project.characters || []).map(c => ({
    id: c.id, name: c.name || c.id, portrait: mediaUrl(c.portraitUrl), voice: c.voiceName || '',
    expressions: (c.expressions || []).map(e => ({ name: e.name || e.id, kind: e.kind || '', src: mediaUrl(e.imageUrl), used: usage(project, e.imageUrl) })),
  }));
  return { media, characters };
}
