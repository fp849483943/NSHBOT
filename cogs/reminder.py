import discord
from discord.ext import commands, tasks
import requests
import asyncio
import os
import random
import re
from datetime import datetime
from utils import load_config

def append_log(log_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open("bot_logs.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {log_text}\n")
    except:
        pass

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder_loop.start()
        self.random_bubble_loop.start() # 🌟 啟動隨機冒泡循環
        self.last_remind_time = ""
        self.last_chat_time = datetime.now() # 🌟 記錄最後一次頻道有人說話的時間

    def cog_unload(self):
        self.reminder_loop.cancel()
        self.random_bubble_loop.cancel()

    # ==========================================
    # 🌟 監聽群友聊天，重置安靜計時器
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        config = load_config()
        # 追蹤目標：優先監聽 AI 聊天專屬頻道，否則監聽提醒頻道
        target_channel_id = config.get("rss_chat_channel_id") or config.get("reminder_channel_id")
        
        if str(message.channel.id) == str(target_channel_id):
            self.last_chat_time = datetime.now()

    # ==========================================
    # ✨ AI 潤色黑科技：讓提醒更有溫度
    # ==========================================
    async def polish_reminder(self, content, config):
        api_key = config.get("grok_api_key")
        if not api_key:
            return content
        
        bot_name = config.get("bot_name", "小布")
        sys_prompt = f"你是遊戲公會的貼心小秘書「{bot_name}」。請以活潑、親切、且帶有江湖武俠氣息的口吻，將以下這段活動提醒重新包裝，使其具有吸引力與情感。要求：不要超過 150 字，多使用表情符號，並且務必保留原本提及的時間與活動名稱。"
        
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "grok-4.20-reasoning", 
                "input": f"【系統指令：{sys_prompt}】\n\n原始需傳達內容：{content}"
            }
            response = await asyncio.to_thread(requests.post, "https://api.x.ai/v1/responses", headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                resp_json = response.json()
                reply = ""
                for block in resp_json.get("output", []):
                    if "content" in block:
                        for item in block["content"]:
                            if item.get("type") == "output_text":
                                reply += item.get("text", "")
                if reply: return reply.strip()
        except Exception as e:
            append_log(f"⚠️ [AI WARN] 提醒任務潤色失敗: {e}")
        return content

    # ==========================================
    # 💭 小布無聊冒泡循環 (純文字，零 Token 消耗)
    # ==========================================
    @tasks.loop(minutes=30)
    async def random_bubble_loop(self):
        await self.bot.wait_until_ready()
        config = load_config()
        
        target_channel_id = config.get("rss_chat_channel_id") or config.get("reminder_channel_id")
        if not target_channel_id:
            return
            
        bubble_prob = int(config.get("bubble_probability", 30))
        if bubble_prob <= 0: 
            return # 機率為 0 則關閉冒泡功能

        silence_minutes = int(config.get("bubble_silence_minutes", 60))
        now = datetime.now()
        
        # 🌟 如果頻道安靜超過設定的分鐘數
        if (now - self.last_chat_time).total_seconds() > (silence_minutes * 60):
            # 🌟 根據控制台設定的機率觸發
            if random.randint(1, 100) <= bubble_prob:
                channel = self.bot.get_channel(int(target_channel_id))
                if channel:
                    async with channel.typing():
                        bubbles = [
                            "咕嚕咕嚕... 🫧",
                            "*偷偷探頭* 👀",
                            "街上都沒人，小布來掃掃地 🧹",
                            "*默默冒個泡* 🎈",
                            "今天天氣真好呀 ☀️",
                            "(發呆中) 😶",
                            "有人發現角落裡長出了一朵小蘑菇嗎 🍄",
                            "茶都涼了... 🍵",
                            "一二三木頭人！...看來真的沒人呢 🪵"
                        ]
                        bubble_msg = random.choice(bubbles)

                        await asyncio.sleep(2) # 稍微延遲假裝打字
                        await channel.send(bubble_msg)
                        append_log("💭 [BUBBLE] 小布因為太無聊，自己跑出來冒泡了！(零消耗)")
                        
                # 重置計時器，避免連續冒泡洗版
                self.last_chat_time = datetime.now()

    # ==========================================
    # ⏰ 公會活動小秘書核心 (支援動態多頻道排程)
    # ==========================================
    @tasks.loop(seconds=60)
    async def reminder_loop(self):
        await self.bot.wait_until_ready()
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        weekday = now.weekday() # 0=週一, 6=週日
        
        if self.last_remind_time == current_time:
            return

        config = load_config()
        reminders = config.get("scheduled_reminders", [])
        default_channel_id = config.get("reminder_channel_id") or config.get("rss_channel_id")
        
        if not reminders:
            return

        tasks_triggered = 0
        for task in reminders:
            task_days = task.get("days", [])
            task_times = task.get("times", [])
            
            if weekday in task_days and current_time in task_times:
                # 判斷發送頻道 (若任務有自訂則覆蓋預設)
                target_channel_id = task.get("channel_id")
                if not target_channel_id:
                    target_channel_id = default_channel_id
                
                if not target_channel_id:
                    append_log(f"⚠️ [REMIND WARN] 提醒任務「{task.get('name')}」沒有指定發送頻道！")
                    continue
                    
                channel = self.bot.get_channel(int(target_channel_id))
                if not channel:
                    append_log(f"❌ [REMIND ERROR] 找不到指定的頻道 ID: {target_channel_id}")
                    continue

                original_content = task.get("content", "大俠，活動要開始囉！")
                bot_name = config.get('bot_name', '小布')
                original_content = original_content.replace("{bot_name}", bot_name)
                
                # 🌟 開啟「輸入中...」狀態，避免 AI 思考時像是當機
                async with channel.typing():
                    if task.get("ai_polish", False):
                        final_msg = await self.polish_reminder(original_content, config)
                        await asyncio.sleep(2) # 稍微延遲 2 秒假裝正在用心打字
                    else:
                        final_msg = f"🔔 **活動提醒**\n{original_content}"

                    try:
                        embed = discord.Embed(
                            title=f"📌 {task.get('name', '公會活動提醒')}",
                            description=final_msg,
                            color=0x5865F2
                        )
                        embed.set_footer(text=f"{bot_name} 萬事屋小秘書")
                        await channel.send(embed=embed)
                        tasks_triggered += 1
                        append_log(f"⏰ [REMIND] 發送提醒: {task.get('name')} 至頻道 #{channel.name}")
                    except discord.Forbidden:
                        append_log(f"❌ [REMIND ERROR] 權限不足！無法發送提醒至 #{channel.name}")
                    except Exception as e:
                        append_log(f"❌ [REMIND ERROR] 發送失敗: {e}")

        if tasks_triggered > 0:
            self.last_remind_time = current_time

async def setup(bot):
    await bot.add_cog(Reminder(bot))