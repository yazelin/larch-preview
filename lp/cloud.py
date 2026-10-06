"""Larch 雲端專案同步模組（拉取與推送）。
支援本機備份、ETag 樂觀鎖防呆與 API 金鑰讀取。
"""

import os
import json
import shutil
import datetime
import urllib.request
import urllib.error


def get_api_key(custom_key=None):
    """取得 Larch API 金鑰，優先序：傳入的自訂金鑰 -> 環境變數 -> ~/.config/larch/key。"""
    if custom_key and str(custom_key).strip():
        return str(custom_key).strip()
    env_key = os.environ.get('LARCH_API_KEY')
    if env_key and env_key.strip():
        return env_key.strip()
    cfg_file = os.path.expanduser('~/.config/larch/key')
    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file, 'r', encoding='utf-8') as f:
                k = f.read().strip()
                if k:
                    return k
        except OSError:
            pass
    return None


def backup_file(file_path):
    """在同一目錄建立帶時間戳的備份檔，防呆防覆蓋。"""
    if not os.path.isfile(file_path):
        return None
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak_path = f"{file_path}.bak.{ts}"
    shutil.copy2(file_path, bak_path)
    return bak_path


def fetch_cloud_project(project_id, api_key=None):
    """向 Larch 官方發送 GET 請求取得專案內容與版本 ETag。"""
    key = get_api_key(api_key)
    if not key:
        raise ValueError("找不到 Larch API 金鑰。請設定 LARCH_API_KEY 或在 ~/.config/larch/key 配置。")
    if not project_id:
        raise ValueError("缺少專案 ID (Project ID)")

    url = f"https://larch.ink/api/agent/projects/{project_id}"
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {key}',
        'User-Agent': 'larch-preview/1.0'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            etag = resp.headers.get('ETag', '').strip('"')
            rev = resp.headers.get('X-Larch-Revision', '')
            data = json.loads(resp.read().decode('utf-8'))
            return data, etag, rev
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f"Larch 雲端回應錯誤 ({e.code}): {err_msg}")
    except OSError as e:
        raise RuntimeError(f"連線至 Larch 雲端失敗: {e}")


def pull(file_path, project_id, api_key=None):
    """從 Larch 雲端拉取專案覆蓋本機檔案，寫入前自動建立備份。"""
    data, etag, rev = fetch_cloud_project(project_id, api_key)
    bak = backup_file(file_path)

    # 確保目錄存在並原子寫入
    tmp_path = f"{file_path}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, file_path)

    return {
        "ok": True,
        "projectId": project_id,
        "etag": etag,
        "revision": rev,
        "backup": bak,
        "title": data.get('name') or project_id
    }


def push(file_path, project_id, api_key=None, summary="從本地 larch-preview 同步"):
    """將本機專案檔案推送至 Larch 雲端（帶 If-Match 樂觀鎖），發送前自動建立本地備份。"""
    key = get_api_key(api_key)
    if not key:
        raise ValueError("找不到 Larch API 金鑰。請設定 LARCH_API_KEY 或在 ~/.config/larch/key 配置。")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"找不到本地專案檔案: {file_path}")

    # 1. 先取得目前雲端最新 ETag
    _, etag, _ = fetch_cloud_project(project_id, key)

    # 2. 備份本地檔案
    bak = backup_file(file_path)

    # 3. 讀取本地專案 JSON
    with open(file_path, 'r', encoding='utf-8') as f:
        local_data = json.load(f)

    # 4. 發送 PUT 替換全專案
    url = f"https://larch.ink/api/agent/projects/{project_id}"
    body = json.dumps({
        "project": local_data,
        "summary": summary
    }, ensure_ascii=False).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='PUT', headers={
        'Authorization': f'Bearer {key}',
        'If-Match': f'"{etag}"' if not etag.startswith('"') else etag,
        'Content-Type': 'application/json',
        'User-Agent': 'larch-preview/1.0'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            new_etag = resp.headers.get('ETag', '').strip('"')
            new_rev = resp.headers.get('X-Larch-Revision', '')
            res_data = json.loads(resp.read().decode('utf-8'))
            return {
                "ok": True,
                "projectId": project_id,
                "etag": new_etag,
                "revision": new_rev,
                "backup": bak,
                "summary": summary,
                "title": res_data.get('name') or project_id
            }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f"推送到 Larch 失敗 ({e.code}): {err_msg}")
    except OSError as e:
        raise RuntimeError(f"連線至 Larch 雲端失敗: {e}")
