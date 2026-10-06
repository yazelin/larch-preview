---
name: larch-preview
description: 在本機用 Larch 自己的播放器預覽專案 JSON，讓使用者直接在畫面上留回饋（改台詞、標語音、演出問題、附截圖），回饋寫成 feedback.jsonl 給 agent 修。做完或改完 Larch 劇本、要給人看成品之前用；不必推上平台、不必發佈。觸發詞：預覽、給我看、看成品、試玩、本機跑起來、回饋、修台詞、語音唸錯。
---

# larch-preview

本機伺服器供應 Larch 前端的快取，只把專案資料換成本機的 JSON，所以畫面就是 Larch 真正的播放器。
repo 在 `~/larch-preview`。前端快取由 `python3 sync.py` 從官網取得並存放於本機 `vendor/larch/`。

## 什麼時候用

- 寫完或改完劇本，要讓使用者看成品：**先用這個，不要為了看一眼就推版子或發佈**。
- 使用者說「這句唸錯」「這裡立繪不對」：請他在預覽上按 F 留回饋，比口頭描述準（會帶卡片 id、第幾句、截圖）。

## 不需要 Larch 專案

只要一個專案 JSON 檔就能跑，**不需要 Larch 帳號、金鑰或線上專案**。最少只要 `boards`：

```json
{"boards": [{"id": "main",
  "nodes": [
    {"id": "a", "data": {"type": "dialogue", "start": true, "speaker": "小明", "text": "你好。"}},
    {"id": "b", "data": {"type": "dialogue", "speaker": "小華", "text": "第二句。"}}],
  "edges": [{"source": "a", "target": "b"}]}]}
```

其他平台建專案時本來就有的欄位（`settings`、`characters`、`media`、`variables`、`languages`、名稱、卡片的 `position`、邊的 `id`）由 serve.py 自動補上；有寫就用你寫的。
沒補的話播放器會直接壞掉（沒有 `settings` 會壞、卡片沒有 `position` 也會壞），所以別自己刪那段補值。
卡片的 `data` 怎麼寫（`dialogueLines`、`stage.actors`、`background`、`bgm`、選擇卡、場景卡…）照 larch-vn skill 的欄位說明，跟推上平台的格式一樣，之後可以原樣推上去。
範本：`~/larch-preview/fixtures/minimal/project.json`（最小）、`fixtures/demo/project.json`（有場景卡與本機背景圖）。

## 開預覽

```bash
python3 ~/larch-preview/serve.py path/to/project.json      # http://127.0.0.1:8790/
python3 ~/larch-preview/serve.py --market <發佈id>          # 看市集上的作品（存成 ./larch-<id>/project.json）
python3 ~/larch-preview/serve.py --project <專案id>         # 抓自己線上的專案（~/.config/larch/key，只讀）
```

- 專案 JSON 吃三種形狀：裸專案、agent API 的 `{"project": …}`、市集回應。
- 素材可以寫相對路徑（`bg/night.webp`、`voice/l0.mp3`），從 JSON 所在資料夾讀，還沒上傳也能看。檔名不要有空白。
- **serve.py 要在背景一直開著**，把網址給使用者。之後你改 JSON，畫面一秒內自動重整並停在原本那張卡，不必叫使用者重新整理。
- port 被佔用會自動往後找空的，**網址以 serve.py 印出來的那行為準**。常有好幾條工作線同時開預覽，
  所以腳本要從輸出讀網址，或用 `--port 0` 讓系統挑。**關 server 只關自己啟動的那個 PID**，
  不要用「誰佔著這個 port 就關誰」，那可能是別條線的預覽。改了 serve.py 之後要重開，舊的 server 跑的是舊程式。

## 請使用者留回饋時要講的話

- 左上角「回饋」或按 **F**。每次打開預覽頁，**第一次**會跳出「分享這個分頁」的授權，按分享才會附截圖。之後都不用再按。
- 要全螢幕請按 **F11**。播放器自己的「全螢幕」鈕在預覽裡不作用，這是刻意的：它會蓋掉回饋鈕。
- 面板的「從這張卡開始」會跳過標題直接播那張卡，並補上前面延續下來的背景、BGM、立繪。**變數不會補**，條件分支在跳卡模式下可能跟實際路線不同。
- 按 **←** 回上一句（播放器本身沒有這個功能）：同一張卡就從上一句重播，已經在第一句就回上一張卡的最後一句（照走過的紀錄，沒有紀錄就照連線往回找）。是用跳卡做的，背景、BGM、立繪會補，**變數不會倒回去**。
- 左上角「跳到…」選單可以直接跳到任何一張卡；網址也吃參數：`http://127.0.0.1:8790/?card=<卡片id>&line=<第幾句>`，跳卡時網址會跟著更新，存書籤或重新整理都停在那裡。卡片 id 不存在會常駐提示並從頭播。

## 讀回饋、修、標記完成

```bash
python3 -m lp.feedback list <專案資料夾>                      # 在 ~/larch-preview 底下跑；一行一筆 open 的 JSON
python3 -m lp.feedback done <專案資料夾> <id> "改了什麼"        # 修完標記，搬進 feedback/archive/，面板上就不再出現
python3 -m lp.feedback archive-done <專案資料夾>               # 舊版留下、已處理但還沒搬走的一次清掉
```

（不在 `~/larch-preview` 底下的話：`PYTHONPATH=~/larch-preview python3 -m lp.feedback …`）

每筆的欄位：

| 欄位 | 意思 |
|---|---|
| `at` | `boardId`、`nodeId`、`lineIndex`、`speaker`、`text`。`matched` 是 `exact`／`prefix`／`picked`（使用者自己選的）／`none`（位置不確定，看 `note` 與截圖） |
| `text` | `from` → `to`，照改 |
| `voice` | `kind`：`misread`（`chars` 哪個字、`should` 該怎麼唸）／`tone`／`redo`／`other` |
| `staging` | `tags`：`actor` `expression` `background` `bgm` `effect` `transition` `other`，細節在 `note` |
| `screenshot` | 相對於專案資料夾的 PNG，**打開看**使用者當下看到什麼 |

- **專案 JSON 是從劇本產生的，就改劇本再重新產生**，不要只改 JSON，下次重產會被蓋回去。
- **不要直接改寫 `feedback.jsonl`**，要走 CLI：面板可能正在寫入，CLI 有檔案鎖。
- 語音唸錯的修法（同音字替身、重配）看 larch-vn 與 tts skill，這裡只負責把問題帶到你手上。

## 自己要看畫面

截圖授權要真人按，agent 自己看畫面走 Playwright 或 chrome-devtools MCP，直接開 `http://127.0.0.1:8790/`：
- 對話在 iframe `#player` 裡：講者 `.vn2-nameplate b`、內文 `.vn2-text`、對話框 `.vn2-box`。
- **點對話框會翻頁**，要把焦點移進播放器用 `#player` 的 `focus()`，不要用點的。
- 要跳到某張卡：`curl -X POST -H 'Content-Type: application/json' -d '{"card":"<nodeId>","line":0}' http://127.0.0.1:8790/api/lp/card`（`null` 回到從頭播）。
- 完整範例：`~/larch-preview/smoke.mjs`。

## 白板

上方的「白板」鈕（或按 **B**）切到 Larch 官方的白板檢視：整張版子的卡片、連線、分支、場景縮圖，不用登入。
網址帶 `?view=board` 直接開白板。卡片上的 ▶ 從那張卡開始試播，右上「預覽播放」從標題開始；
改了專案 JSON 白板也會自動重整。要給使用者看結構、檢查接線，丟這個比丟 JSON 清楚。
從選單跳卡會自動切回播放。

## RPG 地圖卡

Larch 2.0.0 的 RPG 地圖與戰鬥卡（`larch-rpg-system`）播得動：圖塊、角色、像素字型、血條、任務欄都在。
回饋面板判斷不出 RPG 對話框裡是哪一句，請使用者在「位置」手動選卡片、細節寫在備註。
RPG 用 WASD、方向鍵、q／e，跟預覽的 F（回饋）、B（白板）不衝突；但 2.2.0 起作者可以自訂 RPG 按鍵，
**如果把 F 或 B 設成 RPG 的按鍵，在預覽裡會被回饋或白板先攔走**，改用上方的按鈕操作。
RPG 地圖之間靠地圖事件跳轉、不是白板連線，所以跳到地圖卡時不會出現「從起點走不到」的提示。

## 做不到的事

- 平台自己的 AI 卡（AI 對話、AI 導演）、雲端存檔、彈幕、登入功能：要打 larch.ink 的 API，本機一律沒有。
- 插件卡在 sandbox iframe 裡，回饋判斷不出那一刻在插件的哪一步，請使用者寫在備註。
- 只在 Linux／macOS 跑（回饋檔的鎖用 `fcntl`）。

## 前端快取

`vendor/larch/` 由使用者執行 `python3 ~/larch-preview/sync.py` 自動從 larch.ink 下載快取到本機；日後若官網更新播放器，重新執行 `python3 ~/larch-preview/sync.py` 即可同步最新版。
