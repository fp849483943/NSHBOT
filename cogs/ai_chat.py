from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any

import discord
import requests
from discord.ext import commands, tasks

from utils import get_user_data, load_config, load_users, save_users


def update_api_stats(tokens: int = 0, is_image: bool = False):
    today = str(datetime.now().date())
    usage_file = "api_usage.json"
    stats = {"date": today, "count": 0, "image_requests": 0, "chat_requests": 0, "chat_tokens": 0}
    if os.path.exists(usage_file):
        try:
            with open(usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today:
                    stats.update(data)
        except Exception:
            pass
    stats["count"] = stats.get("count", 0) + 1
    if is_image:
        stats["image_requests"] = stats.get("image_requests", 0) + 1
    else:
        stats["chat_requests"] = stats.get("chat_requests", 0) + 1
        stats["chat_tokens"] = stats.get("chat_tokens", 0) + int(tokens or 0)
    try:
        with open(usage_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False)
    except Exception:
        pass


def append_log(log_text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open("bot_logs.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {log_text}\n")
    except Exception:
        pass


def get_emoji_file(emoji_name: str):
    for ext in [".gif", ".png", ".jpg", ".jpeg", ".webp"]:
        path = os.path.join("assets", "emojis", f"{emoji_name}{ext}")
        if os.path.exists(path):
            return discord.File(path, filename=f"emoji_{emoji_name}{ext}")
    return None


def env_or_config(config: dict[str, Any], env_name: str, config_name: str, default: str = "") -> str:
    return (os.getenv(env_name) or config.get(config_name) or default or "").strip()


def extract_response_text(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()
    chunks: list[str] = []
    for block in payload.get("output", []) or []:
        if not isinstance(block, dict):
            continue
        for item in block.get("content", []) or []:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
            elif isinstance(item, str):
                chunks.append(item)
    if chunks:
        return "".join(chunks).strip()
    choices = payload.get("choices", [])
    if choices and isinstance(choices, list):
        msg = (choices[0] or {}).get("message") or {}
        if isinstance(msg.get("content"), str):
            return msg["content"].strip()
    return ""


class AIChat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.chat_memory: dict[int, dict[str, Any]] = {}
        self.current_profile_state: str | None = None
        self.gm_engine: dict[int, str] = {}
        self.profile_loop.start()

    def cog_unload(self):
        self.profile_loop.cancel()

    def is_late_night_now(self, config: dict[str, Any]) -> bool:
        start_h = int(config.get("late_night_start", 23))
        end_h = int(config.get("late_night_end", 5))
        current_h = datetime.now().hour
        if start_h > end_h:
            return current_h >= start_h or current_h < end_h
        return start_h <= current_h < end_h

    def has_adult_access(self, user_data: dict[str, Any]) -> bool:
        config = load_config()
        if not config.get("enable_late_night_mode", True):
            return False
        if user_data.get("inventory", {}).get("大人的證明", 0) <= 0:
            return False
        return self.is_late_night_now(config)

    def check_adult_mode(self, user_data: dict[str, Any], channel) -> bool:
        is_nsfw = isinstance(channel, discord.DMChannel)
        is_nsfw = is_nsfw or bool(getattr(channel, "nsfw", False))
        is_nsfw = is_nsfw or bool(getattr(getattr(channel, "parent", None), "nsfw", False))
        return self.has_adult_access(user_data) and is_nsfw

    @tasks.loop(minutes=10)
    async def profile_loop(self):
        try:
            await self.bot.wait_until_ready()
            config = load_config()
            base_name = config.get("bot_name", "小布")
            state = "night" if self.is_late_night_now(config) else "day"
            if self.current_profile_state == state:
                return
            self.current_profile_state = state

            avatar = "avatar_night.png" if state == "night" else "avatar_day.png"
            avatar_path = os.path.join("assets", "system", avatar)
            if os.path.exists(avatar_path) and self.bot.user:
                try:
                    with open(avatar_path, "rb") as f:
                        await self.bot.user.edit(avatar=f.read())
                except Exception as e:
                    append_log(f"⚠️ [PROFILE WARN] 切換頭像失敗：{e}")

            target_name = f"{base_name}的媽媽" if state == "night" else base_name
            for guild in self.bot.guilds:
                try:
                    if guild.me and guild.me.nick != target_name:
                        await guild.me.edit(nick=target_name)
                except Exception:
                    pass
        except Exception as e:
            append_log(f"⚠️ [PROFILE LOOP WARN] {e}")

    @profile_loop.before_loop
    async def before_profile_loop(self):
        await self.bot.wait_until_ready()

    @commands.command(name="切換大腦", aliases=["switch_engine", "大腦切換", "切換模型", "引擎切換"])
    async def switch_engine(self, ctx: commands.Context):
        try:
            await ctx.message.delete(delay=30.0)
        except Exception:
            pass
        config = load_config()
        if str(ctx.author.id) not in config.get("admin_ids", []):
            return await ctx.reply("❌ 警告：您不是 GM，無法切換大腦！", delete_after=15.0, mention_author=False)
        current = self.gm_engine.get(ctx.author.id, "LM Studio")
        new_engine = "Grok" if current == "LM Studio" else "LM Studio"
        self.gm_engine[ctx.author.id] = new_engine
        msg = f"🔄 **大腦切換成功！**\n{ctx.author.mention} 您現在的專屬對話引擎已切換為：**{new_engine}**"
        if new_engine == "LM Studio":
            msg += "\n*(若 LM Studio 斷線或逾時，系統會自動降級回 Grok 4.3。)*"
        file = get_emoji_file("wink")
        kwargs = {"content": msg, "delete_after": 30.0, "mention_author": False}
        if file:
            kwargs["file"] = file
        await ctx.reply(**kwargs)

    @commands.command(name="大腦測試", aliases=["lm_test", "測試模型"])
    async def lm_studio_test(self, ctx: commands.Context):
        config = load_config()
        if str(ctx.author.id) not in config.get("admin_ids", []):
            return await ctx.reply("❌ 警告：您不是 GM，無權測試本地大腦！", mention_author=False)
        api_url = config.get("lm_studio_url", "http://127.0.0.1:1234/v1/chat/completions")
        model_url = api_url.rsplit("/", 1)[0] + "/models"
        wait_msg = await ctx.reply(f"🔍 **【LM Studio 連線測試】**\n正在嘗試與 `{model_url}` 建立連線...", mention_author=False)
        try:
            resp = await asyncio.to_thread(requests.get, model_url, timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                names = [m.get("id", "unknown") for m in models]
                await wait_msg.edit(content=f"✅ **LM Studio 連線成功！**\n目前模型：`{', '.join(names) if names else '未載入模型'}`")
            else:
                await wait_msg.edit(content=f"⚠️ **連線異常**：HTTP {resp.status_code}")
        except Exception as e:
            await wait_msg.edit(content=f"❌ **連線失敗**：`{e}`")

    @commands.command(name="領取繪圖券", aliases=["領畫布", "領取畫筆", "我要畫畫", "新手福利", "領繪圖券"])
    async def claim_draw_tickets(self, ctx: commands.Context):
        try:
            await ctx.message.delete(delay=30.0)
        except Exception:
            pass
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        if data.get("claimed_free_draw_tickets", False):
            file = get_emoji_file("sad")
            kwargs = {"content": f"❌ {ctx.author.mention} 大俠，您之前已經領取過新手繪圖福利囉！如果需要更多，可以到 `!商店` 購買喔！", "delete_after": 15.0, "mention_author": False}
            if file:
                kwargs["file"] = file
            return await ctx.reply(**kwargs)
        data["claimed_free_draw_tickets"] = True
        data["inventory"]["繪圖券"] = data["inventory"].get("繪圖券", 0) + 10
        save_users(users)
        bot_name = load_config().get("bot_name", "小布")
        file = get_emoji_file("happy")
        kwargs = {"content": f"🎉 **【推廣福利發放】**\n{ctx.author.mention} 成功向 {bot_name} 領取了 **10 張繪圖券**！\n👉 快去使用 `!畫 <提示詞>` 體驗 AI 繪圖吧！🎨", "delete_after": 60.0, "mention_author": False}
        if file:
            kwargs["file"] = file
        await ctx.reply(**kwargs)

    @commands.command(name="忘記", aliases=["清空記憶", "重置", "洗腦"])
    async def clear_memory(self, ctx: commands.Context):
        try:
            await ctx.message.delete(delay=30.0)
        except Exception:
            pass
        if ctx.channel.id in self.chat_memory:
            del self.chat_memory[ctx.channel.id]
            text, emoji = "✨ 小布已經把這個頻道的聊天內容與設定都忘光光囉！我們重新開始吧！", "wink"
        else:
            text, emoji = "❓ 咦？這個頻道裡小布本來就什麼都不記得了呀...", "shy"
        file = get_emoji_file(emoji)
        kwargs = {"content": text, "delete_after": 30.0, "mention_author": False}
        if file:
            kwargs["file"] = file
        await ctx.reply(**kwargs)

    async def call_lm_studio(self, config: dict[str, Any], messages: list[dict[str, str]]) -> tuple[str, int]:
        api_url = config.get("lm_studio_url", "http://127.0.0.1:1234/v1/chat/completions")
        payload = {
            "model": config.get("lm_studio_model", "local-model"),
            "messages": messages,
            "temperature": float(config.get("chat_temperature", 0.7)),
            "max_tokens": int(config.get("chat_max_tokens", 1500)),
            "stream": False,
        }
        resp = await asyncio.to_thread(requests.post, api_url, headers={"Content-Type": "application/json"}, json=payload, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"LM Studio HTTP {resp.status_code}: {resp.text[:160]}")
        body = resp.json()
        text = extract_response_text(body)
        tokens = int((body.get("usage") or {}).get("total_tokens") or 0)
        return text, tokens

    async def call_grok(self, config: dict[str, Any], messages: list[dict[str, str]]) -> tuple[str, int]:
        api_key = env_or_config(config, "XAI_API_KEY", "grok_api_key")
        if not api_key:
            raise RuntimeError("系統尚未設定 XAI_API_KEY / Grok API Key。")
        api_url = config.get("grok_api_url_text", "https://api.x.ai/v1/responses")
        model = config.get("grok_model", "grok-4.3") or "grok-4.3"
        payload = {"model": model, "input": messages}
        resp = await asyncio.to_thread(
            requests.post,
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Grok HTTP {resp.status_code}: {resp.text[:220]}")
        body = resp.json()
        usage = body.get("usage") or {}
        tokens = int(usage.get("total_tokens") or usage.get("input_tokens", 0) + usage.get("output_tokens", 0) or 0)
        return extract_response_text(body), tokens

    def build_system_prompt(self, config: dict[str, Any], active_data: dict[str, Any], current_speaker: str, active_name: str, is_adult_mode: bool, is_late_night: bool, is_sleepy_time: bool) -> tuple[str, str, str]:
        base_name = config.get("bot_name", "小布")
        target_name = f"{base_name}的媽媽" if is_late_night else base_name
        emoji_mode = "none"
        if is_adult_mode:
            bot_name = active_data.get("bot_custom_name") or target_name
            call_name = active_data.get("called_name") or "主人"
            sys_prompt = active_data.get("bot_persona") or config.get("late_night_prompt", "請切換為成人模式，語氣成熟溫柔。")
            sys_prompt += f"\n[System Override: 小孩子{base_name}已經去休息，現在由{target_name}接替夜間工作。]"
            sys_prompt += f"\n[System Override: 專屬服務對象是「{active_name}」，你被設定為「{bot_name}」，稱呼對方為「{call_name}」。目前對你說話的人是「{current_speaker}」。]"
        elif is_late_night:
            bot_name = target_name
            sys_prompt = config.get("system_prompt", f"你是可愛的又有禮貌的小女孩，名字叫做{base_name}。")
            sys_prompt += f"\n[System Override: 現在是深夜，小女孩{base_name}已經睡了。請扮演「{target_name}」，語氣溫柔、成熟、善解人意。目前對你說話的人是「{current_speaker}」。]"
            sys_prompt += "\n[System Override: 遇到奇怪道具或曖昧玩笑時，請用成熟大人的視角溫柔吐槽，不要色情化。]"
        else:
            bot_name = base_name
            sys_prompt = config.get("system_prompt", f"你是可愛的又有禮貌的小女孩，名字叫做{bot_name}。")
            sys_prompt += f"\n[System Override: 目前對你說話的人是「{current_speaker}」，請保持活潑禮貌，像真人聊天一樣自然回應。]"
            if is_sleepy_time:
                sys_prompt += f"\n[System Override: 現在很晚了，{bot_name}很想睡覺，說話可以帶著睏意。]"
            sys_prompt += "\n[System Override: 請在回覆最結尾加入一個情緒標籤：[開心]、[生氣]、[眨眼]、[大哭]、[得意]、[驚訝]、[害羞]、[難過]、[愛心]。]"
            emoji_mode = "xiaobu"
        sys_prompt += "\n[System Override 全域格式：不要使用小說旁白、動作描寫、角色名前綴。除了必要情緒標籤外，不要使用 Emoji。請使用自然口語短句。]"
        sys_prompt += "\n[公會道具知識：天賞石、黑絲襪、足球、審判小錘錘、樁·小花、嗷嗷交配證、大人的證明皆為伺服器虛擬道具。被問到道具時，請用符合人設的語氣解釋。]"
        return sys_prompt, bot_name, emoji_mode

    def sanitize_reply(self, reply_text: str, bot_name: str, emoji_mode: str) -> tuple[str, str | None]:
        mood_map = {"開心": "happy", "生氣": "angry", "眨眼": "wink", "大哭": "cry", "得意": "smug", "驚訝": "shock", "害羞": "shy", "難過": "sad", "愛心": "love"}
        clean = reply_text or ""
        emoji_name = None
        if emoji_mode == "xiaobu":
            emoji_name = "happy"
            mood = re.search(r"\[(開心|生氣|眨眼|大哭|得意|驚訝|害羞|難過|愛心)\]", clean)
            if mood:
                emoji_name = mood_map.get(mood.group(1), "happy")
                clean = clean.replace(mood.group(0), "")
        clean = re.sub(r"\[.*?\]", "", clean).strip()
        clean = re.sub(r"^\*.*?\*\s*", "", clean).strip()
        clean = re.sub(rf"^(小布|媽媽|小布的媽媽|我|AI|助手|{re.escape(bot_name)})\s*[：:]\s*", "", clean).strip()
        emoji_pattern = re.compile(r"[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff\u2600-\u27bf\u2b00-\u2bff\u2300-\u23ff]+", flags=re.UNICODE)
        clean = emoji_pattern.sub("", clean).strip()
        return (clean or "...")[:1995], emoji_name

    async def read_reference_text(self, message: discord.Message) -> tuple[str, int]:
        if not (message.reference and message.reference.message_id):
            return "", 0
        try:
            ref_msg = message.reference.resolved
            if ref_msg is None or isinstance(ref_msg, discord.DeletedReferencedMessage):
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if not isinstance(ref_msg, discord.Message):
                return "", 0
            text = f"【發言者/來源: {ref_msg.author.display_name}】\n{ref_msg.content or ''}"
            for embed in ref_msg.embeds:
                if embed.title:
                    text += f"\n[標題]: {embed.title}"
                if embed.description:
                    text += f"\n[內容]: {embed.description}"
                for field in embed.fields:
                    if field.name and field.value:
                        text += f"\n[{field.name}]: {field.value}"
            return text.strip(), ref_msg.author.id
        except Exception as e:
            append_log(f"⚠️ [WARN] 無法讀取引用訊息: {e}")
            return "", 0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.content.startswith("!") or message.content.startswith("！"):
            return
        try:
            config = load_config()
            is_admin = str(message.author.id) in config.get("admin_ids", [])
            base_name = config.get("bot_name", "小布")
            is_late_night = self.is_late_night_now(config)
            start_h = int(config.get("late_night_start", 23))
            current_h = datetime.now().hour
            sleepy_start = (start_h - 2) % 24
            is_sleepy_time = sleepy_start <= current_h < start_h if sleepy_start < start_h else current_h >= sleepy_start or current_h < start_h
            target_name = f"{base_name}的媽媽" if is_late_night else base_name
            reference_text, ref_author_id = await self.read_reference_text(message)
            is_in_private_room = hasattr(self.bot, "active_rooms") and message.channel.id in self.bot.active_rooms.values()
            is_mentioned = False
            if self.bot.user in message.mentions:
                is_mentioned = True
            elif self.bot.user and ref_author_id == self.bot.user.id:
                is_mentioned = True
            elif message.guild and message.role_mentions:
                is_mentioned = any(role in message.guild.me.roles for role in message.role_mentions)
            elif f"@{base_name}" in message.clean_content or f"@{target_name}" in message.clean_content or "@小布" in message.clean_content:
                is_mentioned = True
            elif is_in_private_room:
                is_mentioned = True
            if not is_mentioned:
                return

            user_text = re.sub(r"<@!?&?\d+>", "", message.content).strip()
            user_text = user_text.replace(f"@{target_name}", "").replace(f"@{base_name}", "").replace("@小布", "").strip()
            if not user_text and not reference_text:
                if is_in_private_room:
                    return
                return await message.reply(f"找{base_name}有什麼事嗎？", mention_author=False)

            if any(kw in user_text for kw in ["領取繪圖券", "新手福利", "領畫畫券", "領繪圖券", "給我繪圖券", "給我畫布"]):
                users = load_users()
                data = get_user_data(message.author.id, users)
                if not data.get("claimed_free_draw_tickets", False):
                    data["claimed_free_draw_tickets"] = True
                    data["inventory"]["繪圖券"] = data["inventory"].get("繪圖券", 0) + 10
                    save_users(users)
                    reply_msg = f"🎉 **【推廣福利發放】**\n{message.author.mention} 成功領取了 **10 張繪圖券**！\n👉 快使用 `!畫 <提示詞>` 讓{base_name}為您作畫吧！🎨"
                else:
                    reply_msg = f"❌ {message.author.mention} 大俠，您已經領取過繪圖福利囉！如果需要更多，可以去 `!商店` 購買喔！"
                return await (message.channel.send(reply_msg) if is_in_private_room else message.reply(reply_msg, mention_author=False))

            now = datetime.now()
            channel_id = message.channel.id
            current_speaker = message.author.display_name
            if channel_id not in self.chat_memory or (now - self.chat_memory[channel_id]["last_time"]).total_seconds() > 900:
                self.chat_memory[channel_id] = {"last_time": now, "history": [], "active_uid": message.author.id, "active_name": current_speaker}
            mem = self.chat_memory[channel_id]
            mem["last_time"] = now
            active_uid = mem["active_uid"]
            active_name = mem["active_name"]
            history = mem["history"]
            users = load_users()
            active_data = get_user_data(active_uid, users)
            is_adult_mode = self.check_adult_mode(active_data, message.channel)
            safe_user_text = user_text if is_adult_mode else user_text.replace("交配", "配對").replace("配種", "配對").replace("🔞", "🚫")
            safe_ref_text = reference_text if is_adult_mode else reference_text.replace("交配", "配對").replace("配種", "配對").replace("🔞", "🚫")
            engine_name = self.gm_engine.get(message.author.id, "LM Studio") if is_admin else "Grok"
            sys_prompt, bot_name, emoji_mode = self.build_system_prompt(config, active_data, current_speaker, active_name, is_adult_mode, is_late_night, is_sleepy_time)
            messages = [{"role": "system", "content": sys_prompt}]
            for item in history[-10:]:
                if len(item) == 3:
                    h_role, h_name, h_text = item
                elif len(item) == 2:
                    h_role, h_text = item
                    h_name = "大俠" if h_role == "user" else bot_name
                else:
                    continue
                messages.append({"role": "user" if h_role == "user" else "assistant", "content": f"{h_name}: {h_text}" if h_role == "user" else h_text})
            full_user_input = safe_user_text
            if safe_ref_text:
                full_user_input += f"\n\n【引用資料】\n{safe_ref_text}\n\n請根據引用資料回應「{safe_user_text}」。"
            messages.append({"role": "user", "content": f"{current_speaker}: {full_user_input}"})

            reply_text = ""
            total_tokens = 0
            used_engine = engine_name
            async with message.channel.typing():
                if engine_name == "LM Studio":
                    try:
                        await message.add_reaction("🩷")
                        reply_text, total_tokens = await self.call_lm_studio(config, messages)
                    except Exception as e:
                        append_log(f"⚠️ [LM Studio Fallback] {e}，自動降級為 Grok 4.3。")
                        used_engine = "Grok 4.3 (自動降級)"
                        try:
                            await message.add_reaction("🔄")
                        except Exception:
                            pass
                if not reply_text:
                    if engine_name == "Grok":
                        try:
                            await message.add_reaction("❤️")
                        except Exception:
                            pass
                    reply_text, total_tokens = await self.call_grok(config, messages)
                    if used_engine == "Grok":
                        used_engine = config.get("grok_model", "grok-4.3")
            if not reply_text:
                reply_text = f"*(系統提示：{used_engine} API 連線成功，但模型沒有產生文字回傳)*"
            if total_tokens == 0:
                total_tokens = len(sys_prompt + full_user_input + reply_text)
            update_api_stats(tokens=total_tokens, is_image=False)
            clean_reply, emoji_name = self.sanitize_reply(reply_text, bot_name, emoji_mode)
            history.append(("user", current_speaker, safe_user_text))
            history.append(("bot", bot_name, clean_reply))
            mem["history"] = history[-10:]
            append_log(f"✅ [CHAT RES] 成功回覆 {current_speaker} | 引擎: {used_engine} | Token: {total_tokens}T")
            discord_file = get_emoji_file(emoji_name) if emoji_name else None
            if is_adult_mode and active_data.get("bot_custom_name") and message.guild:
                custom_name = active_data.get("bot_custom_name") or target_name
                try:
                    webhooks = await message.channel.webhooks()
                    webhook = discord.utils.get(webhooks, user=self.bot.user)
                    if not webhook:
                        webhook = await message.channel.create_webhook(name="NSH_RP_Webhook")
                    content = clean_reply[:1900] if is_in_private_room else f"{message.author.mention} {clean_reply[:1900]}"
                    await webhook.send(content=content, username=custom_name, avatar_url=self.bot.user.display_avatar.url)
                    return
                except discord.Forbidden:
                    clean_reply = f"**【{custom_name}】**：\n{clean_reply}"
            kwargs = {"content": clean_reply[:1995]}
            if discord_file:
                kwargs["file"] = discord_file
            if is_in_private_room:
                await message.channel.send(**kwargs)
            else:
                kwargs["mention_author"] = False
                await message.reply(**kwargs)
        except Exception as e:
            append_log(f"❌ [CRITICAL ERROR] {e}")
            err = {"content": f"嗚嗚，大腦好像打結了...\n`{e}`"}
            file = get_emoji_file("cry")
            if file:
                err["file"] = file
            try:
                if "is_in_private_room" in locals() and is_in_private_room:
                    await message.channel.send(**err)
                else:
                    err["mention_author"] = False
                    await message.reply(**err)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChat(bot))
