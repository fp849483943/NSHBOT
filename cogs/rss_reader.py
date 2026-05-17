import discord
from discord.ext import commands, tasks
import requests
import feedparser
import json
import os
import asyncio
import re
from datetime import datetime, timedelta
from utils import load_config

HISTORY_FILE = "rss_history.json"
YT_HISTORY_FILE = "yt_history.json" # 🌟 新增 YouTube 的歷史紀錄檔

def load_history(filename=HISTORY_FILE):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return []

def save_history(history, filename=HISTORY_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(history[-100:], f, ensure_ascii=False)

def append_log(log_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open("bot_logs.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {log_text}\n")
    except:
        pass

# ==========================================
# 🔗 連結按鈕元件
# ==========================================
class NewsLinkView(discord.ui.View):
    def __init__(self, url, label="前往查看完整內容", emoji="🔗"):
        super().__init__()
        self.add_item(discord.ui.Button(label=label, url=url, emoji=emoji))

class RSSReader(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rss_loop.start()
        self.youtube_loop.start() # 🌟 啟動 YouTube 監聽迴圈

    def cog_unload(self):
        self.rss_loop.cancel()
        self.youtube_loop.cancel()

    # ==========================================
    # ✨ AI 活絡氣氛黑科技 (讀取公告並發表感言)
    # ==========================================
    async def generate_hyped_comment(self, title, config, is_youtube=False, author_name=""):
        api_key = config.get("grok_api_key")
        if not api_key: return None
        
        bot_name = config.get("bot_name", "小布")
        
        if is_youtube:
            # YouTube 專屬提示詞
            sys_prompt = f"你是遊戲公會的貼心小秘書「{bot_name}」。有一位叫「{author_name}」的實況主剛上傳了新影片，標題是「{title}」。這可能是有關副本打法、攻略或遊戲閒聊的影片。請你用極度活潑、期待的口吻，在公會聊天裡向大家推薦這部影片（例如：大家快來看新攻略！）。字數請控制在 50 字以內，可以多使用表情符號。\n[重要指示：請在回覆的最結尾加上代表你心情的標籤，可用標籤為：[喜]、[怒]、[哀]、[樂]、[驚訝]。例如：好期待呀！[喜]]"
        else:
            # 官方公告提示詞
            sys_prompt = f"你是遊戲公會的貼心小秘書「{bot_name}」。官方剛剛發布了最新公告，標題為「{title}」。請你以玩家/粉絲的視角，用極度活潑、期待、或是調皮的口吻，在公會聊天群裡起個頭，帶動大家討論的氣氛（例如：好期待呀~、又有新東西了！之類的）。字數請控制在 50 字以內，可以多使用表情符號。\n[重要指示：請在回覆的最結尾加上代表你心情的標籤，可用標籤為：[喜]、[怒]、[哀]、[樂]、[驚訝]。例如：好期待呀！[喜]]"
        
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "grok-4.20-reasoning", 
                "input": f"【系統指令：{sys_prompt}】\n\n請直接給出你要在群裡說的話，不要包含引號或多餘的解釋。"
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
            append_log(f"⚠️ [AI WARN] 互動生成失敗: {e}")
        return None

    # ==========================================
    # 📺 YouTube 影片自動搬運邏輯 (含關鍵字過濾)
    # ==========================================
    @tasks.loop(minutes=15) # 每 15 分鐘檢查一次 YouTube
    async def youtube_loop(self):
        await self.bot.wait_until_ready()
        config = load_config()
        
        channel_ids = config.get("yt_channel_ids", [])
        discord_channel_id = str(config.get("yt_discord_channel_id", "")).strip()
        
        if not channel_ids or not discord_channel_id:
            return

        target_channel = self.bot.get_channel(int(discord_channel_id))
        if not target_channel:
            return

        history = load_history(YT_HISTORY_FILE)
        is_first_run = len(history) == 0
        new_items = []

        # 🌟 實用過濾關鍵字：影片標題必須包含以下至少一個詞才會轉貼
        # 大俠可依需求在此陣列中自行增減關鍵字
        valid_keywords = ["攻略", "打法", "教學", "推薦", "前瞻", "指南", "職業", "更新", "介紹"]

        # 遍歷所有的 YouTube Channel ID
        for cid in channel_ids:
            try:
                feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
                feed = await asyncio.to_thread(feedparser.parse, feed_url)
                
                for entry in feed.entries:
                    video_id = entry.get("yt_videoid")
                    if not video_id: continue
                    
                    title = entry.get("title", "無標題")
                    
                    # 🌟 核心過濾邏輯：若標題沒有包含任何關鍵字，就直接忽略它！
                    if not any(kw in title for kw in valid_keywords):
                        # 將不想轉貼的短片也塞進歷史紀錄，避免下次又重複檢查
                        if video_id not in history:
                            history.append(video_id)
                        continue
                    
                    # 若符合條件且沒發布過，就準備推播
                    if video_id not in history:
                        link = entry.get("link", f"https://www.youtube.com/watch?v={video_id}")
                        author = entry.get("author", "未知作者")
                        published = entry.get("published", "")
                        
                        new_items.append({
                            "id": video_id,
                            "title": title,
                            "link": link,
                            "author": author,
                            "published": published
                        })
            except Exception as e:
                append_log(f"❌ [YT SCRAPE ERROR] 頻道 {cid} 抓取失敗: {e}")

        # 第一輪執行只寫入歷史，不發送，防洗版
        if is_first_run and new_items:
            history.extend([x["id"] for x in new_items])
            save_history(history, YT_HISTORY_FILE)
            return

        if not new_items:
            # 即使沒新片也要存一下剛剛被過濾掉的廢片ID
            save_history(history, YT_HISTORY_FILE)
            return

        for item in reversed(new_items):
            bot_name = config.get('bot_name', '小布')
            
            # 讓 AI 幫忙說點話
            async with target_channel.typing():
                ai_comment = await self.generate_hyped_comment(item["title"], config, is_youtube=True, author_name=item["author"])
                discord_file = None
                
                if ai_comment:
                    mood_match = re.search(r'\[(喜|怒|哀|樂|害羞|驚訝)\]', ai_comment)
                    if mood_match:
                        mood = mood_match.group(1)
                        ai_comment = ai_comment.replace(mood_match.group(0), '').strip()
                        mood_map = {
                            '喜': 'mood_happy', '怒': 'mood_angry', '哀': 'mood_sad',
                            '樂': 'mood_joy', '害羞': 'mood_shy', '驚訝': 'mood_surprise'
                        }
                        base_name = mood_map.get(mood)
                        if base_name:
                            for ext in ['.gif', '.png', '.jpg']:
                                img_path = os.path.join("assets", "moods", base_name + ext)
                                if os.path.exists(img_path):
                                    discord_file = discord.File(img_path, filename=f"mood{ext}")
                                    break
                
                if not ai_comment:
                    ai_comment = f"大俠！「{item['author']}」剛發布了新影片，快來看看有沒有最新的副本攻略吧！"
                
                await asyncio.sleep(2)
                
                # 發送帶有 YouTube 預覽的訊息
                msg_content = f"📢 **YouTube 攻略快報**\n{ai_comment}\n\n🎬 **{item['title']}**\n👉 {item['link']}"
                
                try:
                    kwargs = {"content": msg_content}
                    if discord_file:
                        kwargs["file"] = discord_file
                    await target_channel.send(**kwargs)
                    history.append(item["id"])
                    append_log(f"📺 [YT POST] 成功發送 YouTube 影片: {item['title']}")
                except Exception as e:
                    append_log(f"❌ [YT POST ERROR] 發送 YouTube 影片失敗: {e}")

        save_history(history, YT_HISTORY_FILE)


    # ==========================================
    # 📰 官網公告搬運邏輯
    # ==========================================
    async def scrape_nsh_official(self):
        url = "https://www.swordofjustice.com/zh-cht/news/official/" 
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        try:
            response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=15)
            response.encoding = 'utf-8' 
            if response.status_code != 200: return []
            
            pattern = r'href="([^"]+news/official/(\d+)/[^"]+\.html)".*?src="([^"]+)"[^>]*>.*?class="time">([\d\.]+)<.*?<p>(.*?)</p>'
            matches = re.findall(pattern, response.text, re.S)

            items = []
            for link, date_id, img_url, date_txt, title in matches:
                full_link = link if link.startswith("http") else f"https://www.swordofjustice.com{link}"
                full_img = img_url if img_url.startswith("http") else f"https://www.swordofjustice.com{img_url}"
                clean_title = re.sub(r'<[^>]+>', '', title).replace('\n', '').strip()
                clean_title = re.sub(r'^\[.*?\]\s*', '', clean_title)
                guid = link.split('/')[-1].replace('.html', '')
                
                pub_date = None
                if date_txt:
                    try:
                        clean_date = date_txt.replace('.', '').strip()
                        pub_date = datetime.strptime(clean_date, "%Y%m%d")
                    except: pass
                
                items.append({"title": clean_title, "link": full_link, "image": full_img, "id": guid, "date": pub_date})
            
            seen = set()
            unique_items = []
            for item in items:
                if item["id"] not in seen:
                    unique_items.append(item)
                    seen.add(item["id"])
            return unique_items
        except Exception as e:
            append_log(f"❌ [SCRAPE ERROR] {e}")
            return []

    @tasks.loop(minutes=10)
    async def rss_loop(self):
        await self.bot.wait_until_ready()
        config = load_config()
        rss_url = config.get("rss_feed_url", "").strip()
        channel_id = str(config.get("rss_channel_id", "")).strip()
        if not channel_id: return

        if "swordofjustice" in rss_url or not rss_url:
            official_posts = await self.scrape_nsh_official()
            if official_posts:
                await self.process_posts(official_posts, channel_id)

    async def process_posts(self, posts, channel_id):
        if not posts: return
        config = load_config()
        channel = self.bot.get_channel(int(channel_id))
        if not channel: return

        history = load_history()
        is_first_run = len(history) == 0
        new_items = []
        threshold = datetime.now() - timedelta(days=7)

        for p in posts:
            if p["id"] and p["id"] not in history:
                if p["date"] and p["date"] < threshold:
                    history.append(p["id"])
                    continue
                new_items.append(p)

        if is_first_run and new_items:
            history.extend([x["id"] for x in new_items])
            new_items = [new_items[0]]

        for p in reversed(new_items):
            bot_name = config.get('bot_name', '小布')
            date_str = p["date"].strftime("%Y-%m-%d") if p["date"] else "未知"
            embed = discord.Embed(
                title=p["title"], url=p["link"],
                description=f"📅 發布日期：{date_str}\n\n大俠，{bot_name} 幫您搬運了官方最新情報！",
                color=0x2b2d31
            )
            if p.get("image"): embed.set_image(url=p["image"])
            embed.set_author(name="逆水寒 - 官方公告同步", icon_url="https://www.swordofjustice.com/favicon.ico")
            embed.set_footer(text=f"來源: Sword of Justice | 同步時間: {datetime.now().strftime('%H:%M')}")
            try:
                await channel.send(embed=embed, view=NewsLinkView(p["link"]))
                if not is_first_run: history.append(p["id"])
                
                chat_channel_id = config.get("rss_chat_channel_id", "").strip()
                if chat_channel_id:
                    chat_channel = self.bot.get_channel(int(chat_channel_id))
                    if chat_channel:
                        async with chat_channel.typing():
                            ai_comment = await self.generate_hyped_comment(p["title"], config)
                            if ai_comment:
                                mood_match = re.search(r'\[(喜|怒|哀|樂|害羞|驚訝)\]', ai_comment)
                                discord_file = None
                                if mood_match:
                                    mood = mood_match.group(1)
                                    ai_comment = ai_comment.replace(mood_match.group(0), '').strip()
                                    mood_map = {
                                        '喜': 'mood_happy', '怒': 'mood_angry', '哀': 'mood_sad',
                                        '樂': 'mood_joy', '害羞': 'mood_shy', '驚訝': 'mood_surprise'
                                    }
                                    base_name = mood_map.get(mood)
                                    if base_name:
                                        for ext in ['.gif', '.png', '.jpg']:
                                            img_path = os.path.join("assets", "moods", base_name + ext)
                                            if os.path.exists(img_path):
                                                discord_file = discord.File(img_path, filename=f"mood{ext}")
                                                break

                                await asyncio.sleep(3) 
                                kwargs = {"content": ai_comment, "embed": embed, "view": NewsLinkView(p["link"])}
                                if discord_file:
                                    kwargs["file"] = discord_file
                                await chat_channel.send(**kwargs)
                            
            except Exception as e:
                append_log(f"❌ [RSS Process Error] 處理公告或發言失敗: {e}")
                pass
                
        save_history(history)

    # ==========================================
    # 👋 小布自我介紹與打招呼指令
    # ==========================================
    @commands.command(name="自我介紹", aliases=["打招呼", "哈囉", "hello", "hi"])
    async def introduce_self(self, ctx):
        config = load_config()
        bot_name = config.get("bot_name", "小布")
        
        intro_text = (
            f"✨ 嗨嗨～～各位大俠好！我是公會的貼心小秘書「**{bot_name}**」！\n"
            f"我平時會幫大家注意官方的最新情報、管理萬事屋的拍賣與抽獎，\n"
            f"大家無聊的時候也可以隨時 `@我` 找我聊天解悶喔！💕\n\n"
            f"👉 如果忘記我有什麼功能，隨時輸入 `!幫助` 就能呼叫功能選單啦！"
        )
        
        file_path = os.path.join("assets", "system", "hello.gif")
        if os.path.exists(file_path):
            discord_file = discord.File(file_path, filename="hello.gif")
            await ctx.reply(intro_text, file=discord_file)
        else:
            await ctx.reply(intro_text + "\n\n*(⚠️ 系統提示：大俠，您忘了把打招呼用的 `hello.gif` 放到 `assets/system/` 目錄底下啦！)*")

async def setup(bot):
    await bot.add_cog(RSSReader(bot))