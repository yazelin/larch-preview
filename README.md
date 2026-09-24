# larch-preview

在本機用 Larch 自己的播放器預覽專案 JSON，不必推上平台。預覽畫面上可以直接留回饋，回饋寫成檔案，agent 讀了就能修。

**這個 repo 是私有的。**`vendor/larch/` 是 larch.ink 前端程式的快取，版權屬於 Larch，只供本機預覽使用，不可公開散布。

## 用法

```bash
python3 serve.py path/to/project.json      # 開 http://127.0.0.1:8790/
python3 serve.py --market <發佈id>          # 抓市集那份存成 ./larch-<id>/project.json 再預覽
python3 serve.py --project <專案id>         # 用 ~/.config/larch/key 抓自己的專案（只讀）
```

- 專案 JSON 吃三種形狀：裸專案、agent API 的 `{"project": …}`、市集回應。
- **不需要 Larch 專案**：最少只要 `boards`（見 `fixtures/minimal/project.json`），`settings`、`characters`、卡片座標這類平台本來就有的欄位會自動補上。
- 素材可以寫相對路徑（`bg/night.webp`、`voice/l0.mp3`），會從專案 JSON 所在資料夾讀。檔名不要有空白；`..` 一律擋掉。
- 改了專案 JSON，畫面一秒內自動重整並停在原本那張卡。那張卡被拆掉或改名的話，會提示並改成從頭播。
- 伺服器只聽 `127.0.0.1`，而且只收同源的寫入，其他網站寫不進回饋檔。
- 右下角「回饋」或按 `F`。第一次會請你允許分享這個分頁，之後每筆回饋都自動附截圖。
- 回饋面板裡「從這張卡開始」會跳過標題畫面、直接從那張卡播，並補上前面延續下來的背景、BGM、立繪。**變數不會補**，條件分支在跳卡模式下可能跟實際路線不同。
- 按 **←** 回上一句（播放器本身沒有這個功能）：同一張卡就從上一句重播，已經在第一句就回上一張卡的最後一句（照走過的紀錄，沒有紀錄就照連線往回找）。是用跳卡做的，背景、BGM、立繪會補，**變數不會倒回去**。

## 讓其他 AI 用

repo 根目錄的 `SKILL.md` 就是 skill 本體。symlink 到各 agent 的 skill 目錄：

```bash
ln -s ~/larch-preview ~/.claude/skills/larch-preview     # Claude Code
ln -s ~/larch-preview ~/.agents/skills/larch-preview     # Codex、agy 等讀 ~/.agents/skills 的 agent
```

換機器時先 `git clone` 這個私有 repo，再做上面兩行。

## 給 agent：修回饋的迴圈

1. 開著 `python3 serve.py <project.json>`，請使用者看。
2. 讀待處理的回饋：`python3 -m lp.feedback list <專案資料夾>`（一行一筆 JSON）。
3. 每筆的 `at` 告訴你是哪一張卡（`boardId`、`nodeId`）的第幾句（`lineIndex`）；`matched` 是 `none` 時位置不確定，要看 `note` 與截圖。
   - `text.from → text.to`：照改。**如果專案 JSON 是從劇本產生的，改劇本再重新產生**，不要只改 JSON。
   - `voice`：`kind` 是 `misread`（唸錯，`chars` 是哪個字、`should` 是該怎麼唸）／`tone`／`redo`／`other`。
   - `staging.tags`：`actor` `expression` `background` `bgm` `effect` `transition` `other`，細節在 `staging.note`。
   - `screenshot`：相對於專案資料夾的 PNG 路徑，打開看使用者當下看到什麼。
4. 修完標記：`python3 -m lp.feedback done <專案資料夾> <id> "改了什麼"`。面板上會顯示「已處理」。

**不要直接改寫 `feedback.jsonl`**，要走上面那支 CLI。面板可能正好在寫入，CLI 有檔案鎖。

回饋一筆長這樣：

```json
{"id": "fb-20260924-141903-a1b2", "createdAt": "2026-09-24T14:19:03+08:00",
 "status": "open", "resolution": null,
 "at": {"boardId": "board-main", "nodeId": "n12-spar", "lineIndex": 1,
        "speaker": "森", "text": "終於。這才是一個問題。", "matched": "exact"},
 "text": {"from": "終於。這才是一個問題。", "to": "終於。這才像一個問題。"},
 "voice": {"kind": "misread", "chars": "質地", "should": "ㄓˊ ㄉㄧˋ", "note": ""},
 "staging": {"tags": ["bgm"], "note": "這裡音樂太吵"},
 "screenshot": "feedback/fb-20260924-141903-a1b2.png"}
```

## Larch 前端快取

`.github/workflows/sync.yml` 每天台灣時間 06:17 跑 `sync.py`：larch.ink 首頁的 `index-*.js` 換了就重抓整份前端、根目錄的 logo 與內建音效，跑過 `smoke.mjs` 才 commit。失敗會開一張 `sync-failure` issue，舊快取照用。平常 `git pull` 就拿得到 Action 同步好的版本；要立刻更新就自己跑 `python3 sync.py`。

## 測試

```bash
npm install          # 只為了 smoke 用的 playwright-core
npm test             # Python unittest + node:test
node smoke.mjs       # 真 Chrome，會開一個視窗
```

## 做不到的事

- 平台自己的 AI 卡（AI 對話、AI 導演）、存檔同步、彈幕、登入相關功能：那些要打 larch.ink 的 API，本機一律回空。
- 播放器用 `new Audio()` 播的語音與音效，開回饋面板時暫停不了（在 DOM 裡的 BGM 會暫停）。
- 插件卡在 sandbox iframe 裡，回饋判斷不出那一刻在插件的哪一步，要自己寫在備註。
