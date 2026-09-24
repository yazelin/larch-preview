# larch-preview 設計

日期：2026-09-24　狀態：待作者確認

## 要解決的事

Agent 寫 Larch 劇本時，要看到成品只能推上平台再開預覽，一趟要幾十秒到幾分鐘，
而且推版子本身有風險（見 larch-vn skill 的整包 PUT、編輯器分頁回寫等坑）。
使用者看到問題後，也只能用文字描述「第幾張卡哪一句」，agent 還要自己去對位置。

larch-preview 讓 agent 在本機直接預覽專案 JSON，畫面與 Larch 線上播放器相同；
使用者在預覽畫面上直接留回饋，回饋落成檔案，agent 讀了就能修。

**成功的樣子**：agent 改完 JSON，瀏覽器自動重整並停在原本那張卡；
使用者按 `F`，填一句「這裡『質地』唸成四聲」，agent 在 `feedback.jsonl` 讀到
卡片 id、第幾句、原文、截圖，不必再問「是哪一句」。

## 範圍

- 私有 repo，本機執行。**不開 GitHub Pages**：repo 內含 Larch 平台前端的快取，
  公開託管屬於再散布，要等平台作者同意。之後要開時只差 fetch 攔截與路徑改寫，架構不變。
- 不自己重寫播放器。畫面一律由 Larch 自己的前端程式渲染。

## 已驗證的前提（2026-09-24 spike）

| 項目 | 結果 |
|---|---|
| 真播放器吃本機 JSON | 本機伺服器轉發 larch.ink 前端，只把 `GET /api/marketplace/<id>?play=1` 換成本機檔，`/play/market/local` 正常播放：標題、立繪、對話框、工具列都在。其餘 API（presence、danmaku、analytics、emojis、auth/session）回 404 不影響播放 |
| 跳到指定卡 | 把目標卡設 `data.start = true`、其他卡拿掉 `start`、`settings.titleScreenEnabled = false`，播放器從那張卡第 0 句開始 |
| 跳卡的副作用 | **延續下來的狀態會丟**：背景是前面場景卡設的，跳過去之後背景變成空的灰底。BGM 同理 |
| 分頁截圖 | 真 Chrome 上 `getDisplayMedia({video:true, preferCurrentTab:true})` 取得分頁畫面，畫到 canvas 後 POST 回伺服器，成功存成 PNG（1268×774） |
| 截圖的限制 | 串流跟著頁面走，**頁面重整後就斷了**，要重新授權 |

## 架構

```
larch-preview/
├─ vendor/larch/        Larch 前端快取：index.html、assets/、sfx/（Action 每日同步）
├─ serve.py             本機伺服器，Python 標準庫，零相依
├─ shell/               外層頁面：index.html、panel.js、panel.css
├─ sync.py              爬 larch.ink，更新 vendor/
├─ smoke.mjs            Playwright 冒煙測試：載入 fixture、斷言真播放器能播
├─ fixtures/demo/       自製示範專案（不含任何別人的作品）
└─ .github/workflows/sync.yml
```

兩層頁面：

```
http://localhost:8790/                  外層（shell）：回饋面板、截圖串流、重載控制
  └─ <iframe src="/play/market/local">  內層：Larch 真播放器
```

分兩層的原因是截圖串流。agent 每次改 JSON 都會觸發重整；
只重整 iframe，外層的串流就不會斷，一整個工作階段只需授權一次。
兩層同源，外層讀得到 iframe 的 DOM（用來判斷目前在哪一句）。

## serve.py

```
python3 serve.py <project.json> [--port 8790]
python3 serve.py --market <發佈id>          # 先抓市集那份存成本機檔再預覽
python3 serve.py --project <專案id>         # 用 ~/.config/larch/key 抓自己的專案（GET，唯讀）
```

路由：

| 路徑 | 行為 |
|---|---|
| `/` | 外層頁面 |
| `/play/market/local` 及其他非 API 路徑 | `vendor/larch/index.html`（SPA 萬用路由） |
| `/assets/*`、`/sfx/*` | `vendor/larch/` 底下的檔案 |
| `GET /api/marketplace/local` | 本機專案，包成市集回應的形狀（`{id, title, startBoardId, publishedBoardIds, project, …}`） |
| `GET /files/<相對路徑>` | 專案 JSON 所在資料夾底下的檔案（本機素材） |
| `GET /api/lp/state` | `{mtime, card}`，外層每秒輪詢，變了就重載 iframe |
| `POST /api/lp/card` | 設定下次從哪張卡開始（`null` 表示從頭、有標題畫面） |
| `POST /api/lp/feedback` | 寫一筆回饋與截圖 |
| `GET /api/lp/feedback` | 讀回全部回饋（面板顯示狀態用） |
| 其他 `/api/*` | 回 `{}`，避免播放器報錯 |

**本機素材**：專案 JSON 裡不是 `http(s):`、`data:`、`/` 開頭的網址視為相對路徑，
回應前改寫成 `/files/<路徑>`。agent 可以先用本機圖與音檔預覽，還沒上傳也行。
`/files/` 只能讀專案資料夾底下的東西，`..` 一律擋掉。

**跳卡**：`card` 有值時，回應前改寫專案：目標卡設 `start`、其餘拿掉 `start`、
關標題畫面。**再補延續狀態**：從原起點沿邊做 BFS 找一條到目標卡的路徑，
照播放器的延續規則累積最後一次設定的 `background`、`bgm`（連同 `bgmVolume`、`bgmLoop`）、
`stage`，目標卡自己沒設的就補上。跨版子的 `boardJump` 照走。
走不到（孤島卡）就不補，面板顯示「此卡無法從起點走到，背景與音樂可能與實際不同」。
變數狀態不補：條件分支在跳卡模式下可能跟實際路線不同，這是已知限制，面板上也標出來。

**不寫回專案 JSON**：所有改寫只發生在回應裡。專案檔只有 agent 會寫。

## 外層頁面與回饋面板

- 右下角「回饋」鈕，快捷鍵 `F`（焦點在 iframe 裡也要能觸發：外層在 iframe 的 document 上掛鍵盤事件）。
- 按下的順序：**先截圖、再開面板**，面板不會入鏡。第一次按會跳出分頁分享的授權；
  使用者拒絕的話，這次與之後都不附截圖，其他照常。
- 自動帶入的位置資訊：讀 iframe 裡 `.vn2-box` 的講者名牌與內文，
  到專案 JSON 所有卡的 `dialogueLines`（沒有就用卡片層 `speaker`/`text`）裡比對，
  得到 `boardId`、`nodeId`、`lineIndex`。比對時先去掉空白與打字效果還沒打完的差異（用「內文是原文的前綴」判斷）。
  命中多張卡就列出候選讓使用者選；都沒命中（選擇卡、插件卡、標題畫面）就讓使用者從卡片清單選，也可以不選（記 `nodeId: null`）。
- 三個分頁，可以同時填：
  - **台詞**：預填原文，直接改。存 `text.from` / `text.to`。
  - **語音**：類型（唸錯字／語氣不對／重配／其他）、哪個字、應該怎麼唸、備註。
  - **演出**：勾選立繪／表情／背景／BGM／特效／轉場／其他，加自由描述。
- 面板角落列出本張卡已有的回饋與狀態（open／done 與 agent 寫的處理說明）。
- 「從這張卡開始」按鈕：`POST /api/lp/card` 設成目前這張，之後 agent 每次改完重整都停在這裡。

## 回饋檔格式

位置：專案 JSON 同一個資料夾底下的 `feedback/`。

`feedback/feedback.jsonl`，每行一筆：

```jsonc
{"id": "fb-20260924-141903-a1",
 "createdAt": "2026-09-24T14:19:03+08:00",
 "status": "open",                       // agent 處理完改成 "done"
 "resolution": null,                     // agent 寫一句做了什麼
 "at": {"boardId": "board-main", "nodeId": "n12-spar", "lineIndex": 1,
        "speaker": "Mori/森之精靈", "text": "終於。這才是一個問題。",
        "matched": "exact"},             // exact | prefix | picked | none
 "text": {"from": "終於。這才是一個問題。", "to": "終於。這才像一個問題。"},
 "voice": {"kind": "misread", "chars": "質地", "should": "ㄓˊ ㄉㄧˋ", "note": ""},
 "staging": {"tags": ["bgm"], "note": "這裡音樂太吵"},
 "note": "",
 "screenshot": "feedback/fb-20260924-141903-a1.png"}
```

沒填的分頁整個鍵省略。agent 改 `status` 時整行重寫；
伺服器寫入用「讀全檔、附加一行、寫暫存檔、rename」，避免跟 agent 同時寫時撕裂。

## 每日同步（sync.py 與 Action）

- `sync.py`：抓 `https://larch.ink/`（帶瀏覽器 User-Agent），取出 `index-<hash>.js`。
  跟 `vendor/larch/VERSION` 相同就結束。不同就從 index.html 出發，
  遞迴抓所有 `assets/*.{js,css,woff2,woff,ttf,png,svg,webp,jpg}` 引用
  （包含 `__vite__mapDeps` 陣列與 CSS 的 `url()`），加上內建 11 個音效
  `/sfx/{rain,thunder,wind,waves,fire,footsteps,knock,whoosh,sting,heartbeat,chime}.mp3`。
  先寫到暫存資料夾，全部成功才換掉 `vendor/larch/`。
- `sync.yml`：每天台灣時間 06:17 跑（避開整點）。`sync.py` → `smoke.mjs`；
  通過就 commit `vendor/larch`；smoke 失敗就開一個 issue 附錯誤訊息，不 commit，舊快取照用。
- 本機也能手動跑 `python3 sync.py`。

## 冒煙測試（smoke.mjs）

用 fixtures/demo 起 serve.py，Playwright（真 Chrome）斷言：
1. `/play/market/local` 出現標題畫面，按開始後出現 `.vn2-box`，內文等於 fixture 第一句。
2. 點對話框能前進到第二句。
3. 跳卡模式（`POST /api/lp/card`）從指定卡開始，而且**背景圖是從前一張場景卡延續過來的那張**。
4. 外層回饋 API 寫得進 `feedback.jsonl`、讀得回來。

截圖流程要真人授權，冒煙測試用 `--auto-accept-this-tab-capture` 旗標跑一次機械驗證。

## 錯誤處理

- 專案 JSON 解析失敗：外層顯示錯誤訊息與行號，保留上一份能播的畫面，不重整 iframe。
- vendor 不存在：serve.py 提示先跑 `python3 sync.py`。
- 截圖授權被拒或串流中斷：該筆回饋不附圖，面板顯示一行提示，可再按一次重新授權。

## 刻意不做

- GitHub Pages 公開版（等平台作者同意）。
- 自己重寫的離線渲染器。
- 回饋自動改專案 JSON：修法交給 agent 判斷。
- 推上 Larch：這個工具只負責看，寫回平台走各專案自己的建置腳本。
- 變數狀態重播（跳卡模式下條件分支可能與實際不同，標示出來即可）。

## 給 agent 的使用說明

README 要寫清楚 agent 的迴圈：
`serve.py` 開著 → 改專案 JSON → 讀 `feedback/feedback.jsonl` 裡 `status: "open"` 的 →
逐筆修 → 把那筆改成 `done` 並寫 `resolution`。
