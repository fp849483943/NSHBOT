import discord
from discord.ext import commands, tasks
import requests
import asyncio
import os
import json
from datetime import datetime, timedelta
import re
from utils import load_config, load_users, save_users, get_user_data

# ==========================================
# 📊 寫入 API 統計與日誌的輔助函式
# ==========================================
def update_api_stats(tokens=0, is_image=False):
    today = str(datetime.now().date())
    usage_file = "api_usage.json"
    stats = {"date": today, "count": 0, "image_requests": 0, "chat_requests": 0, "chat_tokens": 0}
    
    if os.path.exists(usage_file):
        try:
            with open(usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today:
                    stats.update(data)
        except:
            pass
            
    stats["count"] = stats.get("count", 0) + 1
    
    if is_image:
        stats["image_requests"] = stats.get("image_requests", 0) + 1
    else:
        stats["chat_requests"] = stats.get("chat_requests", 0) + 1
        stats["chat_tokens"] = stats.get("chat_tokens", 0) + tokens
    
    try:
        with open(usage_file, "w", encoding="utf-8") as f:
            json.dump(stats, f)
    except:
        pass

def append_log(log_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open("bot_logs.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {log_text}\n")
    except:
        pass

def get_emoji_file(emoji_name):
    for ext in ['.gif', '.png', '.jpg']:
        path = os.path.join("assets", "emojis", f"{emoji_name}{ext}")
        if os.path.exists(path):
            return discord.File(path, filename=f"emoji_{emoji_name}{ext}")
    return None

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.grok_model_name = "grok-4.20-reasoning"
        self.grok_api_url_text = "https://api.x.ai/v1/responses"
        # 🌟 將記憶庫改為以 channel_id 為主鍵，實現頻道共通記憶
        self.chat_memory = {}
        # 🌟 記錄當前頭像狀態
        self.current_profile_state = None 
        # 🌟 記錄 GM 大腦偏好設定 (手動切換用)
        self.gm_engine = {}
        self.profile_loop.start()

    def cog_unload(self):
        self.profile_loop.cancel()

    def has_adult_access(self, user_data):
        config = load_config()
        if not config.get('enable_late_night_mode', True): return False
        has_black_card = user_data["inventory"].get("大人的證明", 0) > 0
        if not has_black_card: return False

        start_h = int(config.get('late_night_start', 23))
        end_h = int(config.get('late_night_end', 5))
        current_h = datetime.now().hour
        if start_h > end_h: return current_h >= start_h or current_h < end_h
        else: return start_h <= current_h < end_h

    def check_adult_mode(self, user_data, channel):
        is_nsfw = False
        if isinstance(channel, discord.DMChannel): is_nsfw = True
        elif getattr(channel, 'nsfw', False): is_nsfw = True
        elif hasattr(channel, 'parent') and getattr(channel.parent, 'nsfw', False): is_nsfw = True
        return self.has_adult_access(user_data) and is_nsfw

    # ==========================================
    # 🌙 智能精準生理時鐘：自動切換大頭貼與暱稱
    # ==========================================
    @tasks.loop()
    async def profile_loop(self):
        try:
            await self.bot.wait_until_ready()
            config = load_config()
            
            start_h = int(config.get('late_night_start', 23))
            end_h = int(config.get('late_night_end', 5))
            now = datetime.now()
            current_h = now.hour
            
            if start_h > end_h:
                is_late_night = current_h >= start_h or current_h < end_h
            else:
                is_late_night = start_h <= current_h < end_h
                
            target_state = "night" if is_late_night else "day"
            
            # 執行變身
            if self.current_profile_state != target_state:
                self.current_profile_state = target_state
                
                avatar_filename = "avatar_night.png" if target_state == "night" else "avatar_day.png"
                avatar_path = os.path.join("assets", "system", avatar_filename)
                
                if os.path.exists(avatar_path):
                    try:
                        with open(avatar_path, "rb") as f:
                            avatar_bytes = f.read()
                            await self.bot.user.edit(avatar=avatar_bytes)
                        append_log(f"🔄 [PROFILE] 晨昏交替！已精準切換為 {target_state} 模式。")
                    except Exception as e:
                        append_log(f"⚠️ [PROFILE WARN] 切換頭像失敗 (可能是剛開機或觸發 Discord 頻率限制): {e}")
                
                base_bot_name = config.get('bot_name', '小布')
                target_name = f"{base_bot_name}的媽媽" if target_state == "night" else base_bot_name
                
                for guild in self.bot.guilds:
                    try:
                        if guild.me.nick != target_name:
                            await guild.me.edit(nick=target_name)
                    except Exception as e:
                        # 攔截所有改名錯誤 (防 Discord Rate Limit)，避免迴圈崩潰
                        pass

            # 🌟 核心：智能計算距離下一個「整點變身」還有幾秒
            target_hour = end_h if is_late_night else start_h
            
            next_target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            # 如果計算出的目標時間已經過了，代表是明天的這個時間
            if next_target <= now:
                next_target += timedelta(days=1)
                
            sleep_seconds = (next_target - now).total_seconds()
            
            # 黑科技防呆：單次最高只睡 10 分鐘
            wait_time = min(sleep_seconds, 600)
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            append_log(f"⚠️ [PROFILE LOOP WARN] 監視器發生異常: {e}")
            await asyncio.sleep(60) # 發生異常時休息 60 秒，避免崩潰重啟迴圈

    # ==========================================
    # 👑 GM 專屬：切換大腦引擎 (LM Studio <-> Grok)
    # ==========================================
    @commands.command(name="切換大腦", aliases=["switch_engine", "大腦切換", "切換模型", "引擎切換"])
    async def switch_engine(self, ctx):
        try: await ctx.message.delete(delay=30.0)
        except: pass
        
        config = load_config()
        is_admin = str(ctx.author.id) in config.get('admin_ids', [])
        
        if not is_admin:
            return await ctx.reply("❌ 警告：您不是 GM，無法切換大腦！", delete_after=15.0, mention_author=False)

        current = self.gm_engine.get(ctx.author.id, "LM Studio")
        new_engine = "Grok" if current == "LM Studio" else "LM Studio"
        self.gm_engine[ctx.author.id] = new_engine
        
        file = get_emoji_file("wink")
        msg = f"🔄 **大腦切換成功！**\n{ctx.author.mention} 您現在的專屬對話引擎已手動切換為：**{new_engine}**"
        if new_engine == "LM Studio":
            msg += "\n*(💡 提示：若 LM Studio 斷線或逾時，系統會自動為您降級回 Grok！)*"
        
        if file:
            await ctx.reply(msg, file=file, delete_after=30.0, mention_author=False)
        else:
            await ctx.reply(msg, delete_after=30.0, mention_author=False)

    # ==========================================
    # 👑 GM 專屬：本地 LM Studio 大腦連線測試
    # ==========================================
    @commands.command(name="大腦測試", aliases=["lm_test", "測試模型"])
    async def lm_studio_test(self, ctx):
        config = load_config()
        is_admin = str(ctx.author.id) in config.get('admin_ids', [])
        
        if not is_admin:
            return await ctx.reply("❌ 警告：您不是 GM，無權測試本地大腦！(若您是GM，請確認控制台有填妥您的 Discord ID)", mention_author=False)

        wait_msg = await ctx.reply("🔍 **【LM Studio 連線測試】**\n正在嘗試與本機 `http://127.0.0.1:1234` 建立連線...", mention_author=False)
        try:
            api_url = "http://127.0.0.1:1234/v1/models"
            resp = await asyncio.to_thread(requests.get, api_url, timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                model_names = [m.get("id") for m in models]
                if not model_names:
                    await wait_msg.edit(content="⚠️ **連線成功，但未載入模型！**\n請在 LM Studio 中手動載入一個模型！")
                else:
                    await wait_msg.edit(content=f"✅ **LM Studio 連線成功！**\n目前正在運行的模型為：`{', '.join(model_names)}`\n現在您可以直接 `@小布` 跟我說話了！")
            else:
                await wait_msg.edit(content=f"⚠️ **連線異常**：伺服器回傳 HTTP {resp.status_code}")
        except Exception as e:
            await wait_msg.edit(content=f"❌ **連線失敗**：無法連線到 LM Studio。\n👉 請確認 LM Studio 左側 `<->` 的 Server 已經按下 `Start Server`！\n錯誤細節：`{e}`")

    # ==========================================
    # 🎁 新手福利：領取繪圖券指令
    # ==========================================
    @commands.command(name="領取繪圖券", aliases=["領畫布", "領取畫筆", "我要畫畫", "新手福利", "領繪圖券"])
    async def claim_draw_tickets(self, ctx):
        try: await ctx.message.delete(delay=30.0)
        except: pass
        
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        
        if data.get("claimed_free_draw_tickets", False):
            file = get_emoji_file("sad")
            kwargs = {"content": f"❌ {ctx.author.mention} 大俠，您之前已經領取過新手繪圖福利囉！如果需要更多，可以到 `!商店` 購買喔！", "delete_after": 15.0, "mention_author": False}
            if file: kwargs["file"] = file
            return await ctx.reply(**kwargs)
            
        data["claimed_free_draw_tickets"] = True
        data["inventory"]["繪圖券"] = data["inventory"].get("繪圖券", 0) + 10
        save_users(users)
        
        config = load_config()
        bot_name = config.get("bot_name", "小布")
        
        file = get_emoji_file("happy")
        msg = f"🎉 **【推廣福利發放】**\n{ctx.author.mention} 成功向 {bot_name} 領取了 **10 張繪圖券**！\n👉 快去大廳或私密包廂使用 `!畫 <提示詞>` 體驗強大的 AI 繪圖吧！🎨"
        
        kwargs = {"content": msg, "delete_after": 60.0, "mention_author": False}
        if file: kwargs["file"] = file
        await ctx.reply(**kwargs)

    # ==========================================
    # 🧠 清空記憶指令 (針對當前頻道)
    # ==========================================
    @commands.command(name="忘記", aliases=["清空記憶", "重置", "洗腦"])
    async def clear_memory(self, ctx):
        try: await ctx.message.delete(delay=30.0)
        except: pass
        
        channel_id = ctx.channel.id
        if channel_id in self.chat_memory:
            del self.chat_memory[channel_id]
            file = get_emoji_file("wink")
            kwargs = {"content": "✨ 呼～小布揉了揉腦袋，已經把這個頻道的聊天內容與設定都忘光光囉！我們重新開始吧！", "delete_after": 30.0, "mention_author": False}
            if file: kwargs["file"] = file
            await ctx.reply(**kwargs)
        else:
            file = get_emoji_file("shy")
            kwargs = {"content": "❓ 咦？這個頻道裡小布本來就什麼都不記得了呀...", "delete_after": 15.0, "mention_author": False}
            if file: kwargs["file"] = file
            await ctx.reply(**kwargs)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return 
        if message.content.startswith('!'): return
        if message.content.startswith('！'): return

        # ==========================================
        # 🛡️ 全域絕對防護罩：攔截所有不可預期的崩潰
        # ==========================================
        try:
            config = load_config()
            is_admin = str(message.author.id) in config.get('admin_ids', [])
            base_bot_name = config.get('bot_name', '小布')

            # 時間與身分判定
            current_h = datetime.now().hour
            start_h = int(config.get('late_night_start', 23))
            end_h = int(config.get('late_night_end', 5))
            
            if start_h > end_h:
                is_late_night = current_h >= start_h or current_h < end_h
            else:
                is_late_night = start_h <= current_h < end_h

            target_name = f"{base_bot_name}的媽媽" if is_late_night else base_bot_name

            # ==========================================
            # 🌟 解決幽靈回覆 Bug：預先深度抓取引用訊息
            # ==========================================
            reference_text = ""
            ref_author_id = 0
            if message.reference and message.reference.message_id:
                try:
                    ref_msg = message.reference.resolved
                    # 若在快取中找不到，主動去向 Discord 伺服器要資料
                    if ref_msg is None or isinstance(ref_msg, discord.DeletedReferencedMessage):
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    
                    if isinstance(ref_msg, discord.Message):
                        ref_author_id = ref_msg.author.id
                        ref_author = ref_msg.author.display_name
                        ref_content = f"【發言者/來源: {ref_author}】\n" + (ref_msg.content or "")
                        
                        # 處理轉發 (Snapshots) 與 Embeds
                        try:
                            raw_msg = await self.bot.http.get_message(ref_msg.channel.id, ref_msg.id)
                            if 'message_snapshots' in raw_msg:
                                for snapshot in raw_msg['message_snapshots']:
                                    snap_msg = snapshot.get('message', {})
                                    snap_content = snap_msg.get('content', '')
                                    if snap_content:
                                        ref_content += f"\n[轉發內容]: {snap_content}"
                                    for embed in snap_msg.get('embeds', []):
                                        if 'title' in embed: ref_content += f"\n[轉發標題]: {embed['title']}"
                                        if 'description' in embed: ref_content += f"\n[轉發敘述]: {embed['description']}"
                                        for field in embed.get('fields', []):
                                            ref_content += f"\n[{field.get('name', '')}]: {field.get('value', '')}"
                        except Exception as e:
                            append_log(f"⚠️ [WARN] 讀取轉發底層資料失敗: {e}")

                        if ref_msg.embeds:
                            for embed in ref_msg.embeds:
                                if embed.title: ref_content += f"\n[公告標題]: {embed.title}"
                                if embed.description: ref_content += f"\n[內容]: {embed.description}"
                                for field in embed.fields:
                                    if field.name and field.value:
                                        ref_content += f"\n[{field.name}]: {field.value}"
                        
                        reference_text = ref_content.strip()
                except Exception as e:
                    append_log(f"⚠️ [WARN] 無法讀取引用訊息: {e}")

            # ==========================================
            # 🌟 解決 Discord 標記陷阱：精準判定是否呼叫小布
            # ==========================================
            is_mentioned = False
            is_in_private_room = hasattr(self.bot, 'active_rooms') and message.channel.id in self.bot.active_rooms.values()
            
            # 1. 偵測直接標記使用者
            if self.bot.user in message.mentions:
                is_mentioned = True
            # 2. 偵測回覆小布的訊息 (使用剛剛抓取到的 ref_author_id，無懼快取遺失)
            elif ref_author_id == self.bot.user.id:
                is_mentioned = True
            # 3. 偵測標記了包含小布的身分組
            elif message.guild and message.role_mentions:
                for role in message.role_mentions:
                    if role in message.guild.me.roles:
                        is_mentioned = True
                        break
            # 4. 偵測純文字手打 (自動轉換 Discord 的 <@&ID> 為文字來比對)
            elif f"@{base_bot_name}" in message.clean_content or f"@{target_name}" in message.clean_content or "@小布" in message.clean_content:
                is_mentioned = True
            # 5. 🌟 終極特權：如果是在「私密包廂」內，免標記自動回應所有訊息！
            elif is_in_private_room:
                is_mentioned = True
                        
            if not is_mentioned: 
                return 

            # 安全移除所有標記文字 (包含使用者與身分組，確保乾淨的 user_text)
            user_text = re.sub(r'<@!?&?\d+>', '', message.content).strip()
            user_text = user_text.replace(f"@{target_name}", "").replace(f"@{base_bot_name}", "").replace("@小布", "").strip()

            # ==========================================
            # 🎁 攔截：防呆回覆與自然語言領取福利
            # ==========================================
            # 在包廂內如果不小心只傳了空白或圖片，避免觸發防呆回應
            if not user_text and not reference_text: 
                if is_in_private_room:
                    return # 包廂內純傳圖或空文字直接忽略即可
                file = get_emoji_file("wink")
                kwargs = {"content": f"找{base_bot_name}有什麼事嗎？"}
                if file: kwargs["file"] = file
                kwargs["mention_author"] = False
                return await message.reply(**kwargs)
                
            # 領取福利攔截
            if any(kw in user_text for kw in ["領取繪圖券", "新手福利", "領畫畫券", "領繪圖券", "給我繪圖券", "給我畫布"]):
                users = load_users()
                data = get_user_data(message.author.id, users)
                if not data.get("claimed_free_draw_tickets", False):
                    data["claimed_free_draw_tickets"] = True
                    data["inventory"]["繪圖券"] = data["inventory"].get("繪圖券", 0) + 10
                    save_users(users)
                    file = get_emoji_file("happy")
                    reply_msg = f"🎉 **【推廣福利發放】**\n{message.author.mention} 成功領取了 **10 張繪圖券**！\n👉 快使用 `!畫 <提示詞>` 讓{base_bot_name}為您作畫吧！🎨"
                else:
                    file = get_emoji_file("sad")
                    reply_msg = f"❌ {message.author.mention} 大俠，您已經領取過繪圖福利囉！如果需要更多，可以去 `!商店` 購買喔！"
                
                # 安全封裝發送機制，防止 file 為 None 導致崩潰
                kwargs = {"content": reply_msg}
                if file: kwargs["file"] = file
                if is_in_private_room:
                    return await message.channel.send(**kwargs)
                else:
                    kwargs["mention_author"] = False
                    return await message.reply(**kwargs)

            # ==========================================
            # 🌟 核心：頻道記憶與大腦設定
            # ==========================================
            now = datetime.now()
            channel_id = message.channel.id
            current_speaker = message.author.display_name

            if channel_id not in self.chat_memory or (now - self.chat_memory[channel_id]["last_time"]).total_seconds() > 900:
                self.chat_memory[channel_id] = {
                    "last_time": now, 
                    "history": [],
                    "active_uid": message.author.id, 
                    "active_name": current_speaker
                }
                
            self.chat_memory[channel_id]["last_time"] = now
            active_uid = self.chat_memory[channel_id]["active_uid"]
            active_name = self.chat_memory[channel_id]["active_name"]
            history_list = self.chat_memory[channel_id]["history"]
            
            users = load_users()
            active_data = get_user_data(active_uid, users)
            is_adult_mode = self.check_adult_mode(active_data, message.channel)

            if not is_adult_mode:
                safe_user_text = user_text.replace("交配", "配對").replace("配種", "配對").replace("🔞", "🚫")
                safe_ref_text = reference_text.replace("交配", "配對").replace("配種", "配對").replace("🔞", "🚫")
            else:
                safe_user_text = user_text
                safe_ref_text = reference_text

            # 讀取偏好引擎
            preferred_engine = self.gm_engine.get(message.author.id, "LM Studio")
            engine_name = preferred_engine if is_admin else "Grok"
            grok_api_key = config.get("grok_api_key", "")
            
            # 如果不是準備使用 LM Studio，且沒有 Grok API Key，就直接拒絕
            if not grok_api_key and engine_name == "Grok":
                kwargs = {"content": "❌ 系統尚未設定 Grok API Key！請伺服器管理員至網頁控制台設定。"}
                if is_in_private_room:
                    return await message.channel.send(**kwargs)
                else:
                    kwargs["mention_author"] = False
                    return await message.reply(**kwargs)

            # ==========================================
            # 🚀 AI 對話請求與雙軌路由
            # ==========================================
            async with message.channel.typing():
                sys_prompt = ""
                
                # 🌙 角色扮演與時間感設定
                sleepy_start = (start_h - 2) % 24
                if sleepy_start < start_h:
                    is_sleepy_time = sleepy_start <= current_h < start_h
                else:
                    is_sleepy_time = current_h >= sleepy_start or current_h < start_h

                emoji_mode = "none"

                if is_adult_mode:
                    if active_data.get("bot_persona"):
                        sys_prompt = active_data["bot_persona"]
                    else:
                        sys_prompt = config.get('late_night_prompt', '請切換為成人模式，語氣性感誘惑。')
                        sys_prompt += f"\n[System Override: 小孩子{base_bot_name}已經乖乖去睡覺了，現在是由{base_bot_name}的媽媽（或成熟的大姐姐）來接替夜間工作，請展現成熟、性感、充滿大人魅力的語氣。]"

                    call_name = active_data.get("called_name") or "主人"
                    bot_name = active_data.get("bot_custom_name") or target_name
                    bot_gender = active_data.get("bot_gender") or "女性"
                    bot_race = active_data.get("bot_race") or "未知"
                    
                    sys_prompt += f"\n[System Override: 這個頻道的專屬服務對象是「{active_name}」，他/她設定你的名字為「{bot_name}」，性別「{bot_gender}」，種族「{bot_race}」，並且要稱呼他/她為「{call_name}」。]"
                    sys_prompt += f"\n[System Override: 這是一個【多人聊天頻道】，除了 {active_name} 之外，可能還有其他人會對你說話。目前對你說話的人是「{current_speaker}」。請維持 {active_name} 為你設定的人格，自然地回應 {current_speaker}，絕對不可切換為其他人的人格！]"
                
                elif is_late_night:
                    # 🌟 一般頻道的深夜模式 (溫柔媽媽代班)
                    bot_name = target_name
                    sys_prompt = config.get('system_prompt', f'你是可愛的又有禮貌的小女孩，名字叫做{base_bot_name}。')
                    sys_prompt += f"\n[System Override: 注意！現在已經是深夜，小女孩{base_bot_name}已經乖乖洗澡睡覺了。現在由「{bot_name}」來代班。請你扮演{bot_name}，語氣像是一位溫柔、賢淑、充滿母愛且善解人意的人妻或長輩，自然地關心大家（例如：夜深了怎麼還沒休息呢、要不要幫忙準備宵夜等日常寒暄）。請告訴大家{base_bot_name}已經睡了，現在由你來陪大家聊天或處理公會事務。]"
                    sys_prompt += f"\n[System Override: 這是一個【多人聊天頻道】。目前對你說話的人是「{current_speaker}」，請你自然地回應他/她。]"
                    sys_prompt += "\n[System Override 重要指示：若對話中提及「黑絲襪」、「嗷嗷交配證」等奇怪道具，請以成熟大人的視角溫柔吐嘈，絕對不要有色情暗示。]"

                elif is_sleepy_time:
                    # 😴 睡前兩小時 (小布打瞌睡)
                    bot_name = base_bot_name
                    sys_prompt = config.get('system_prompt', f'你是可愛的又有禮貌的小女孩，名字叫做{bot_name}。')
                    sys_prompt += f"\n[System Override: 這是一個【多人聊天頻道】。目前對你說話的人是「{current_speaker}」。現在時間很晚了，{bot_name}是一個早睡的小孩子。你現在非常睏，說話時不時會打哈欠、揉眼睛，甚至有點語無倫次，並且要一直跟 {current_speaker} 說你想睡覺了。]"
                    sys_prompt += "\n[System Override: 請分析你當前的情緒，並在回覆的「最結尾」強制加上一個情緒標籤。可用的標籤為：[開心]、[生氣]、[眨眼]、[大哭]、[得意]、[驚訝]、[害羞]、[難過]、[愛心]。]"
                    emoji_mode = "xiaobu"
                    
                else:
                    # ☀️ 正常時段 (活潑小布)
                    bot_name = base_bot_name
                    sys_prompt = config.get('system_prompt', f'你是可愛的又有禮貌的小女孩，名字叫做{bot_name}。')
                    sys_prompt += f"\n[System Override: 這是一個【多人聊天頻道】。目前對你說話的人是「{current_speaker}」，請保持原本活潑禮貌的性格自然地回應他/她，不可使用玩家自訂的稱呼或越界的人格設定。]"
                    sys_prompt += "\n[System Override 重要指示：若對話中提及「黑絲襪」、「抽打」、「配對證」等奇怪道具，這些僅是玩家間的虛擬遊戲道具廣播。你（小女孩）絕對不是當事人！請以「吃瓜群眾」或「調皮吐嘈」的第三人稱視角回應，切勿代入自身。]"
                    sys_prompt += "\n[System Override: 請分析你當前的情緒，並在回覆的「最結尾」強制加上一個情緒標籤。可用的標籤為：[開心]、[生氣]、[眨眼]、[大哭]、[得意]、[驚訝]、[害羞]、[難過]、[愛心]。例如：「今天天氣真好！[開心]」]"
                    emoji_mode = "xiaobu"

                # 🌟 全域格式強制指令
                sys_prompt += "\n[System Override 全域對話格式強制：\n1. 除了結尾必要的情緒標籤外，絕對不要使用任何「小說式的旁白」、「動作/場景描寫」(例如 *微笑*、我頓了頓、(嘆氣))。\n2. 絕對不要加上「角色名字前綴」(例如 小布：、媽媽：)。\n3. 【最高禁令】：你的鍵盤沒有表情符號功能，絕對禁止在文字中使用任何 Emoji (如✨、😂、💖等)！只能打出純文字，否則會極度出戲！\n4. 請【完全像一般真人用 Line 聊天一樣】，直接、口語、自然地打字！]"

                item_lore = (
                    "【公會專屬道具圖鑑知識】\n"
                    "1. 💎 天賞石：極致稀有的閃亮神石。可以「舔一下」嘲諷大家，或用洪荒之力按壓引爆，化作漫天金雨(銅幣)隨機灑給群友！\n"
                    "2. 🖤 大當家的黑絲襪：傳說中大當家珍藏的極品黑絲。使用後會潛入衣櫃竊取並發送高畫質的黑絲美腿照。\n"
                    "3. ⚽ 足球：充滿活力的運動用品。使用後能大力的踢向指定的群友，可能會被帥氣接住、慘遭爆頭，或跟著球一起飛離地球。\n"
                    "4. ⚖️ 審判小錘錘：正義的象徵。能展開「誅伏賜死」領域控告群友，由全服投票，有罪則強制禁言 3 分鐘。\n"
                    "5. 🌸 樁·小花：可以在地上擺滿木樁的奇妙道具。\n"
                    "6. 💦 嗷嗷交配證：神秘的票券，使用後會強制全服廣播呼叫「嗷嗷」出來接客配種。\n"
                    "7. 💳 大人的證明：最高級的 VIP 憑證。只要持有它，就能在深夜時段解鎖隱藏的「成人模式」與「深夜私密包廂」。"
                )
                sys_prompt += f"\n[System Override: 你熟悉公會裡的所有道具。若玩家問起特定道具，請根據以下知識，用符合你人設的語氣為他們解答（可加上對應的 Emoji）：\n{item_lore}]"

                # 🛡️ 安全解析歷史記憶
                history_prompt = ""
                if history_list:
                    history_prompt = "\n\n【近期頻道的對話記憶 (幫助你理解上下文與分辨說話者)】\n"
                    for item in history_list:
                        if len(item) == 3:
                            h_role, h_name, h_text = item
                        elif len(item) == 2:
                            h_role, h_text = item
                            h_name = "大俠" if h_role == "user" else bot_name
                        else:
                            continue
                        history_prompt += f"{h_name}: {h_text}\n"
                    history_prompt += "------------------------"

                full_user_input = safe_user_text
                if safe_ref_text:
                    full_user_input += f"\n\n📋 【以下是 {current_speaker} 請你參考/處理的引用資料】：\n{safe_ref_text}\n\n(❗️強烈指示：請務必根據上述資料，回答或處理 {current_speaker} 的要求：「{safe_user_text}」)"

                response = None
                reply_text = ""
                total_tokens = 0
                used_engine = engine_name
                log_preview = user_text[:20].replace('\n', ' ') if user_text else "要求分析資料"
                
                # --- 嘗試走 LM Studio 引擎 ---
                if engine_name == "LM Studio":
                    try: await message.add_reaction("🩷")
                    except: pass
                    
                    api_url = config.get("lm_studio_url", "http://127.0.0.1:1234/v1/chat/completions")
                    headers = {"Content-Type": "application/json"}
                    
                    lm_messages = [{"role": "system", "content": sys_prompt}]
                    
                    for item in history_list:
                        if len(item) == 3:
                            h_role, h_name, h_text = item
                        elif len(item) == 2:
                            h_role, h_text = item
                            h_name = "大俠" if h_role == "user" else bot_name
                        else:
                            continue
                            
                        if h_role == "user":
                            lm_messages.append({"role": "user", "content": f"{h_name}: {h_text}"})
                        else:
                            lm_messages.append({"role": "assistant", "content": h_text})
                            
                    if safe_ref_text:
                        lm_messages.append({"role": "user", "content": f"📋 【引用資料】：\n{safe_ref_text}\n\n{current_speaker}: {safe_user_text}"})
                    else:
                        lm_messages.append({"role": "user", "content": f"{current_speaker}: {safe_user_text}"})

                    payload = {
                        "model": "local-model", 
                        "messages": lm_messages,
                        "temperature": 0.7,
                        "max_tokens": 1500, 
                        "stream": False 
                    }
                    
                    append_log(f"⏳ [CHAT REQ] {current_speaker} 發起對話 | 引擎: LM Studio | 內容: {log_preview}...")
                    
                    try:
                        resp = await asyncio.to_thread(requests.post, api_url, headers=headers, json=payload, timeout=120)
                        if resp.status_code == 200:
                            resp_json = resp.json()
                            choices = resp_json.get("choices", [])
                            if choices and isinstance(choices, list):
                                reply_text = choices[0].get("message", {}).get("content", "")
                            total_tokens = resp_json.get("usage", {}).get("total_tokens", 0)
                            response = resp
                        else:
                            raise Exception(f"HTTP {resp.status_code}")
                    except Exception as e:
                        append_log(f"⚠️ [LM Studio Fallback] 本地模型無法連線或逾時: {e}。自動降級為 Grok！")
                        try: await message.remove_reaction("🩷", self.bot.user)
                        except: pass
                        try: await message.add_reaction("🔄")
                        except: pass
                        
                        used_engine = "Grok (自動降級)"
                        response = None 
                        
                # --- 嘗試走 Grok 引擎 ---
                if not response:
                    if engine_name == "Grok":
                        try: await message.add_reaction("❤️")
                        except: pass

                    if not grok_api_key:
                        raise Exception("系統未設定 Grok API Key，且本地 LM Studio 連線失敗或未啟用。")
                        
                    api_url = self.grok_api_url_text
                    headers = {"Authorization": f"Bearer {grok_api_key}", "Content-Type": "application/json"}
                    payload = {"model": self.grok_model_name, "input": f"【系統設定：{sys_prompt}】{history_prompt}\n\n{current_speaker} 最新發言：{full_user_input}"}
                    
                    append_log(f"⏳ [CHAT REQ] {current_speaker} 發起對話 | 引擎: {used_engine} | 內容: {log_preview}...")
                    
                    resp = await asyncio.to_thread(requests.post, api_url, headers=headers, json=payload, timeout=60)
                    
                    if resp.status_code == 200:
                        resp_json = resp.json()
                        output_data = resp_json.get("output", [])
                        if isinstance(output_data, list):
                            for block in output_data:
                                if "content" in block:
                                    content_list = block["content"]
                                    if isinstance(content_list, list):
                                        for item in content_list:
                                            if item.get("type") == "output_text": reply_text += item.get("text", "")
                        total_tokens = resp_json.get("usage", {}).get("total_tokens", 0)
                        response = resp
                    else:
                        err_detail = resp.text[:100]
                        raise Exception(f"Grok 伺服器錯誤 HTTP {resp.status_code}: {err_detail}")
                    
                if not reply_text: 
                    reply_text = f"*(系統提示：{used_engine} API 連線成功，但模型沒有產生任何文字回傳)*"
                
                if total_tokens == 0:
                    total_tokens = len(sys_prompt + history_prompt + full_user_input + reply_text)
                    
                update_api_stats(tokens=total_tokens, is_image=False)
                
                discord_file = None
                clean_reply_text = reply_text 
                emoji_name = "None"
                escaped_bot_name = re.escape(bot_name)
                
                if emoji_mode == "xiaobu":
                    mood_map = {
                        '開心': 'happy', '生氣': 'angry', '眨眼': 'wink', 
                        '大哭': 'cry', '得意': 'smug', '驚訝': 'shock', 
                        '害羞': 'shy', '難過': 'sad', '愛心': 'love'
                    }
                    emoji_name = "happy"
                    mood_match = re.search(r'\[(開心|生氣|眨眼|大哭|得意|驚訝|害羞|難過|愛心)\]', reply_text)
                    if mood_match:
                        zh_mood = mood_match.group(1)
                        clean_reply_text = reply_text.replace(mood_match.group(0), '').strip()
                        emoji_name = mood_map.get(zh_mood, "happy")

                    clean_reply_text = re.sub(r'\[.*?\]', '', clean_reply_text).strip()
                    clean_reply_text = re.sub(r'^\*.*?\*\s*', '', clean_reply_text).strip()
                    clean_reply_text = re.sub(rf'^(小布|媽媽|小布的媽媽|我|AI|助手|{escaped_bot_name})\s*[：:]\s*', '', clean_reply_text).strip()
                    
                    emoji_pattern = re.compile(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff\u2600-\u27bf\u2b00-\u2bff\u2300-\u23ff]+', flags=re.UNICODE)
                    clean_reply_text = emoji_pattern.sub('', clean_reply_text)
                    
                    if not clean_reply_text: clean_reply_text = "..."
                    discord_file = get_emoji_file(emoji_name)
                else:
                    clean_reply_text = re.sub(r'\[.*?\]', '', clean_reply_text).strip()
                    clean_reply_text = re.sub(r'^\*.*?\*\s*', '', clean_reply_text).strip()
                    clean_reply_text = re.sub(rf'^(小布|媽媽|小布的媽媽|我|AI|助手|{escaped_bot_name})\s*[：:]\s*', '', clean_reply_text).strip()
                    
                    emoji_pattern = re.compile(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff\u2600-\u27bf\u2b00-\u2bff\u2300-\u23ff]+', flags=re.UNICODE)
                    clean_reply_text = emoji_pattern.sub('', clean_reply_text)
                    
                    if not clean_reply_text: clean_reply_text = "..."
                    discord_file = None

                history_list.append(("user", current_speaker, safe_user_text))
                history_list.append(("bot", bot_name, clean_reply_text))
                
                if len(history_list) > 10:
                    self.chat_memory[channel_id]["history"] = history_list[-10:]

                log_msg = (
                    f"✅ [CHAT RES] 成功回覆 {current_speaker} | 引擎: {used_engine} | Token: {total_tokens}T\n"
                    f"   ↳ 回應內容: {clean_reply_text[:60]}... -> [{'媽媽模式' if emoji_mode == 'none' else emoji_name}]\n"
                    f"{'-'*50}"
                )
                append_log(log_msg)
                
                # ==========================================
                # 🛡️ 安全發送機制 (Kwargs) 防止 file 為 None 崩潰
                # ==========================================
                if is_adult_mode and active_data.get("bot_custom_name") and message.guild:
                    custom_name = active_data.get("bot_custom_name") or target_name
                    try:
                        webhooks = await message.channel.webhooks()
                        webhook = discord.utils.get(webhooks, user=self.bot.user)
                        if not webhook:
                            webhook = await message.channel.create_webhook(name="NSH_RP_Webhook")
                        
                        if is_in_private_room:
                            final_msg = clean_reply_text[:1900]
                        else:
                            final_msg = f"{message.author.mention} {clean_reply_text[:1900]}"
                            
                        wh_kwargs = {"content": final_msg, "username": custom_name, "avatar_url": self.bot.user.display_avatar.url}
                        await webhook.send(**wh_kwargs)
                        return 
                    except discord.Forbidden:
                        clean_reply_text = f"**【{custom_name}】**：\n" + clean_reply_text
                        pass 

                send_kwargs = {"content": clean_reply_text[:1995]}
                if discord_file: send_kwargs["file"] = discord_file
                
                if is_in_private_room:
                    await message.channel.send(**send_kwargs)
                else:
                    send_kwargs["mention_author"] = False
                    await message.reply(**send_kwargs)
                
        except Exception as e:
            # ==========================================
            # 🚨 終極防護網：攔截並回報任何未預期的崩潰
            # ==========================================
            try: await message.remove_reaction("🩷", self.bot.user)
            except: pass
            try: await message.remove_reaction("❤️", self.bot.user)
            except: pass
            try: await message.add_reaction("🔄")
            except: pass

            err_msg = f"❌ [CRITICAL ERROR] 系統發生嚴重錯誤：{e}"
            append_log(err_msg)
            
            error_file = get_emoji_file("cry")
            err_kwargs = {"content": f"嗚嗚，大腦好像打結了...\n`{e}`"}
            if error_file: err_kwargs["file"] = error_file
            
            try:
                if 'is_in_private_room' in locals() and is_in_private_room:
                    await message.channel.send(**err_kwargs)
                else:
                    err_kwargs["mention_author"] = False
                    await message.reply(**err_kwargs)
            except: pass

async def setup(bot):
    await bot.add_cog(AIChat(bot))