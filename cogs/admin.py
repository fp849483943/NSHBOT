import discord
from discord.ext import commands
import threading
from flask import Flask, request, render_template_string, session, redirect, jsonify
import os
import json
from datetime import datetime
from utils import load_config, save_config, load_users, save_users, get_user_data

app = Flask(__name__)
app.secret_key = os.urandom(24) 

LOG_FILE = "bot_logs.txt"

# ==========================================
# 📊 讀取 API 統計數據輔助函式
# ==========================================
def load_api_stats():
    today = str(datetime.now().date())
    stats = {"date": today, "count": 0, "image_requests": 0, "chat_requests": 0, "chat_tokens": 0}
    if os.path.exists("api_usage.json"):
        try:
            with open("api_usage.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today:
                    stats.update(data)
        except: pass
    return stats

# ==========================================
# 🔒 登入畫面模板
# ==========================================
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>登入 - NSH 控制台</title>
    <style>
        body { background-color: #121212; color: #fff; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: #1e1e1e; padding: 40px; border-radius: 12px; border: 1px solid #333; text-align: center; box-shadow: 0 8px 24px rgba(0,0,0,0.6); width: 320px; }
        h2 { color: #5865F2; margin-top: 0; margin-bottom: 25px; }
        input[type="password"] { padding: 12px; width: 100%; box-sizing: border-box; margin-bottom: 20px; border-radius: 6px; border: 1px solid #444; background: #121212; color: white; font-size: 16px; }
        input[type="password"]:focus { outline: none; border-color: #5865F2; box-shadow: 0 0 5px rgba(88, 101, 242, 0.5); }
        input[type="submit"] { padding: 12px; background: #5865F2; color: white; border: none; border-radius: 6px; cursor: pointer; width: 100%; font-weight: bold; font-size: 16px; transition: 0.2s; }
        input[type="submit"]:hover { background: #4752C4; }
        .error { color: #ff5555; margin-bottom: 15px; font-weight: bold; background: #3b1a1a; padding: 10px; border-radius: 6px; border: 1px solid #ff5555;}
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔒 NSH 終極控制台</h2>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="password" name="pwd" placeholder="請輸入控制台密碼" required>
            <input type="submit" value="登入 (Login)">
        </form>
    </div>
</body>
</html>
"""

# ==========================================
# ⚙️ 系統控制台模板
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>NSH Bot 終極伺服器控制台</title>
    <style>
        :root { --primary: #5865F2; --bg: #121212; --panel: #1e1e1e; --text: #e0e0e0; --border: #333; --danger: #f04747; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 20px; background-color: var(--bg); color: var(--text); }
        
        .container { max-width: 1800px; width: 96%; margin: auto; }
        h1 { color: var(--primary); text-align: center; border-bottom: 2px solid var(--border); padding-bottom: 15px; margin-bottom: 30px; position: relative; }
        .logout-btn { position: absolute; right: 10px; top: 10px; background: #da373c; color: white; padding: 8px 15px; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: bold; transition: 0.2s; }
        .logout-btn:hover { background: #a1282c; }
        
        .top-layout { display: flex; gap: 20px; margin-bottom: 20px; align-items: stretch; flex-wrap: wrap; }
        .top-stats-section { flex: 0 0 320px; margin: 0; }
        .top-terminal-section { flex: 1; min-width: 600px; margin: 0; }
        
        .dashboard-layout { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }
        .panel-left, .panel-right { flex: 1; min-width: 600px; display: flex; flex-direction: column; gap: 20px; }
        
        .mini-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; align-items: stretch; }
        
        .section { background-color: var(--panel); padding: 25px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 4px 15px rgba(0,0,0,0.3); display: flex; flex-direction: column; height: 100%; box-sizing: border-box; }
        .section-title { font-size: 1.2em; font-weight: bold; color: #fff; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #444; display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
        
        .form-group { margin-bottom: 15px; display: flex; flex-direction: column; }
        label { font-weight: bold; color: #aaa; margin-bottom: 8px; font-size: 0.95em; }
        .hint { font-size: 0.8em; color: #777; margin-top: -5px; margin-bottom: 8px; }
        
        input[type="text"], input[type="password"], input[type="number"], textarea { width: 100%; padding: 10px; border: 1px solid #444; border-radius: 6px; background-color: #121212; color: #fff; box-sizing: border-box; font-family: inherit; }
        input[type="text"]:focus, input[type="password"]:focus, input[type="number"]:focus, textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 5px rgba(88, 101, 242, 0.5); }
        textarea { resize: vertical; min-height: 80px; white-space: pre; }
        
        .row { display: flex; gap: 15px; flex-wrap: wrap; }
        .row > div { flex: 1; min-width: 150px; }
        
        .toggle-group { display: flex; align-items: center; gap: 10px; background: #252526; padding: 10px 15px; border-radius: 8px; border: 1px solid #333; margin-bottom: 15px; }
        input[type="checkbox"] { transform: scale(1.4); accent-color: var(--primary); cursor: pointer; flex-shrink: 0; }
        .toggle-label { font-weight: bold; color: #fff; cursor: pointer; margin: 0; display: inline-block;}
        
        .btn-submit { background-color: var(--primary); color: white; border: none; padding: 15px 30px; font-size: 1.2em; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; margin-top: 30px; transition: background 0.2s; box-shadow: 0 4px 15px rgba(88, 101, 242, 0.3); }
        .btn-submit:hover { background-color: #4752C4; }
        
        .alert { background-color: #166534; color: #4ade80; padding: 15px; border-radius: 8px; border: 1px solid #14532d; text-align: center; font-weight: bold; margin-bottom: 25px; }
        .error-alert { background-color: rgba(240, 71, 71, 0.2); color: #f04747; border: 1px solid #f04747; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 25px; }
        
        /* 卡片共用樣式 */
        .visual-card { background: #252526; padding: 15px; border-radius: 8px; border: 1px solid #444; margin-bottom: 15px; position: relative; transition: 0.3s; }
        .visual-card:hover { border-color: var(--primary); }
        .visual-card .btn-delete { position: absolute; right: 15px; top: 15px; background: transparent; color: var(--danger); border: 1px solid var(--danger); border-radius: 4px; cursor: pointer; padding: 4px 8px; font-size: 0.8em; transition: 0.2s; }
        .visual-card .btn-delete:hover { background: var(--danger); color: white; }
        .btn-add-card { background: #43b581; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; transition: 0.2s; margin-top: 10px; }
        .btn-add-card:hover { background: #3ca374; }
        
        /* 提醒任務專屬樣式 */
        .day-checkboxes { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; margin-top: 5px; }
        .day-checkboxes label { display: flex; align-items: center; gap: 5px; background: #1e1e1e; padding: 6px 12px; border-radius: 20px; border: 1px solid #333; cursor: pointer; color: #aaa; font-size: 0.9em; transition: 0.2s; margin: 0; }
        .day-checkboxes input[type="checkbox"] { display: none; }
        .day-checkboxes input[type="checkbox"]:checked + span { color: #fff; font-weight: bold; }
        .day-checkboxes label:has(input[type="checkbox"]:checked) { background: var(--primary); border-color: #4752C4; }
        
        .stat-container { flex: 1; display: flex; flex-direction: column; gap: 15px; justify-content: space-between; }
        .stat-box { flex: 1; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #334155; transition: 0.3s; display: flex; flex-direction: column; justify-content: center; }
        
        .cmd-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .cmd-grid .form-group { margin-bottom: 0; display: flex; flex-direction: row; align-items: center; gap: 8px; }
        .cmd-grid label { width: 50px; margin-bottom: 0; color: #ccc; flex-shrink: 0; text-align: right; }
        .cmd-grid input { flex: 1; padding: 8px 10px; }

        .log-terminal { background-color: #0c0c0c; color: #a3e635; font-family: 'Consolas', 'Courier New', monospace; height: 350px; overflow-y: auto; padding: 15px; border-radius: 8px; border: 1px solid #333; font-size: 0.9em; white-space: pre-wrap; word-wrap: break-word; line-height: 1.4; margin: 0; }
        .log-terminal::-webkit-scrollbar { width: 8px; }
        .log-terminal::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
        
        @media (max-width: 1400px) {
            .top-stats-section { flex: 1; min-width: 100%; }
            .stat-container { flex-direction: row; }
        }
        @media (max-width: 1200px) {
            .panel-left, .panel-right { min-width: 100%; }
        }
        @media (max-width: 768px) {
            .stat-container { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>👑 NSH Bot 終極伺服器控制台 <a href="/logout" class="logout-btn">🚪 登出系統</a></h1>
        
        {% if message %}
            {% if '❌' in message %}
                <div class="error-alert">{{ message }}</div>
            {% else %}
                <div class="alert">{{ message }}</div>
            {% endif %}
        {% endif %}
        
        <div class="top-layout">
            <div class="section top-stats-section">
                <div class="section-title">
                    📊 API 消耗 (今日)
                    <span id="api-status" style="margin-left: auto; font-size: 0.65em; color: #94a3b8; font-weight: normal; background: #1e293b; padding: 4px 10px; border-radius: 12px; border: 1px solid #334155; min-width: 135px; text-align: center; white-space: nowrap; flex-shrink: 0; display: inline-block;">實時同步待命</span>
                </div>
                <div class="stat-container">
                    <div class="stat-box" style="background: #1e293b;" id="box-chat-req">
                        <div style="color: #94a3b8; font-size: 0.9em; margin-bottom: 5px;">💬 聊天請求總數</div>
                        <div id="stat-chat-req" style="font-size: 28px; font-weight: bold; color: #38bdf8;">{{ api_stats.chat_requests }} 次</div>
                    </div>
                    <div class="stat-box" style="background: #422006; border-color: #713f12;" id="box-chat-tok">
                        <div style="color: #fdba74; font-size: 0.9em; margin-bottom: 5px;">🪙 Token 總消耗</div>
                        <div id="stat-chat-tok" style="font-size: 28px; font-weight: bold; color: #fbbf24;">{{ api_stats.chat_tokens }} T</div>
                    </div>
                    <div class="stat-box" style="background: #14532d; border-color: #166534;" id="box-img-req">
                        <div style="color: #86efac; font-size: 0.9em; margin-bottom: 5px;">🎨 生圖請求總數</div>
                        {% set img_req = api_stats.image_requests if api_stats.image_requests > 0 else api_stats.count %}
                        <div id="stat-img-req" style="font-size: 28px; font-weight: bold; color: #4ade80;">{{ img_req }} 次</div>
                    </div>
                </div>
            </div>

            <div class="section top-terminal-section">
                <div class="section-title">
                    🖥️ 終端機實時監測日誌 (Terminal Logs)
                    <div style="margin-left: auto; display: flex; gap: 15px; align-items: center; flex-shrink: 0;">
                        <label style="font-size: 0.75em; margin:0; color: #ccc; font-weight: normal; cursor: pointer; white-space: nowrap; display: flex; align-items: center;">
                            <input type="checkbox" id="auto-scroll" checked style="margin-right: 5px;"> 自動滾動
                        </label>
                        <button type="button" onclick="clearLogs()" style="background: #da373c; color: white; border: none; border-radius: 4px; padding: 4px 10px; font-size: 0.75em; font-weight: bold; cursor: pointer; transition: 0.2s; white-space: nowrap;">🗑️ 清空面板</button>
                    </div>
                </div>
                <div id="log-terminal" class="log-terminal">等待系統初始化日誌...</div>
            </div>
        </div>

        <form method="POST">
            <div class="dashboard-layout">
                <!-- 👈 左側面板 -->
                <div class="panel-left">
                    <div class="mini-grid">
                        <div class="section">
                            <div class="section-title">⚙️ 基礎與 AI 設定</div>
                            <div class="form-group"><label>機器人暱稱</label><input type="text" name="bot_name" value="{{ config.bot_name }}"></div>
                            <div class="form-group"><label style="color: #ff5555;">🔒 控制台登入密碼</label><input type="text" name="admin_password" value="{{ config.get('admin_password', '123456') }}"></div>
                            <div class="form-group"><label>管理員 ID (逗號分隔)</label><input type="text" name="admin_ids" value="{{ config.admin_ids | join(',') }}"></div>
                            
                            <!-- 🌟 新增了 OpenAI 的輸入欄位 -->
                            <div class="form-group">
                                <label style="color: #4ade80;">🔑 Grok API Key (文字/對話)</label>
                                <input type="password" name="grok_api_key" value="{{ config.get('grok_api_key', '') }}" placeholder="xai-xxxxxxxxxxxxxxxxxxx">
                            </div>
                            <div class="form-group" style="margin-bottom: 0;">
                                <label style="color: #10b981;">🖼️ OpenAI API Key (DALL-E 繪圖)</label>
                                <input type="password" name="openai_api_key" value="{{ config.get('openai_api_key', '') }}" placeholder="sk-xxxxxxxxxxxxxxxxxxx">
                            </div>
                        </div>

                        <div class="section">
                            <div class="section-title">🌙 深夜模式設定</div>
                            <div class="toggle-group">
                                <input type="checkbox" id="enable_late_night_mode" name="enable_late_night_mode" {% if config.get('enable_late_night_mode', True) %}checked{% endif %}>
                                <label for="enable_late_night_mode" class="toggle-label">啟用深夜模式 (需大人的證明)</label>
                            </div>
                            <div class="row">
                                <div class="form-group"><label>開始時間 (0-23)</label><input type="number" name="late_night_start" value="{{ config.get('late_night_start', 23) }}" min="0" max="23"></div>
                                <div class="form-group"><label>結束時間 (0-23)</label><input type="number" name="late_night_end" value="{{ config.get('late_night_end', 5) }}" min="0" max="23"></div>
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label>深夜模式 AI 覆寫提示詞</label>
                                <textarea name="late_night_prompt" style="height: 100%;">{{ config.get('late_night_prompt', '') }}</textarea>
                            </div>
                        </div>
                    </div>

                    <div class="section">
                        <div class="section-title">🧠 AI 系統提示詞 (System Prompt)</div>
                        <div class="form-group" style="margin-bottom: 0;"><textarea name="system_prompt" style="height: 100px;">{{ config.system_prompt }}</textarea></div>
                    </div>

                    <div class="mini-grid">
                        <div class="section">
                            <div class="section-title">💰 經濟與消耗限制</div>
                            <div class="form-group"><label>每日簽到獲得銅幣</label><input type="number" name="daily_sign_coins" value="{{ config.get('daily_sign_coins', 500) }}"></div>
                            <div class="form-group"><label>AI 繪圖消耗【繪圖券】數量</label><input type="number" name="ai_image_ticket_cost" value="{{ config.get('ai_image_ticket_cost', 1) }}"></div>
                            <div class="form-group"><label>全服每日生圖總數上限</label><input type="number" name="ai_image_daily_limit" value="{{ config.get('ai_image_daily_limit', 50) }}"></div>
                        </div>

                        <div class="section">
                            <div class="section-title">⌨️ 指令名稱自訂</div>
                            <div class="cmd-grid">
                                <div class="form-group"><label>抽獎:</label><input type="text" name="cmd_gacha" value="{{ config.get('cmd_gacha', '神鑿') }}"></div>
                                <div class="form-group"><label>求籤:</label><input type="text" name="cmd_divination" value="{{ config.get('cmd_divination', '機運') }}"></div>
                                <div class="form-group"><label>商店:</label><input type="text" name="cmd_shop" value="{{ config.get('cmd_shop', '商店') }}"></div>
                                <div class="form-group"><label>使用:</label><input type="text" name="cmd_use" value="{{ config.get('cmd_use', '使用') }}"></div>
                                <div class="form-group"><label>背包:</label><input type="text" name="cmd_backpack" value="{{ config.get('cmd_backpack', '背包') }}"></div>
                                <div class="form-group"><label>簽到:</label><input type="text" name="cmd_sign" value="{{ config.get('cmd_sign', '簽到') }}"></div>
                                <div class="form-group"><label>幫助:</label><input type="text" name="cmd_help" value="{{ config.get('cmd_help', '幫助') }}"></div>
                                <div class="form-group"><label style="width:auto;">GM錢:</label><input type="text" name="cmd_gm" value="{{ config.get('cmd_gm', 'gm_money') }}"></div>
                            </div>
                        </div>
                    </div>

                    <div class="section">
                        <div class="section-title">🛒 萬事屋市場與回收定義</div>
                        <div class="row">
                            <div class="form-group">
                                <label>一般商店 (格式 物品名:售價)</label>
                                <textarea name="shop_items" style="height:120px;">{% if config.shop_items %}{% for k, v in config.shop_items.items() %}{{ k }}:{{ v }}&#13;&#10;{% endfor %}{% else %}鑒石神鑿:180&#13;&#10;大人的證明:9999&#13;&#10;繪圖券:50{% endif %}</textarea>
                            </div>
                            <div class="form-group">
                                <label>星期四黑市 (格式 物品名:售價:庫存)</label>
                                <textarea name="hidden_shop_items" style="height:120px;">{% for k, v in config.hidden_shop_items.items() %}{{ k }}:{{ v }}&#13;&#10;{% endfor %}</textarea>
                            </div>
                        </div>
                        <div class="row">
                            <div class="form-group" style="margin-bottom:0;">
                                <label>商會回收價格 (格式 物品名:收購價)</label>
                                <textarea name="sell_prices" style="height:100px;">{% for k, v in config.sell_prices.items() %}{{ k }}:{{ v }}&#13;&#10;{% endfor %}</textarea>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 👉 右側面板 -->
                <div class="panel-right">
                    <div class="section">
                        <div class="section-title">📡 官方公告自動同步 (RSS)</div>
                        <div class="row" style="margin-top: 10px;">
                            <div class="form-group" style="margin-bottom:0;">
                                <label>RSS 訂閱網址</label>
                                <input type="text" name="rss_feed_url" value="{{ config.get('rss_feed_url', '') }}" placeholder="留空則使用預設逆水寒官網爬蟲">
                            </div>
                        </div>
                        <div class="row" style="margin-top: 10px;">
                            <div class="form-group" style="margin-bottom:0;"><label>發送正式公告頻道 ID</label><input type="text" name="rss_channel_id" value="{{ config.get('rss_channel_id', '') }}"></div>
                            <div class="form-group" style="margin-bottom:0;"><label>🌟 AI 發表感言頻道 ID</label><input type="text" name="rss_chat_channel_id" value="{{ config.get('rss_chat_channel_id', '') }}"></div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <div class="section-title">📺 YouTube 自動轉貼設定 (副本打法/攻略)</div>
                        <div class="form-group">
                            <label>目標 YouTube 頻道 ID (一行一個)</label>
                            <div class="hint" style="color: #60a5fa;">💡 取得方式：進入該 YouTube 頻道首頁 -> 點擊簡介/關於 -> 分享 -> 複製頻道 ID (通常是 UC 開頭的字串)</div>
                            <textarea name="yt_channel_ids" style="height: 80px;" placeholder="例如：\nUCxxxxxxxxx\nUCyyyyyyyyy">{{ config.get('yt_channel_ids', []) | join('\n') }}</textarea>
                        </div>
                        <div class="form-group" style="margin-bottom:0;">
                            <label>YouTube 推播 Discord 頻道 ID</label>
                            <input type="text" name="yt_discord_channel_id" value="{{ config.get('yt_discord_channel_id', '') }}" placeholder="留空則不推播">
                        </div>
                    </div>
                    
                    <!-- 🌟 更新 EEW 地震速報設定區域 -->
                    <div class="section" style="border-color: #f87171;">
                        <div class="section-title" style="color: #f87171;">🚨 EEW 緊急地震速報系統</div>
                        
                        <div class="toggle-group" style="margin-top: 10px; background: #3f1515; border-color: #7f1d1d;">
                            <input type="checkbox" id="enable_eew" name="enable_eew" {% if config.get('enable_eew', False) %}checked{% endif %}>
                            <label for="enable_eew" class="toggle-label" style="color: #fca5a5;">啟用 EEW 系統 (自動輪詢與即時廣播)</label>
                        </div>
                        
                        <div class="form-group" style="margin-top: 10px;">
                            <label>發送警報的頻道 ID</label>
                            <input type="text" name="eew_channel_id" value="{{ config.get('eew_channel_id', '') }}" placeholder="請輸入要接收地震速報的頻道 ID">
                        </div>
                        
                        <div class="form-group" style="margin-top: 10px;">
                            <label>📡 WebSocket 廣播節點 URL</label>
                            <input type="text" name="eew_websocket_url" value="{{ config.get('eew_websocket_url', 'wss://ws-eew.teew.tw/') }}" placeholder="預設: wss://ws-eew.teew.tw/">
                        </div>
                        
                        <div class="row">
                            <div class="form-group" style="margin-bottom:0;">
                                <label>📍 機器人所在緯度 (Latitude)</label>
                                <input type="text" name="bot_latitude" value="{{ config.get('bot_latitude', 22.68) }}" placeholder="例如: 22.68">
                            </div>
                            <div class="form-group" style="margin-bottom:0;">
                                <label>📍 機器人所在經度 (Longitude)</label>
                                <input type="text" name="bot_longitude" value="{{ config.get('bot_longitude', 120.30) }}" placeholder="例如: 120.30">
                            </div>
                        </div>
                        <div class="hint" style="color: #fca5a5; margin-top: 5px;">💡 座標用於精準計算「S波抵達倒數時間」與「預估當地最大震度」。預設為高雄市左營區。</div>
                    </div>

                    <div class="section">
                        <div class="section-title">💭 小布無聊冒泡設定</div>
                        <div class="row" style="margin-top: 10px;">
                            <div class="form-group" style="margin-bottom:0;"><label>安靜多久後觸發 (分鐘)</label><input type="number" name="bubble_silence_minutes" value="{{ config.get('bubble_silence_minutes', 60) }}" min="1"></div>
                            <div class="form-group" style="margin-bottom:0;"><label>觸發機率 (0~100%)</label><input type="number" name="bubble_probability" value="{{ config.get('bubble_probability', 30) }}" min="0" max="100"></div>
                        </div>
                    </div>

                    <div class="section">
                        <div class="section-title">⏰ 公會活動定時提醒小秘書</div>
                        <div class="form-group" style="margin-top: 10px;">
                            <label>預設提醒頻道 ID</label>
                            <input type="text" name="reminder_channel_id" value="{{ config.get('reminder_channel_id', config.get('rss_channel_id', '')) }}">
                        </div>
                        <textarea name="scheduled_reminders" id="hidden_reminders" style="display:none;"></textarea>
                        <div id="reminders-container" style="margin-top: 15px;"></div>
                        <button type="button" class="btn-add-card" onclick="addReminderCard()">➕ 新增一筆定時提醒</button>
                    </div>

                    <div class="section" style="flex: 1;">
                        <div class="section-title">🎰 抽獎系統、神爐與獎池設定</div>
                        <div class="row">
                            <div class="toggle-group" style="flex: 1;">
                                <input type="checkbox" id="enable_gacha" name="enable_gacha" {% if config.get('enable_gacha', True) %}checked{% endif %}>
                                <label for="enable_gacha" class="toggle-label">啟用鑒石開鑿</label>
                            </div>
                            <div class="toggle-group" style="flex: 1;">
                                <input type="checkbox" id="enable_auto_convert" name="enable_auto_convert" {% if config.get('enable_auto_convert', True) %}checked{% endif %}>
                                <label for="enable_auto_convert" class="toggle-label">啟用自動熔煉</label>
                            </div>
                        </div>
                        <div class="toggle-group">
                            <input type="checkbox" id="enable_grand_effect" name="enable_grand_effect" {% if config.get('enable_grand_effect', True) %}checked{% endif %}>
                            <label for="enable_grand_effect" class="toggle-label">啟用天賞專屬華麗特效 (全頻廣播)</label>
                        </div>
                        
                        <div class="row">
                            <div class="form-group"><label>天賞保底抽數</label><input type="number" name="gacha_pity_count" value="{{ config.get('gacha_pity_count', 180) }}"></div>
                            <div class="form-group"><label>天賞機率 (千分之)</label><input type="number" name="gacha_rate_grand" value="{{ config.get('gacha_rate_grand', 4) }}"></div>
                            <div class="form-group"><label>奇賞機率 (千分之)</label><input type="number" name="gacha_rate_rare" value="{{ config.get('gacha_rate_rare', 40) }}"></div>
                            <div class="form-group"><label>熔煉比率</label><input type="number" name="auto_convert_rate" value="{{ config.get('auto_convert_rate', 20) }}"></div>
                        </div>
                        
                        <div style="border-top: 1px dashed #444; margin: 15px 0 20px 0;"></div>
                        <div class="form-group">
                            <label style="color:#ffd700;">✨ 【天賞】獎池 (機率權重制 格式：物品:權重)</label>
                            <textarea name="pool_grand" style="height:80px; background: #0c0c0c;">{% if config.pool_grand is mapping %}{% for k, v in config.pool_grand.items() %}{{ k }}:{{ v }}{% if not loop.last %}, {% endif %}{% endfor %}{% else %}{{ config.pool_grand | join(', ') }}{% endif %}</textarea>
                        </div>
                        <div class="row" style="margin-top: 10px;">
                            <div class="form-group" style="margin-bottom:0;"><label style="color:#b388ff;">💎 【奇賞】獎池</label><textarea name="pool_rare" style="height: 100px; background: #0c0c0c;">{{ config.pool_rare | join(', ') }}</textarea></div>
                            <div class="form-group" style="margin-bottom:0;"><label style="color:#a0a0a0;">📦 【凡賞】獎池</label><textarea name="pool_normal" style="height: 100px; background: #0c0c0c;">{{ config.pool_normal | join(', ') }}</textarea></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <button type="submit" class="btn-submit" onclick="saveAllSettings()">💾 儲存並套用所有設定</button>
        </form>
    </div>

    <script>
        // ==========================================
        // ⏰ 提醒排程管理器
        // ==========================================
        const defaultReminders = {{ config.get('scheduled_reminders', []) | tojson }};
        const reminderContainer = document.getElementById('reminders-container');

        function addReminderCard(data = null) {
            const card = document.createElement('div');
            card.className = 'visual-card';
            
            const days = data && data.days ? data.days : [];
            const isChecked = (day) => days.includes(day) ? 'checked' : '';
            const randomId = Math.floor(Math.random() * 10000);
            
            card.innerHTML = `
                <button type="button" class="btn-delete" onclick="this.parentElement.remove()">🗑️ 刪除任務</button>
                <div class="row">
                    <div class="form-group"><label>任務名稱</label><input type="text" class="r-name" placeholder="例如: 幫派戰提醒" value="${data && data.name ? data.name : ''}"></div>
                    <div class="form-group"><label>專屬發送頻道 ID</label><input type="text" class="r-channel" placeholder="留空則使用上方預設頻道" value="${data && data.channel_id ? data.channel_id : ''}"></div>
                </div>
                <div class="form-group" style="margin-bottom: 10px;">
                    <label>重複星期 (可複選)</label>
                    <div class="day-checkboxes">
                        <label><input type="checkbox" class="r-day" value="0" ${isChecked(0)}><span>週一</span></label>
                        <label><input type="checkbox" class="r-day" value="1" ${isChecked(1)}><span>週二</span></label>
                        <label><input type="checkbox" class="r-day" value="2" ${isChecked(2)}><span>週三</span></label>
                        <label><input type="checkbox" class="r-day" value="3" ${isChecked(3)}><span>週四</span></label>
                        <label><input type="checkbox" class="r-day" value="4" ${isChecked(4)}><span>週五</span></label>
                        <label><input type="checkbox" class="r-day" value="5" ${isChecked(5)}><span>週六</span></label>
                        <label><input type="checkbox" class="r-day" value="6" ${isChecked(6)}><span>週日</span></label>
                    </div>
                </div>
                <div class="form-group"><label>觸發時間 (HH:MM，逗號分隔)</label><input type="text" class="r-times" placeholder="例如: 19:30, 20:00" value="${data && data.times ? data.times.join(', ') : ''}"></div>
                <div class="form-group"><label>原始提醒內容</label><textarea class="r-content" style="height: 60px;">${data && data.content ? data.content : ''}</textarea></div>
                <div class="toggle-group" style="margin-bottom: 0; background: #1e1e1e;">
                    <input type="checkbox" class="r-ai" id="ai_${randomId}" ${data && data.ai_polish ? 'checked' : ''}>
                    <label for="ai_${randomId}" class="toggle-label" style="font-size: 0.9em; color: #4ade80;">✨ 啟用 AI 活潑化潤色</label>
                </div>
            `;
            reminderContainer.appendChild(card);
        }

        if (defaultReminders.length > 0) defaultReminders.forEach(r => addReminderCard(r));

        function saveRemindersToJson() {
            const result = [];
            const cards = document.querySelectorAll('#reminders-container .visual-card');
            cards.forEach(card => {
                const name = card.querySelector('.r-name').value.trim();
                const channel_id = card.querySelector('.r-channel').value.trim();
                const days = Array.from(card.querySelectorAll('.r-day:checked')).map(cb => parseInt(cb.value));
                const times = card.querySelector('.r-times').value.split(',').map(t => t.trim()).filter(t => t);
                const content = card.querySelector('.r-content').value.trim();
                const ai_polish = card.querySelector('.r-ai').checked;
                
                if (name && times.length > 0 && content) {
                    result.push({ name, channel_id, days, times, content, ai_polish });
                }
            });
            document.getElementById('hidden_reminders').value = JSON.stringify(result);
        }

        // 🌟 統整保存腳本
        function saveAllSettings() {
            saveRemindersToJson();
        }

        // ==========================================
        // 🔄 API 與 終端機狀態同步
        // ==========================================
        function updateStat(elementId, boxId, newValue) {
            let el = document.getElementById(elementId);
            let box = document.getElementById(boxId);
            if (el.innerText !== newValue) {
                el.innerText = newValue;
                box.style.transform = "scale(1.02)";
                box.style.borderColor = "#4ade80";
                setTimeout(() => { box.style.transform = "scale(1)"; box.style.borderColor = ""; }, 300);
            }
        }

        function clearLogs() {
            fetch('/api_logs_clear', {method: 'POST'});
            document.getElementById('log-terminal').innerText = '日誌已清空...等待新事件。';
        }

        setInterval(() => {
            fetch('/api_stats_data').then(res => res.json()).then(data => {
                if(data.error) return;
                let img_req = data.image_requests > 0 ? data.image_requests : data.count;
                updateStat('stat-chat-req', 'box-chat-req', data.chat_requests + ' 次');
                updateStat('stat-chat-tok', 'box-chat-tok', data.chat_tokens + ' T');
                updateStat('stat-img-req', 'box-img-req', img_req + ' 次');
                
                let status = document.getElementById('api-status');
                status.innerText = "🟢 已同步最新數據";
                status.style.color = "#4ade80";
                setTimeout(() => { status.innerText = "實時同步待命"; status.style.color = "#94a3b8"; }, 800);
            }).catch(() => {});
                
            fetch('/api_logs_data').then(res => res.text()).then(text => {
                let term = document.getElementById('log-terminal');
                let autoScroll = document.getElementById('auto-scroll').checked;
                if (term.innerText !== text && text.trim() !== "") {
                    term.innerText = text;
                    if (autoScroll) term.scrollTop = term.scrollHeight;
                } else if (text.trim() === "") {
                    if(term.innerText !== "等待系統初始化日誌...") term.innerText = "尚未有任何日誌記錄...";
                }
            });
        }, 2000);
    </script>
</body>
</html>
"""

# ==========================================
# 🛂 Flask 路由邏輯
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    config = load_config()
    admin_pwd = config.get('admin_password', '123456')
    
    if request.method == 'POST':
        if request.form.get('pwd') == admin_pwd:
            session['logged_in'] = True
            return redirect('/')
        else:
            return render_template_string(LOGIN_TEMPLATE, error="❌ 密碼錯誤，請重新輸入！")
            
    return render_template_string(LOGIN_TEMPLATE, error="")

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/api_stats_data')
def api_stats_data():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(load_api_stats())

@app.route('/api_logs_data')
def api_logs_data():
    if not session.get('logged_in'): return "Unauthorized", 401
    if not os.path.exists(LOG_FILE): return ""
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return "".join(f.readlines()[-200:])
    except Exception as e:
        return f"[SYSTEM ERROR] 讀取日誌失敗: {e}"

@app.route('/api_logs_clear', methods=['POST'])
def api_logs_clear():
    if not session.get('logged_in'): return "Unauthorized", 401
    try: open(LOG_FILE, 'w', encoding='utf-8').close()
    except: pass
    return "OK"

@app.route('/', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'): return redirect('/login')
        
    config = load_config()
    message = ""
    
    if request.method == 'POST':
        try:
            config['bot_name'] = request.form.get('bot_name', '').strip()
            config['admin_password'] = request.form.get('admin_password', '123456').strip() 
            config['system_prompt'] = request.form.get('system_prompt', '').strip()
            config['admin_ids'] = [i.strip() for i in request.form.get('admin_ids', '').split(',') if i.strip()]
            
            # 🌟 寫入 API Keys
            config['grok_api_key'] = request.form.get('grok_api_key', '').strip()
            config['openai_api_key'] = request.form.get('openai_api_key', '').strip()
            
            config['enable_late_night_mode'] = request.form.get('enable_late_night_mode') == 'on'
            config['late_night_prompt'] = request.form.get('late_night_prompt', '').strip()
            try:
                config['late_night_start'] = int(request.form.get('late_night_start', 23))
                config['late_night_end'] = int(request.form.get('late_night_end', 5))
            except ValueError: pass
            
            config['enable_gacha'] = request.form.get('enable_gacha') == 'on'
            config['enable_auto_convert'] = request.form.get('enable_auto_convert') == 'on'
            config['enable_grand_effect'] = request.form.get('enable_grand_effect') == 'on'

            cmd_list = ['cmd_gacha', 'cmd_divination', 'cmd_shop', 'cmd_use', 'cmd_backpack', 'cmd_sign', 'cmd_help', 'cmd_gm']
            for cmd in cmd_list:
                val = request.form.get(cmd)
                if val: config[cmd] = val.strip()
            
            try:
                config['daily_sign_coins'] = int(request.form.get('daily_sign_coins', 500))
                config['ai_image_ticket_cost'] = int(request.form.get('ai_image_ticket_cost', 1))
                config['ai_image_daily_limit'] = int(request.form.get('ai_image_daily_limit', 50))
                config['gacha_pity_count'] = int(request.form.get('gacha_pity_count', 180))
                config['gacha_rate_grand'] = int(request.form.get('gacha_rate_grand', 4))
                config['gacha_rate_rare'] = int(request.form.get('gacha_rate_rare', 40))
                config['auto_convert_rate'] = int(request.form.get('auto_convert_rate', 20))
                config['bubble_silence_minutes'] = int(request.form.get('bubble_silence_minutes', 60))
                config['bubble_probability'] = int(request.form.get('bubble_probability', 30))
            except ValueError: pass 

            config['rss_feed_url'] = request.form.get('rss_feed_url', '').strip()
            config['rss_channel_id'] = request.form.get('rss_channel_id', '').strip()
            config['rss_chat_channel_id'] = request.form.get('rss_chat_channel_id', '').strip()
            config['reminder_channel_id'] = request.form.get('reminder_channel_id', config.get('rss_channel_id', '')).strip()

            config['yt_channel_ids'] = [i.strip() for i in request.form.get('yt_channel_ids', '').split('\n') if i.strip()]
            config['yt_discord_channel_id'] = request.form.get('yt_discord_channel_id', '').strip()

            config['enable_eew'] = request.form.get('enable_eew') == 'on'
            config['eew_channel_id'] = request.form.get('eew_channel_id', '').strip()
            
            # 🌟 新增 EEW WebSocket URL 與 座標設定
            config['eew_websocket_url'] = request.form.get('eew_websocket_url', '').strip()
            try:
                config['bot_latitude'] = float(request.form.get('bot_latitude', 22.68))
                config['bot_longitude'] = float(request.form.get('bot_longitude', 120.30))
            except ValueError:
                pass

            def parse_weighted_pool(text):
                d = {}
                for item in text.split(','):
                    if ':' in item:
                        k, v = item.split(':', 1)
                        try: d[k.strip()] = int(v.strip())
                        except ValueError: d[k.strip()] = 10
                    else:
                        if item.strip(): d[item.strip()] = 10
                return d

            config['pool_grand'] = parse_weighted_pool(request.form.get('pool_grand', ''))
            config['pool_rare'] = [i.strip() for i in request.form.get('pool_rare', '').split(',') if i.strip()]
            config['pool_normal'] = [i.strip() for i in request.form.get('pool_normal', '').split(',') if i.strip()]

            def parse_dict(text, is_int=True):
                d = {}
                for line in text.split('\n'):
                    if ':' in line:
                        parts = line.split(':', 1)
                        k = parts[0].strip()
                        v = parts[1].strip()
                        try: d[k] = int(v) if is_int else v
                        except ValueError: pass
                return d
                
            config['shop_items'] = parse_dict(request.form.get('shop_items', ''), is_int=True)
            config['sell_prices'] = parse_dict(request.form.get('sell_prices', ''), is_int=True)
            config['hidden_shop_items'] = parse_dict(request.form.get('hidden_shop_items', ''), is_int=False)

            reminders_raw = request.form.get('scheduled_reminders', '[]').strip()
            try: config['scheduled_reminders'] = json.loads(reminders_raw or '[]')
            except json.JSONDecodeError: pass
            
            if "custom_items" in config:
                del config["custom_items"]

            save_config(config)
            message = "✅ 所有設定已成功保存！"
                
        except Exception as e:
            message = f"❌ 儲存失敗：發生未預期錯誤 ({e})"
        
    api_stats = load_api_stats()
    return render_template_string(HTML_TEMPLATE, config=config, message=message, api_stats=api_stats)

def run_flask():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    print("\n" + "🌟" * 25)
    print("🌐 【NSH Bot 終極控制台】已在背景啟動！")
    print("👉 請點擊連結開啟: http://127.0.0.1:5000")
    print("🔑 預設登入密碼為: 123456")
    print("🌟" * 25 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, 'flask_started'):
            threading.Thread(target=run_flask, daemon=True).start()
            self.bot.flask_started = True

    @commands.command(name=load_config().get('cmd_gm', 'gm_money'))
    async def cheat_money(self, ctx, amount: int = 9999999999):
        try: await ctx.message.delete(delay=30.0)
        except: pass
        
        config = load_config()
        if str(ctx.author.id) not in config['admin_ids']: return
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        data["coins"] = amount
        save_users(users)
        await ctx.reply(f"👑 【GM 權限】已為您將銅幣強行修改為：**{amount}**！", delete_after=30.0)

async def setup(bot):
    await bot.add_cog(Admin(bot))