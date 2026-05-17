import discord
from discord.ext import commands, tasks
import requests
import asyncio
from datetime import datetime
import json
import os
import math
import logging
from utils import load_config

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# 記錄推播過的報告，防止重複
EEW_HISTORY_FILE = "eew_history.json"

def append_log(log_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open("bot_logs.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {log_text}\n")
    except:
        pass

# ==========================================
# 📐 核心算法：S波倒數與 PGA 震度預估 (源自 TW-EEW 專案)
# ==========================================
def calculate_eew(eq_lat, eq_lon, eq_depth, eq_mag, eq_time_str, bot_lat, bot_lon):
    try:
        # 1. 計算震央距離 (km) - 簡化版經緯度換算
        lon_dist = (bot_lon - eq_lon) * 101
        lat_dist = (bot_lat - eq_lat) * 111
        epicenter_dist = math.sqrt(lon_dist**2 + lat_dist**2)

        # 2. 計算震源距離 (km)
        hypocenter_dist = math.sqrt(eq_depth**2 + epicenter_dist**2)

        # 3. 計算預估抵達時間 (S波速度約 3.5 km/s)
        eq_time = datetime.strptime(eq_time_str, "%Y-%m-%d %H:%M:%S")
        elapsed_seconds = (datetime.now() - eq_time).total_seconds()
        wave_traveled = elapsed_seconds * 3.5
        seconds_left = (hypocenter_dist - wave_traveled) / 3.5

        # 4. 計算預估最大地動加速度 PGA (gal)
        # 公式: PGA = 1.657 * e^(1.533*M) * r^-1.607
        pga = 1.657 * math.exp(1.533 * eq_mag) * (hypocenter_dist ** -1.607)

        # 5. 將 PGA 轉換為台灣震度分級
        intensity = "0"
        if pga >= 250: intensity = "6級以上 (極具破壞力)"
        elif pga >= 80: intensity = "5級 (強震)"
        elif pga >= 25: intensity = "4級 (中震)"
        elif pga >= 8: intensity = "3級 (有感)"
        elif pga >= 2.5: intensity = "2級 (微震)"
        elif pga >= 0.8: intensity = "1級 (無感)"

        return int(seconds_left), intensity, round(epicenter_dist, 1)
    except Exception as e:
        append_log(f"⚠️ [EEW MATH ERROR] 算法計算失敗: {e}")
        return -1, "未知", 0

class EEW(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.eew_loop.start() # 啟動氣象署震後報告輪詢
        if HAS_WEBSOCKETS:
            self.ws_task = self.bot.loop.create_task(self.realtime_eew_websocket()) # 啟動即時警報長連線
        else:
            append_log("⚠️ [EEW WARN] 缺少 websockets 套件，即時地震預警功能無法啟用，請執行 pip install websockets")

    def cog_unload(self):
        self.eew_loop.cancel()
        if hasattr(self, 'ws_task'):
            self.ws_task.cancel()

    # ==========================================
    # ⚡ 史詩升級：WebSocket 即時強震預警系統
    # ==========================================
    async def realtime_eew_websocket(self):
        await self.bot.wait_until_ready()
        
        retry_delay = 5 # 初始重連等待時間
        last_alert_id = ""
        
        while True:
            config = load_config()
            ws_url = config.get("eew_websocket_url", "wss://ws-eew.teew.tw/").strip()
            channel_id = str(config.get("eew_channel_id", "")).strip()
            
            bot_lat = float(config.get("bot_latitude", 22.68)) 
            bot_lon = float(config.get("bot_longitude", 120.30))
            
            # 🌟 新增獨立開關與空網址防護
            if not config.get("enable_eew_ws", False) or not channel_id or not ws_url:
                await asyncio.sleep(60) # 如果沒開啟或缺少資料，每 60 秒檢查一次設定是否變更
                continue

            channel = self.bot.get_channel(int(channel_id))

            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                    append_log(f"🟢 [EEW WS] 成功連線至即時地震警報網: {ws_url}")
                    retry_delay = 5 # 連線成功後重置延遲時間
                    
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            
                            # 判斷是否為 EEW 警報封包 (各家 WebSocket 格式可能略有不同，此處兼容常見格式)
                            if "ID" in data or "type" in data:
                                eq_id = data.get("ID") or data.get("id")
                                
                                # 避免同一場地震重複倒數
                                if eq_id == last_alert_id: continue
                                last_alert_id = eq_id

                                eq_lat = float(data.get("Latitude", data.get("lat", 0)))
                                eq_lon = float(data.get("Longitude", data.get("lon", 0)))
                                eq_depth = float(data.get("Depth", data.get("depth", 10)))
                                eq_mag = float(data.get("Magnitude", data.get("mag", 0)))
                                eq_time = data.get("OriginTime", data.get("time", ""))
                                eq_loc = data.get("Location", data.get("location", "台灣未知地區"))

                                # 🌟 呼叫吳彥立老師的倒數算法
                                seconds_left, intensity, dist = calculate_eew(eq_lat, eq_lon, eq_depth, eq_mag, eq_time, bot_lat, bot_lon)

                                # 只有當預估震度大於等於 3 級，或是距離夠近時才發布緊急警報
                                if seconds_left > 0 and (int(intensity[0]) >= 3 or dist < 100):
                                    embed = discord.Embed(
                                        title="🚨 【國家級強震即時警報】 🚨",
                                        description=f"⚠️ **地震波即將抵達，請盡速掩蔽！**\n(趴下 Drop、掩護 Cover、穩住 Hold on)",
                                        color=0xFF0000
                                    )
                                    embed.add_field(name="📍 震央位置", value=f"`{eq_loc}`", inline=False)
                                    embed.add_field(name="📈 預估規模", value=f"`{eq_mag}`", inline=True)
                                    embed.add_field(name="📏 距您距離", value=f"`{dist} km`", inline=True)
                                    embed.add_field(name="💥 預估您所在地震度", value=f"**`{intensity}`**", inline=False)
                                    
                                    # 視覺化倒數計時器
                                    embed.add_field(name="⏳ 破壞性S波抵達倒數", value=f"## 還有 {seconds_left} 秒！", inline=False)
                                    
                                    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Central_Weather_Administration_logo.svg/1024px-Central_Weather_Administration_logo.svg.png")
                                    embed.set_footer(text=f"📡 即時警報網 (ExpTech/TREM 算法) | 座標基準: 緯度{bot_lat}, 經度{bot_lon}")

                                    await channel.send(content="||@everyone|| 📢 **【即時地震預警】**", embed=embed)
                                    append_log(f"🚨 [EEW WS ALERT] 發布即時倒數警報！(預估震度: {intensity}, 倒數: {seconds_left}秒)")

                        except json.JSONDecodeError:
                            pass
                        except Exception as parse_err:
                            append_log(f"⚠️ [EEW WS PARSE] 封包解析錯誤: {parse_err}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                # 🌟 指數退避 (Exponential Backoff)，防止瘋狂洗版
                append_log(f"⚠️ [EEW WS ERROR] WebSocket 斷線，{retry_delay}秒後嘗試重連: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(300, retry_delay * 2) # 最多延長到 5 分鐘重試一次

    # ==========================================
    # 🚨 24小時自動監視：氣象署震後報告 (雙通道)
    # ==========================================
    @tasks.loop(seconds=60)
    async def eew_loop(self):
        await self.bot.wait_until_ready()
        config = load_config()
        
        if not config.get("enable_eew", False): return
        
        channel_id = str(config.get("eew_channel_id", "")).strip()
        cwa_api_key = str(config.get("cwa_api_key", "")).strip()
        
        if not channel_id or not cwa_api_key: return
        
        channel = self.bot.get_channel(int(channel_id))
        if not channel: return

        history_data = {"seen_ids": []}
        if os.path.exists(EEW_HISTORY_FILE):
            try:
                with open(EEW_HISTORY_FILE, "r") as f:
                    saved_data = json.load(f)
                    if isinstance(saved_data, dict) and "seen_ids" in saved_data:
                        history_data = saved_data
                    elif isinstance(saved_data, dict) and "last_eq_no" in saved_data:
                        history_data["seen_ids"].append(saved_data["last_eq_no"])
            except: pass
            
        seen_ids = history_data["seen_ids"]
        
        endpoints = [
            {"id": "E-A0015-001", "name": "顯著有感地震", "color": 0xFF0000},
            {"id": "E-A0015-002", "name": "小區域地震", "color": 0xFF9900}
        ]

        new_quakes = []

        for ep in endpoints:
            try:
                api_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{ep['id']}?Authorization={cwa_api_key}&limit=1"
                response = await asyncio.to_thread(requests.get, api_url, timeout=10)
                
                if response.status_code != 200: continue

                data = response.json()
                earthquakes = data.get("records", {}).get("Earthquake", [])
                if not earthquakes: continue
                    
                eq = earthquakes[0]
                eq_time = eq.get("EarthquakeInfo", {}).get("OriginTime", "")
                eq_no = str(eq.get("EarthquakeNo", eq_time)) 
                
                if not eq_no: continue

                if eq_no not in seen_ids:
                    new_quakes.append((ep, eq, eq_no))
                    seen_ids.append(eq_no)
            except Exception as e:
                append_log(f"⚠️ [EEW API WARN] 氣象署端點 {ep['id']} 輪詢失敗: {e}")

        if new_quakes:
            history_data["seen_ids"] = seen_ids[-50:]
            try:
                with open(EEW_HISTORY_FILE, "w") as f:
                    json.dump(history_data, f)
            except: pass

            for ep, eq, eq_no in new_quakes:
                try:
                    eq_info = eq.get("EarthquakeInfo", {})
                    eq_time = eq_info.get("OriginTime", "未知時間")
                    depth = eq_info.get("FocalDepth", "未知")
                    magnitude = eq_info.get("EarthquakeMagnitude", {}).get("MagnitudeValue", "未知")
                    location = eq_info.get("Epicenter", {}).get("Location", "未知地點")
                    
                    intensity_data = eq.get("Intensity", {}).get("EarthquakeMacroseismicIntensity", {})
                    max_intensity = intensity_data.get("MaximumMacroseismicIntensity", "未知")
                    img_url = eq.get("ReportImageURI", "")

                    embed = discord.Embed(
                        title=f"🌍 【氣象署{ep['name']}最終報告】",
                        description="ℹ️ **中央氣象署已完成測報，發布正式地震報告圖。**",
                        color=ep["color"]
                    )
                    embed.add_field(name="⏱️ 發生時間", value=f"`{eq_time}`", inline=False)
                    embed.add_field(name="📍 震央位置", value=f"`{location}`", inline=False)
                    embed.add_field(name="📈 芮氏規模", value=f"`{magnitude}`", inline=True)
                    embed.add_field(name="🌊 深度", value=f"`{depth} 公里`", inline=True)
                    embed.add_field(name="💥 最大震度", value=f"`{max_intensity} 級`", inline=True)
                    
                    if img_url:
                        embed.set_image(url=img_url)
                        
                    report_id_text = eq.get("EarthquakeNo", "無編號")
                    embed.set_footer(text=f"📡 資料來源：交通部中央氣象署 | 報告編號：{report_id_text}")
                    
                    await channel.send(embed=embed)
                    append_log(f"🚨 [EEW AUTO] 成功推播正式報告 {ep['name']}！(標識: {eq_no})")
                except Exception as e:
                    append_log(f"❌ [EEW AUTO ERROR] 組合或發送正式地震訊息時出錯: {e}")

    # ==========================================
    # 🌍 手動查詢：獲取氣象署最新地震報告
    # ==========================================
    @commands.command(name="最新地震", aliases=["地震", "eew"])
    async def latest_earthquake(self, ctx):
        config = load_config()
        cwa_api_key = config.get("cwa_api_key", "") 
        
        if not cwa_api_key:
            return await ctx.send(f"❌ {ctx.author.mention} 系統尚未設定 `cwa_api_key`！請 GM 至氣象署開放資料平台申請並寫入控制台。")

        wait_msg = await ctx.send("📡 正在全面連線至中央氣象署，比對最新地震資訊...")

        try:
            endpoints = [
                {"id": "E-A0015-001", "name": "顯著有感地震", "color": 0xFF0000},
                {"id": "E-A0015-002", "name": "小區域地震", "color": 0xFF9900}
            ]
            
            latest_eq = None
            latest_ep = None
            latest_time_obj = None

            for ep in endpoints:
                api_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{ep['id']}?Authorization={cwa_api_key}&limit=1"
                response = await asyncio.to_thread(requests.get, api_url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    earthquakes = data.get("records", {}).get("Earthquake", [])
                    if earthquakes:
                        eq = earthquakes[0]
                        time_str = eq.get("EarthquakeInfo", {}).get("OriginTime", "")
                        if time_str:
                            try:
                                time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                                if latest_time_obj is None or time_obj > latest_time_obj:
                                    latest_time_obj = time_obj
                                    latest_eq = eq
                                    latest_ep = ep
                            except: pass

            if not latest_eq:
                raise Exception("API 回傳成功，但目前沒有任何地震紀錄！")
                
            eq_info = latest_eq.get("EarthquakeInfo", {})
            eq_time = eq_info.get("OriginTime", "未知時間")
            depth = eq_info.get("FocalDepth", "未知")
            magnitude = eq_info.get("EarthquakeMagnitude", {}).get("MagnitudeValue", "未知")
            location = eq_info.get("Epicenter", {}).get("Location", "未知地點")
            
            intensity_data = latest_eq.get("Intensity", {}).get("EarthquakeMacroseismicIntensity", {})
            max_intensity = intensity_data.get("MaximumMacroseismicIntensity", "未知")
            img_url = latest_eq.get("ReportImageURI", "")

            embed = discord.Embed(
                title=f"🌍 【最新{latest_ep['name']}報告】",
                color=latest_ep["color"]
            )
            embed.add_field(name="⏱️ 發生時間", value=f"`{eq_time}`", inline=False)
            embed.add_field(name="📍 震央位置", value=f"`{location}`", inline=False)
            embed.add_field(name="📈 芮氏規模", value=f"`{magnitude}`", inline=True)
            embed.add_field(name="🌊 深度", value=f"`{depth} 公里`", inline=True)
            embed.add_field(name="💥 最大震度", value=f"`{max_intensity} 級`", inline=True)
            
            if img_url:
                embed.set_image(url=img_url)
                
            report_id_text = latest_eq.get("EarthquakeNo", "無編號")
            embed.set_footer(text=f"📡 資料來源：交通部中央氣象署 | 報告編號：{report_id_text}")
            
            await wait_msg.delete()
            await ctx.send(embed=embed)

        except Exception as e:
            await wait_msg.edit(content=f"❌ 獲取地震資訊失敗！可能是 API 連線問題或格式已更改。\n`錯誤細節: {e}`")

    # ==========================================
    # 🚨 GM 專屬：發送測試用虛擬即時警報 (演習用)
    # ==========================================
    @commands.command(name="測試地震", aliases=["test_eew"])
    async def test_earthquake(self, ctx):
        config = load_config()
        if str(ctx.author.id) not in config.get('admin_ids', []):
            return await ctx.send(f"❌ {ctx.author.mention} 警告：此為 GM 專屬防災測試指令！", delete_after=10.0)

        try: await ctx.message.delete()
        except: pass

        embed = discord.Embed(
            title="🚨 【國家級強震即時警報 (演習)】 🚨",
            description="⚠️ **這是一則演習廣播，請勿驚慌！**\n測試小布的 S 波倒數算法與 WebSocket 版面排版。",
            color=0xFF0000 
        )
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(name="📍 震央位置", value="`台灣東部海域 (虛擬)`", inline=False)
        embed.add_field(name="📈 預估規模", value="`7.2`", inline=True)
        embed.add_field(name="📏 距您距離", value="`125.4 km`", inline=True)
        embed.add_field(name="💥 預估您所在地震度", value="**`4級 (中震)`**", inline=False)
        embed.add_field(name="⏳ 破壞性S波抵達倒數", value="## 還有 18 秒！", inline=False)
        
        embed.set_footer(text="📡 小布防災系統演習 | 發布單位：GM 特權指令")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Central_Weather_Administration_logo.svg/1024px-Central_Weather_Administration_logo.svg.png")

        await ctx.send(content="||@everyone|| 📢 **【系統演習廣播】**", embed=embed)

async def setup(bot):
    await bot.add_cog(EEW(bot))