@echo off
title NSH 伺服器機器人
color 0A

if not exist .env (
    echo ==========================================
    echo  找不到 .env 設定檔！
    echo ==========================================
    echo  請先複製 .env.example 並改名為 .env
    echo  然後填入 DISCORD_BOT_TOKEN 與 XAI_API_KEY
    echo ==========================================
    pause
    exit /b 1
)

if not exist .venv (
    echo 正在建立 Python 虛擬環境...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

:START
echo ==========================================
echo  正在啟動 NSH Bot / Grok 4.3...
echo ==========================================
python bot.py

echo.
echo  機器人已停止運作或發生崩潰！
echo  將在 5 秒後自動重新啟動...
timeout /t 5
goto START
