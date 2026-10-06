# larch-preview

在本機用 [Larch](https://larch.ink) 自己的播放器預覽專案 JSON，不必推上雲端平台。預覽畫面上可以直接留回饋，回饋寫成檔案，AI Agent 讀了就能直接修復。

存檔後大約 1 秒，預覽自己重整，停在原本那張卡、那一句。改的時候不打雲端 API，就不會撞到官方的寫入限流（2026-10-06 實測：agent 連續第 13 次寫入回 429，要等 49～52 秒）。

### macOS / Linux

```bash
git clone https://github.com/yazelin/larch-preview ~/larch-preview
cd ~/larch-preview && python3 sync.py
ln -s ~/larch-preview ~/.claude/skills/larch-preview     # Claude Code
ln -s ~/larch-preview ~/.agents/skills/larch-preview     # Codex、agy、GitHub Copilot CLI 等讀 ~/.agents/skills 的 agent
```

### Windows（PowerShell 原生執行，免 WSL）

在開始功能表搜尋打開「PowerShell」，依序複製貼上執行：

```powershell
git clone https://github.com/yazelin/larch-preview "$HOME\larch-preview"
cd "$HOME\larch-preview"
python sync.py

# 建立 Agent Skill 連結（免管理員權限）
New-Item -ItemType Junction -Path "$HOME\.claude\skills\larch-preview" -Target "$HOME\larch-preview" -Force
New-Item -ItemType Junction -Path "$HOME\.agents\skills\larch-preview" -Target "$HOME\larch-preview" -Force
```

> **注意**：播放器前端的程式碼屬於 Larch 官方，這個 repo 不放。第一次安裝、或 Larch 平台更新之後，跑一次 `sync.py`，它會從 larch.ink 把前端抓到本機的 `vendor/larch/`（第一次大約 26 MB）。前端沒變就不會重抓，要整包重抓加 `--force`。

## 用法

```bash
python3 serve.py path/to/project.json      # 開 http://127.0.0.1:8790/
python3 serve.py --market <發佈id>          # 抓市集那份存成 ./larch-<id>/project.json 再預覽
python3 serve.py --project <專案id>         # 用 ~/.config/larch/key 抓自己的線上專案（只讀）
```

- **專案格式**：專案 JSON 吃三種形狀：裸專案、agent API 的 `{"project": …}`、市集回應。
- **不需要 Larch 帳號/專案**：最少只要 `boards`（見 `fixtures/minimal/project.json`），`settings`、`characters`、卡片座標等欄位會由伺服器自動補上。
- **本地素材支援**：素材可以寫相對路徑（`bg/night.webp`、`voice/l0.mp3`），從專案 JSON 所在資料夾讀取，還沒上傳雲端也能完整預覽。
- **素材放 GitHub 走 jsDelivr**：JSON 填 `cdn.jsdelivr.net/gh/<帳號>/<repo>@<版本>/<路徑>`，本機預覽載得到（RPG 地圖的圖例外）。兩個坑：jsDelivr 把整個 repo 當一個套件，**超過 50 MB 就回 403**（快取過期的那幾張會慢或出不來），作品大了就改成一張卡片一個 tag、網址指到那個 tag；**tag 名不要用「v＋數字」開頭**，`v2-act1` 會被當成版本號而 404。
- **1 秒熱重載**：修改專案 JSON 後，畫面一秒內自動重整並停在原本那張卡。
- **白板模式**：按鍵盤 `B` 或點擊上方「白板」按鈕，切換到 Larch 官方的白板畫面（在本機跑，只能看）。
- **即時回饋**：按鍵盤 `F` 彈出回饋面板，自動帶入卡片 ID、行數與即時截圖。
- **素材庫（唯讀）**：上方「素材庫」另開一頁，列出角色的立繪與差分、專案的圖片音訊影片，標出每個被卡片用到幾次。只能看，要改請改專案 JSON。

## 給 AI Agent：回饋修復迴圈

1. 在背景開著 `python3 serve.py <project.json>`。
2. 讀取待處理回饋：`python3 -m lp.feedback list <專案資料夾>`（一行一筆 JSON）。
3. 取得位置（`boardId`、`nodeId`、`lineIndex`）與修改內容（`text` / `voice` / `staging` / `screenshot`）。
4. 修改專案後標記完成：`python3 -m lp.feedback done <專案資料夾> <id> "改了什麼"`。

## 授權

MIT © 林亞澤

---

[GitHub](https://github.com/yazelin) · [Facebook](https://www.facebook.com/yaze.lin.gm) · [請亞澤喝咖啡](https://buymeacoffee.com/yazelin) · [亞澤的部落格](https://yazelin.github.io/)
