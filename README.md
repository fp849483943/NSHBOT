# NSHBOT Discord Bot

這是 NSHBOT 的新版 Discord Bot 核心。新版保留原本的 Cog 功能架構，並將主要 AI 對話引擎升級為 **Grok 4.3**。

## 目前新版分支

分支名稱：`rewrite-grok43-discord-bot`

這個分支是重寫版，不會影響 `main`。

## 核心功能

- AI 聊天：Grok 文字對話主引擎，保留 LM Studio GM 切換與自動降級。
- 圖片識別：`!看圖` / `!識圖`，可附圖或回覆圖片訊息，用 Grok Vision 分析圖片。
- 圖像生成：`!畫 <提示詞>`，保留 Grok 與第三方 GPT IMAGE2 / APIMart 相容接口。
- 動畫生成：`!動畫 <提示詞>`，新增通用第三方影片生成 API 接口，可接 Runway、Kling、Luma 或其他相容服務。
- 遊戲資訊查詢：`!遊戲資訊 [關鍵字]`，支援 RSS 公告源，也可接外部搜尋 API。
- 每日 / 每週活動提醒：`!新增提醒`、`!提醒列表`、`!刪除提醒`。
- 經濟系統：每日簽到、銅幣、背包、商店、回收、轉帳、贈送。
- 模擬抽獎：保留神鑿抽獎、稀有池、保底與道具池設定。
- 地震預警：中央氣象署正式地震報告、自動推播、最新地震查詢、WebSocket 即時預警接口。
- RSS / YouTube 自動同步。
- Flask 網頁控制台。

## 第一次啟動

### 1. 安裝 Python

建議 Python 3.10 以上版本。

### 2. 建立 `.env`

把 `.env.example` 複製一份，改名成 `.env`：

```env
DISCORD_BOT_TOKEN=你的DiscordBotToken
XAI_API_KEY=你的xAI_APIKey
XAI_MODEL=grok-4.3
XAI_VISION_MODEL=grok-4.3
COMMAND_PREFIX=!
LOG_LEVEL=INFO
```

### 3. 安裝依賴並啟動

Windows 可直接雙擊：

```bat
start.bat
```

或手動執行：

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python bot.py
```

## Discord Developer Portal 必要設定

請確認 Bot 已開啟以下 Privileged Gateway Intents：

- Message Content Intent
- Server Members Intent

否則 Bot 可能無法讀取文字訊息、圖片互動、標記、包廂與部分成員相關功能。

## 重要 API Key / 設定

### Grok 文字與圖片識別

```env
XAI_API_KEY=你的xAI_APIKey
XAI_API_URL_TEXT=https://api.x.ai/v1/responses
XAI_MODEL=grok-4.3
XAI_VISION_MODEL=grok-4.3
```

> 注意：`grok-4.3` 是目前依你的需求預設的 model id。若 xAI 實際 API 名稱不同，只要改 `.env` 或 `config.json` 的模型名稱即可。

### GPT IMAGE2 / 第三方圖片生成

舊版程式仍使用 `openai_api_key` 欄位，實際可填 APIMart 或相容服務 Key。

```env
OPENAI_API_KEY=你的GPT_IMAGE2或第三方圖片API_Key
```

### 動畫 / 影片生成

新增模組 `cogs/video_generation.py` 使用通用第三方 API 接口：

```env
VIDEO_API_URL=
VIDEO_API_KEY=
VIDEO_MODEL=
```

指令：

```text
!動畫 一名少女在雨中的古風街道轉身，電影感，慢鏡頭
```

也可以附上一張圖當參考圖。

### 遊戲資訊查詢

可用 RSS：

```json
"game_news_feeds": [
  "https://example.com/game-news/rss.xml"
]
```

或接自己的搜尋 API：

```env
GAME_SEARCH_API_URL=
GAME_SEARCH_API_KEY=
```

指令：

```text
!遊戲資訊 新職業
!遊戲資訊 更新公告
```

### 每日 / 每週活動提醒

新增提醒：

```text
!新增提醒 20:00 每日 記得打每日副本
!新增提醒 21:30 週一,週三,週五 幫會活動準備集合
```

查看提醒：

```text
!提醒列表
```

刪除提醒：

```text
!刪除提醒 1
```

### 地震預警

正式地震報告需要中央氣象署 Open Data API Key：

```env
CWA_API_KEY=你的中央氣象署APIKey
```

`config.json` 相關欄位：

```json
{
  "enable_eew": true,
  "enable_eew_ws": false,
  "eew_channel_id": "Discord頻道ID",
  "cwa_api_key": "你的中央氣象署APIKey",
  "bot_latitude": 22.68,
  "bot_longitude": 120.30,
  "eew_websocket_url": "wss://ws-eew.teew.tw/"
}
```

指令：

```text
!最新地震
!測試地震
```

## 主要指令範例

- `!幫助`：查看完整功能指南
- `@小布 你好`：呼叫 AI 對話
- `!看圖 這張圖在做什麼？`：Grok 圖片識別
- `!畫 <提示詞>`：AI 繪圖
- `!動畫 <提示詞>`：生成動畫 / 影片
- `!遊戲資訊 <關鍵字>`：查遊戲公告與新資訊
- `!新增提醒 20:00 每日 記得打每日`：新增活動提醒
- `!背包`：查看背包
- `!商店`：開啟商店
- `!神鑿`：抽獎
- `!機運` / `!求籤`：每日機會與命運
- `!最新地震`：查詢中央氣象署最新地震
- `!切換大腦`：GM 在 LM Studio / Grok 間切換
- `!大腦測試`：測試 LM Studio 連線

## 安全注意事項

不要把 `.env`、`config.json`、Token、API Key 上傳到 GitHub。新版 `.gitignore` 已預設忽略這些檔案。
