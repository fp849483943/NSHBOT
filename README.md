# NSHBOT Discord Bot

這是 NSHBOT 的新版 Discord Bot 核心。新版保留原本的 Cog 功能架構，並將主要 AI 對話引擎升級為 **Grok 4.3**。

## 保留功能

- Discord 指令與 Cog 自動載入
- 小布 AI 對話、頻道記憶、引用訊息理解、GM 本地 LM Studio 切換與自動降級
- Grok 對話主引擎
- AI 繪圖、模板管理、圖生圖、GM 繪圖
- 經濟系統、每日簽到、背包、商店、抽獎、求籤
- 道具圖鑑與道具使用
- 深夜模式、伴侶設定、私密包廂
- RSS / YouTube 自動同步
- 地震速報與最新地震查詢
- Flask 網頁控制台

## 新版重點

1. Discord Token 不再寫死在 `bot.py`，改用 `.env` 或環境變數。
2. 文字對話主模型預設為 `grok-4.3`。
3. `utils.py` 重新整理設定檔與玩家資料相容邏輯，保留舊資料格式。
4. 新增 `requirements.txt`、`.env.example`、`.gitignore`。
5. `start.bat` 會自動建立虛擬環境、安裝依賴並啟動 Bot。

## 第一次啟動

### 1. 安裝 Python

請使用 Python 3.10 以上版本。

### 2. 建立 `.env`

把 `.env.example` 複製一份，改名成 `.env`：

```env
DISCORD_BOT_TOKEN=你的DiscordBotToken
XAI_API_KEY=你的xAI_APIKey
COMMAND_PREFIX=!
LOG_LEVEL=INFO
```

### 3. 啟動

Windows 直接雙擊：

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

如果沒有開啟，Bot 可能無法讀取文字訊息、標記、包廂與部分成員相關功能。

## API Key 說明

- `DISCORD_BOT_TOKEN`：Discord Bot 登入用。
- `XAI_API_KEY`：Grok 4.3 文字對話主引擎用。
- 繪圖相關 Key 仍可透過網頁控制台設定。

## 管理員設定

第一次啟動後，請到控制台或 `config.json` 設定：

```json
"admin_ids": ["你的Discord使用者ID"]
```

Discord 使用者 ID 取得方式：

1. Discord 設定開啟「開發者模式」
2. 對自己的帳號按右鍵
3. 複製使用者 ID

## 主要指令範例

- `!幫助`：查看完整功能指南
- `@小布 你好`：呼叫 AI 對話
- `!畫 <提示詞>`：AI 繪圖
- `!背包`：查看背包
- `!商店`：開啟商店
- `!神鑿`：抽獎
- `!機運` / `!求籤`：每日機會與命運
- `!深夜包廂`：建立私密包廂
- `!伴侶設定`：設定深夜伴侶人格
- `!切換大腦`：GM 在 LM Studio / Grok 間切換
- `!大腦測試`：測試 LM Studio 連線

## 安全注意事項

不要把 `.env`、`config.json`、Token、API Key 上傳到 GitHub。新版 `.gitignore` 已預設忽略這些檔案。
