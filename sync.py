#!/usr/bin/env python3
"""把 larch.ink 的前端抓成本機快取 vendor/larch/。index 的 hash 沒變就不動。"""
import argparse
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

BASE = 'https://larch.ink'
ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(ROOT, 'vendor', 'larch')
SFX = ['rain', 'thunder', 'wind', 'waves', 'fire', 'footsteps', 'knock', 'whoosh', 'sting', 'heartbeat', 'chime']
REF = re.compile(r'(?:/?assets/|\./)([A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*'
                 r'\.(?:js|mjs|css|woff2?|ttf|otf|png|svg|webp|jpe?g|gif|wasm|json|mp3))')


# 網站根目錄的圖（logo、favicon），不在 assets/ 底下
ROOT_REF = re.compile(r'["\'(`]/([A-Za-z0-9_\-]+\.(?:png|svg|ico|webp)'
                      r'|plugins/(?:[A-Za-z0-9_\-]+/)*[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*'
                      r'\.(?:png|webp|svg|jpe?g|gif|woff2?|otf|ttf|m4a|mp3|ogg|json))')
# plugins/ 底下是內建插件（例如 RPG）的字型、圖、音樂，放在網站根目錄而不是 assets/


def extract_refs(text):
    return sorted(set(REF.findall(text)))


def extract_root_refs(text):
    return sorted(set(ROOT_REF.findall(text)))


def version(html):
    m = re.search(r'assets/(index-[A-Za-z0-9_\-]+\.js)', html)
    if not m:
        raise ValueError('larch.ink 首頁找不到 index-*.js，平台可能改了打包方式')
    return m.group(1)


# Vite 打包出來的檔名尾巴是 8 碼 hash；這種檔抓不到一定是真的缺，不是字串碰巧長得像檔名
HASHED = re.compile(r'-[A-Za-z0-9_\-]{8}\.(?:js|mjs|css|woff2?)$')


def get(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500 or attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3)


def crawl(dest, html):
    os.makedirs(os.path.join(dest, 'assets'))
    os.makedirs(os.path.join(dest, 'sfx'))
    with open(os.path.join(dest, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    queue, seen, missing, roots = extract_refs(html), set(), [], set(extract_root_refs(html))
    fatal = []
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            data = get(f'{BASE}/assets/{name}')
        except urllib.error.HTTPError as e:
            (fatal if e.code != 404 or HASHED.search(name) else missing).append(f'{name}（{e.code}）')
            continue
        with open(os.path.join(dest, 'assets', name), 'wb') as f:
            f.write(data)
        if name.endswith(('.js', '.mjs', '.css')):
            text = data.decode('utf-8', 'replace')
            queue += extract_refs(text)
            roots.update(extract_root_refs(text))
    os.makedirs(os.path.join(dest, 'root'))
    for name in sorted(roots):
        try:
            data = get(f'{BASE}/{name}')
        except urllib.error.HTTPError as e:
            missing.append(f'/{name}（{e.code}）')
            continue
        os.makedirs(os.path.dirname(os.path.join(dest, 'root', name)), exist_ok=True)
        with open(os.path.join(dest, 'root', name), 'wb') as f:
            f.write(data)
    if fatal:
        raise RuntimeError('這些檔案抓不到，快取不完整，不更新：' + '、'.join(fatal))
    for s in SFX:
        with open(os.path.join(dest, 'sfx', s + '.mp3'), 'wb') as f:
            f.write(get(f'{BASE}/sfx/{s}.mp3'))
    print(f'抓了 {len(seen) + len(roots) - len(missing)} 個檔案＋{len(SFX)} 個音效')
    if missing:
        print('抓不到（多半是字串裡碰巧長得像檔名）：' + '、'.join(missing))


def output(changed):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'changed={"true" if changed else "false"}\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    html = get(BASE + '/').decode('utf-8')
    ver = version(html)
    vfile = os.path.join(VENDOR, 'VERSION')
    old = open(vfile).read().strip() if os.path.exists(vfile) else None
    if ver == old and not a.force:
        print(f'已是最新：{ver}')
        return output(False)
    tmp = VENDOR + '.new'
    shutil.rmtree(tmp, ignore_errors=True)
    crawl(tmp, html)
    with open(os.path.join(tmp, 'VERSION'), 'w') as f:
        f.write(ver + '\n')
    shutil.rmtree(VENDOR, ignore_errors=True)
    os.rename(tmp, VENDOR)
    print(f'已更新：{old} → {ver}')
    output(True)


if __name__ == '__main__':
    sys.exit(main())
