"""回饋檔：<專案資料夾>/feedback/feedback.jsonl，一行一筆。面板與 agent 共用這支，靠檔案鎖避免互相蓋掉。"""
import datetime
import fcntl
import json
import os
import secrets
import sys
from contextlib import contextmanager

ALLOWED = ('at', 'text', 'voice', 'staging', 'note')
TZ = datetime.timezone(datetime.timedelta(hours=8))


def _file(fb_dir):
    return os.path.join(fb_dir, 'feedback.jsonl')


@contextmanager
def _locked(fb_dir):
    os.makedirs(fb_dir, exist_ok=True)
    with open(os.path.join(fb_dir, '.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
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
        set_status(os.path.join(argv[1], 'feedback'), argv[2], 'done', argv[3])
    else:
        sys.exit('用法：python3 -m lp.feedback list <專案資料夾>\n'
                 '　　　python3 -m lp.feedback done <專案資料夾> <id> "<處理說明>"')


if __name__ == '__main__':
    main(sys.argv[1:])
