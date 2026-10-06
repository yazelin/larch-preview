# larch-preview

在本機用 [Larch](https://larch.ink) 自己的播放器預覽專案 JSON，不必推上雲端平台。預覽畫面上可以直接留回饋，回饋寫成檔案，AI Agent 讀了就能直接修復。

專案具備「1 秒極速熱重載」與「精準回饋閉環」，修改台詞或立繪差分時可在 1 秒內即時看到效果，大幅節省雲端上傳與 API 限流等待時間。

### macOS / Linux

```bash
git clone https://github.com/yazelin/larch-preview ~/larch-preview
cd ~/larch-preview && python3 sync.py
ln -s ~/larch-preview ~/.claude/skills/larch-preview     # Claude Code
ln -s ~/larch-preview ~/.agents/skills/larch-preview     # Codex、agy 等讀 ~/.agents/skills 的 agent
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

> **注意**：播放器前端靜態代碼版權屬於 Larch 官方，本倉庫不內建預先打包的第三方資產。初次安裝或需要更新播放器時，執行 `sync.py` 會自動從官方網站下載最新版前端資源快取到本機 `vendor/larch/`，完全合規且確保為最新版本。

## 用法

```bash
python3 serve.py path/to/project.json      # 開 http://127.0.0.1:8790/
python3 serve.py --market <發佈id>          # 抓市集那份存成 ./larch-<id>/project.json 再預覽
python3 serve.py --project <專案id>         # 用 ~/.config/larch/key 抓自己的線上專案（只讀）
```

- **專案格式**：專案 JSON 吃三種形狀：裸專案、agent API 的 `{"project": …}`、市集回應。
- **不需要 Larch 帳號/專案**：最少只要 `boards`（見 `fixtures/minimal/project.json`），`settings`、`characters`、卡片座標等欄位會由伺服器自動補上。
- **本地素材支援**：素材可以寫相對路徑（`bg/night.webp`、`voice/l0.mp3`），從專案 JSON 所在資料夾讀取，還沒上傳雲端也能完整預覽。
- **1 秒熱重載**：修改專案 JSON 後，畫面一秒內自動重整並停在原本那張卡。
- **白板模式**：按鍵盤 `B` 或點擊上方「白板」按鈕，可無縫切換到 Larch 官方連線白板檢視。
- **即時回饋**：按鍵盤 `F` 彈出回饋面板，自動帶入卡片 ID、行數與即時截圖。

## 給 AI Agent：回饋修復迴圈

1. 在背景開著 `python3 serve.py <project.json>`。
2. 讀取待處理回饋：`python3 -m lp.feedback list <專案資料夾>`（一行一筆 JSON）。
3. 取得位置（`boardId`、`nodeId`、`lineIndex`）與修改內容（`text` / `voice` / `staging` / `screenshot`）。
4. 修改專案後標記完成：`python3 -m lp.feedback done <專案資料夾> <id> "改了什麼"`。

## 授權

MIT © 林亞澤

---

[GitHub](https://github.com/yazelin) · [Facebook](https://www.facebook.com/yaze.lin.gm) · [請亞澤喝咖啡](https://buymeacoffee.com/yazelin) · [亞澤的部落格](https://yazelin.github.io/)
