@echo off
title NSH 伺服器機器人
color 0A

:START
echo ==========================================
echo  正在啟動 NSH Bot...
echo ==========================================

:: 執行你的主程式
python bot.py

echo.
echo  機器人已停止運作或發生崩潰！
echo  將在 5 秒後自動重新啟動...
timeout /t 5
goto START