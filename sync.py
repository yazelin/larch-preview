#!/usr/bin/env python3
"""把 larch.ink 的前端抓成本機快取 vendor/larch/。index 的 hash 沒變就不動。"""
import argparse
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
MAX_WORKERS = 8
RETRY_WAIT_SECONDS = 120
MAX_CRAWL_ROUNDS = 4
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


class CrawlError(RuntimeError):
    def __init__(self, files, retryable):
        super().__init__('這些檔案抓不到，快取不完整，不更新：' + '、'.join(files))
        self.retryable = retryable


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
    queue = deque(extract_refs(html))
    seen, missing, roots = set(), [], set(extract_root_refs(html))
    fatal_404, fatal_other = [], []
    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while queue or futures:
            while queue and len(futures) < MAX_WORKERS:
                name = queue.popleft()
                if name in seen:
                    continue
                # 在排入執行緒池時標記，巢狀引用也不會重複下載。
                seen.add(name)
                future = executor.submit(get, f'{BASE}/assets/{name}')
                futures[future] = name
            if not futures:
                continue
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                name = futures.pop(future)
                try:
                    data = future.result()
                except urllib.error.HTTPError as e:
                    if e.code == 404 and HASHED.search(name):
                        fatal_404.append(f'{name}（{e.code}）')
                    elif e.code != 404:
                        fatal_other.append(f'{name}（{e.code}）')
                    else:
                        missing.append(f'{name}（{e.code}）')
                    continue
                with open(os.path.join(dest, 'assets', name), 'wb') as f:
                    f.write(data)
                if name.endswith(('.js', '.mjs', '.css')):
                    text = data.decode('utf-8', 'replace')
                    queue.extend(extract_refs(text))
                    roots.update(extract_root_refs(text))
    os.makedirs(os.path.join(dest, 'root'))

    def fetch_root(name):
        try:
            return name, get(f'{BASE}/{name}'), None
        except urllib.error.HTTPError as e:
            return name, None, e

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        root_futures = [executor.submit(fetch_root, name) for name in sorted(roots)]
        for future in root_futures:
            name, data, error = future.result()
            if error:
                missing.append(f'/{name}（{error.code}）')
                continue
            os.makedirs(os.path.dirname(os.path.join(dest, 'root', name)), exist_ok=True)
            with open(os.path.join(dest, 'root', name), 'wb') as f:
                f.write(data)

    fatal = fatal_404 + fatal_other
    if fatal:
        raise CrawlError(fatal, retryable=bool(fatal_404) and not fatal_other)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        sound_futures = [executor.submit(get, f'{BASE}/sfx/{s}.mp3') for s in SFX]
        sounds = [future.result() for future in sound_futures]
    for s, data in zip(SFX, sounds):
        with open(os.path.join(dest, 'sfx', s + '.mp3'), 'wb') as f:
            f.write(data)
    print(f'抓了 {len(seen) + len(roots) - len(missing)} 個檔案＋{len(SFX)} 個音效')
    if missing:
        print('抓不到（多半是字串裡碰巧長得像檔名）：' + '、'.join(missing))


def crawl_with_retries(dest, html):
    current_html = html
    current_version = version(current_html)
    for round_number in range(1, MAX_CRAWL_ROUNDS + 1):
        shutil.rmtree(dest, ignore_errors=True)
        try:
            crawl(dest, current_html)
            current_version = version(current_html)
            print(f'第 {round_number} 輪同步成功，版本：{current_version}')
            return current_version
        except CrawlError as e:
            if not e.retryable:
                print(f'第 {round_number} 輪遇到不可重試的下載錯誤。')
                raise
            if round_number == MAX_CRAWL_ROUNDS:
                print(f'第 {round_number} 輪仍有帶雜湊檔案 404，已達重試上限。')
                raise

            fresh_url = f'{BASE}/?sync={time.time_ns()}'
            fresh_html = get(fresh_url).decode('utf-8')
            fresh_version = version(fresh_html)
            if fresh_version != current_version:
                print(f'第 {round_number} 輪遇到帶雜湊檔案 404，首頁版本由 {current_version} 變為 {fresh_version}，丟棄本輪並重抓。')
            else:
                print(f'第 {round_number} 輪遇到帶雜湊檔案 404，首頁版本仍為 {current_version}，等待 {RETRY_WAIT_SECONDS} 秒後重抓。')
                time.sleep(RETRY_WAIT_SECONDS)
            current_html = fresh_html
            current_version = fresh_version
    raise AssertionError('爬取輪數超出設定')


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
    if os.path.exists(vfile):
        with open(vfile) as f:
            old = f.read().strip()
    else:
        old = None
    if ver == old and not a.force:
        print(f'已是最新：{ver}')
        return output(False)
    tmp = VENDOR + '.new'
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        ver = crawl_with_retries(tmp, html)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if ver == old and not a.force:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f'已是最新：{ver}')
        return output(False)
    with open(os.path.join(tmp, 'VERSION'), 'w') as f:
        f.write(ver + '\n')
    shutil.rmtree(VENDOR, ignore_errors=True)
    os.rename(tmp, VENDOR)
    print(f'已更新：{old} → {ver}')
    output(True)


if __name__ == '__main__':
    sys.exit(main())
