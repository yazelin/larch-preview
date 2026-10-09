import datetime
import json
import os
import secrets
import sys
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None


ALLOWED = ('at', 'text', 'voice', 'staging', 'note', 'rpg')
TZ = datetime.timezone(datetime.timedelta(hours=8))


def _file(fb_dir):
    return os.path.join(fb_dir, 'feedback.jsonl')


@contextmanager
def _locked(fb_dir):
    os.makedirs(fb_dir, exist_ok=True)
    lock_path = os.path.join(fb_dir, '.lock')
    if fcntl:
        with open(lock_path, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                try:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                except OSError:
                    pass
    elif msvcrt:
        with open(lock_path, 'a+b') as lock:
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            except OSError:
                pass
            try:
                yield
            finally:
                try:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
    else:
        yield


def read_all(fb_dir):
    try:
        with open(_file(fb_dir), encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def _write(fb_dir, rows):
    tmp = _file(fb_dir) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, _file(fb_dir))


def append(fb_dir, entry, png=None):
    now = datetime.datetime.now(TZ)
    fid = f'fb-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}'
    row = {'id': fid, 'createdAt': now.isoformat(timespec='seconds'), 'status': 'open', 'resolution': None}
    row.update({k: entry[k] for k in ALLOWED if k in entry})
    with _locked(fb_dir):
        if png:
            with open(os.path.join(fb_dir, fid + '.png'), 'wb') as f:
                f.write(png)
            row['screenshot'] = f'feedback/{fid}.png'
        _write(fb_dir, read_all(fb_dir) + [row])
    return row


def archive(fb_dir, fid, resolution):
    """標成已處理並搬進 archive/（紀錄與截圖都搬），面板只剩待處理的。封存的紀錄還查得到。"""
    now = datetime.datetime.now(TZ).isoformat(timespec='seconds')
    with _locked(fb_dir):
        rows = read_all(fb_dir)
        hit = next((r for r in rows if r['id'] == fid), None)
        if not hit:
            raise KeyError(f'找不到回饋 {fid}')
        hit.update(status='done', resolution=resolution, doneAt=now)
        adir = os.path.join(fb_dir, 'archive'); os.makedirs(adir, exist_ok=True)
        if hit.get('screenshot'):
            name = os.path.basename(hit['screenshot'])
            if os.path.exists(os.path.join(fb_dir, name)):
                os.replace(os.path.join(fb_dir, name), os.path.join(adir, name))
            hit['screenshot'] = f'feedback/archive/{name}'
        with open(os.path.join(adir, 'archive.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(hit, ensure_ascii=False) + '\n')
        _write(fb_dir, [r for r in rows if r['id'] != fid])
    return hit


def set_status(fb_dir, fid, status, resolution):
    with _locked(fb_dir):
        rows = read_all(fb_dir)
        hit = next((r for r in rows if r['id'] == fid), None)
        if not hit:
            raise KeyError(f'找不到回饋 {fid}')
        hit['status'], hit['resolution'] = status, resolution
        _write(fb_dir, rows)
    return hit


def main(argv):
    if len(argv) >= 2 and argv[0] == 'list':
        for r in read_all(os.path.join(argv[1], 'feedback')):
            if r['status'] == 'open':
                print(json.dumps(r, ensure_ascii=False))
    elif len(argv) == 4 and argv[0] == 'done':
        archive(os.path.join(argv[1], 'feedback'), argv[2], argv[3])
    elif len(argv) == 2 and argv[0] == 'archive-done':   # 舊版留下、已處理但還沒搬走的一次清掉
        fb = os.path.join(argv[1], 'feedback')
        for r in [r for r in read_all(fb) if r['status'] == 'done']:
            archive(fb, r['id'], r.get('resolution'))
    else:
        sys.exit('用法：python3 -m lp.feedback list <專案資料夾>\n'
                 '　　　python3 -m lp.feedback done <專案資料夾> <id> "<處理說明>"   （標成已處理並搬進 feedback/archive/）\n'
                 '　　　python3 -m lp.feedback archive-done <專案資料夾>   （把以前標過已處理的一次搬走）')


if __name__ == '__main__':
    main(sys.argv[1:])
