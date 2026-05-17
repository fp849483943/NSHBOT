import discord
from discord.ext import commands
import requests
import asyncio
import os
import json
from datetime import datetime
import io
import re
from PIL import Image
from utils import load_config, load_users, get_user_data, save_users

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

# ==========================================
# 📐 智能圖片比例分析器 (圖生圖專用)
# ==========================================
def get_best_fit_ratio(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        if response.status_code != 200:
            return "auto"
            
        img = Image.open(io.BytesIO(response.content))
        width, height = img.size
        
        if width <= 0 or height <= 0:
            return "auto"
            
        ratio = width / height
        
        supported_ratios = {
            "21:9": 21/9, "2:1": 2.0, "16:9": 16/9, "3:2": 1.5, "4:3": 4/3, "5:4": 5/4,
            "1:1": 1.0,
            "4:5": 4/5, "3:4": 3/4, "2:3": 2/3, "9:16": 9/16, "1:2": 0.5, "9:21": 9/21
        }
        
        best_match = "auto"
        min_diff = float('inf')
        
        for name, target_ratio in supported_ratios.items():
            diff = abs(ratio - target_ratio)
            if diff < min_diff:
                min_diff = diff
                best_match = name
                
        append_log(f"📐 [IMAGE RATIO] 圖片尺寸: {width}x{height} (比例: {ratio:.2f}) -> 智能判定為: {best_match}")
        return best_match
        
    except Exception as e:
        append_log(f"⚠️ [IMAGE RATIO WARN] 智能比例分析失敗: {e}")
        return "auto"

# ==========================================
# 📝 提示詞模板儲存系統
# ==========================================
TEMPLATES_FILE = "image_templates.json"

def load_templates():
    if not os.path.exists(TEMPLATES_FILE):
        default_templates = {
            "故障賽博海報(自訂)": "生成一张附圖的人物海报。故障艺术风格，赛博朋克动漫美学，数字碎片化构图。画面由多个错位的矩形窗口和几何切片叠加而成，呈现出一种数据损坏和图像溢出的视觉感。核心风格包含：像素排序效果、RGB色彩偏移、横向拉伸的数字噪点以及彩虹色调的电流纹理。背景采用极简主义的米白色，与画面中心高饱和度的湛蓝天空、厚重的积雨云形成强烈视觉对比。整体氛围带有超现实的忧郁感和深邃的数字空间感。角色名稱（請修改），角色伺服器（請修改），角色職業（請修改），角色服飾改为符合主题的服饰，主色调以人物发色为主，配上一段符合人物的句子，16:9，2k",
            "水彩插畫風": "精緻的水彩畫風格，色彩柔和，邊緣暈染，童話繪本感",
            "賽博龐克風": "賽博龐克風格，未來城市，霓虹燈光，高對比度，科技感，16:9",
            "史詩電影感": "好萊塢史詩電影質感，大氣磅礡，體積光，極致細節，8k畫質，16:9"
        }
        save_templates(default_templates)
        return default_templates
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_templates(templates):
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=4)

# ==========================================
# 🔍 終極版圖片網址解析器
# ==========================================
def extract_image_urls(obj):
    urls = []
    try:
        data_block = obj.get("data")
        if isinstance(data_block, list) and len(data_block) > 0:
            data_block = data_block[0]
            
        if isinstance(data_block, dict):
            result_block = data_block.get("result", {})
            if isinstance(result_block, dict):
                images_list = result_block.get("images", [])
                if isinstance(images_list, list):
                    for img_obj in images_list:
                        url_data = img_obj.get("url")
                        if isinstance(url_data, list):
                            for u in url_data:
                                if isinstance(u, str) and u.startswith("http"):
                                    urls.append(u)
                        elif isinstance(url_data, str) and url_data.startswith("http"):
                            urls.append(url_data)
    except Exception as e:
        append_log(f"⚠️ [IMAGE PARSE WARN] 嘗試精準解析失敗: {e}")

    if urls:
        return list(dict.fromkeys(urls))

    def recursive_search(curr_obj):
        if isinstance(curr_obj, dict):
            for k in ["url", "image_url", "link"]:
                if k in curr_obj:
                    val = curr_obj[k]
                    if isinstance(val, str) and val.startswith("http"):
                        urls.append(val)
                    elif isinstance(val, list):
                        for v in val:
                            if isinstance(v, str) and v.startswith("http"):
                                urls.append(v)
            for v in curr_obj.values():
                recursive_search(v)
        elif isinstance(curr_obj, list):
            for item in curr_obj:
                recursive_search(item)

    recursive_search(obj)
    return list(dict.fromkeys(urls))

# ==========================================
# 🎨 AI 繪圖引擎選擇面板 (View)
# ==========================================
class DrawEngineView(discord.ui.View):
    def __init__(self, author_id, clean_prompt, detected_size, detected_res, cost, config, attachment_urls=None, is_gm=False):
        super().__init__(timeout=60.0)
        self.author_id = author_id
        self.clean_prompt = clean_prompt
        self.detected_size = detected_size
        self.detected_res = detected_res
        self.cost = cost
        self.config = config
        self.attachment_urls = attachment_urls or []
        self.is_gm = is_gm
        self.message = None

    async def generate_image(self, interaction: discord.Interaction, engine: str):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 你不能幫別人決定啦！", ephemeral=True)

        users = load_users()
        data = get_user_data(self.author_id, users)
        
        actual_size = self.detected_size
        actual_res = self.detected_res
        is_i2i_downgraded = False
        auto_detected_ratio = False
        
        # 🌟 雙重防護機制：如果不是 GM，絕對不允許 2K/4K！
        if not self.is_gm and actual_res in ["2k", "4k"]:
            actual_res = "1k"
        
        if engine == "GPT Image 2":
            if self.attachment_urls:
                if actual_size == "auto":
                    await interaction.response.edit_message(content="🔍 正在智能分析參考圖片的完美比例，請稍候...", embed=None, view=None)
                    actual_size = await asyncio.to_thread(get_best_fit_ratio, self.attachment_urls[0])
                    auto_detected_ratio = True
                
            supported_4k_sizes = ["16:9", "9:16", "2:1", "1:2", "21:9", "9:21"]
            if actual_res == "4k" and actual_size not in supported_4k_sizes:
                actual_res = "2k"
                is_i2i_downgraded = True
        
        actual_cost = self.cost
        if engine == "GPT Image 2" and actual_res in ["2k", "4k"]:
            actual_cost = self.cost * 3
        
        if actual_cost > 0 and not self.is_gm:
            if data["inventory"].get("繪圖券", 0) < actual_cost:
                if interaction.response.is_done():
                    return await interaction.followup.send(f"❌ 您的【繪圖券】不足！({engine} 需要 {actual_cost} 張)", ephemeral=True)
                else:
                    return await interaction.response.send_message(f"❌ 您的【繪圖券】不足！({engine} 需要 {actual_cost} 張)", ephemeral=True)
            
            data["inventory"]["繪圖券"] -= actual_cost
            if data["inventory"]["繪圖券"] <= 0: del data["inventory"]["繪圖券"]
            save_users(users)

        wait_text = f"🎨 收到！小布正在呼叫 **{engine}** 為您作畫，請稍候片刻...\n*(此引擎通常需要等待 30~60 秒，請大俠耐心等候喔！)*"
        if engine == "GPT Image 2":
            if actual_res in ["2k", "4k"]:
                wait_text = f"🎨 收到！小布正在呼叫 **{engine}** 繪製 {actual_res.upper()} 高畫質大作！\n⚠️ *(高畫質生成需要較長時間，可能需等候 1~3 分鐘，請大俠千萬要耐心等候！)*"
            
            if is_i2i_downgraded:
                wait_text += f"\n🛡️ *(系統提示：{actual_size} 比例不支援 4K，已為您安全降級為 2K)*"
            elif auto_detected_ratio:
                wait_text += f"\n📏 *(系統提示：已自動為您偵測並鎖定最適合的比例：{actual_size})*"
                
        if interaction.response.is_done():
            await interaction.edit_original_response(content=wait_text, embed=None, view=None)
        else:
            await interaction.response.edit_message(content=wait_text, embed=None, view=None)

        try:
            if engine == "Grok":
                api_key = self.config.get("grok_api_key", "")
                if not api_key: raise Exception("未設定 Grok API Key，請通知管理員。")
                
                if self.attachment_urls:
                    api_url = "https://api.x.ai/v1/images/edits"
                    payload = {
                        "model": "grok-imagine-image", 
                        "prompt": self.clean_prompt,
                        "image": {"url": self.attachment_urls[0]} 
                    }
                else:
                    api_url = "https://api.x.ai/v1/images/generations"
                    payload = {"model": "grok-imagine-image", "prompt": self.clean_prompt}
                
            elif engine == "GPT Image 2":
                api_key = self.config.get("openai_api_key", "")
                if not api_key: raise Exception("未設定 APIMart 金鑰 (請至控制台 OpenAI 欄位填寫)。")
                api_url = "https://api.apimart.ai/v1/images/generations"
                
                payload = {
                    "model": "gpt-image-2", 
                    "prompt": self.clean_prompt, 
                    "n": 1, 
                    "size": actual_size,
                    "resolution": actual_res
                }
                if self.attachment_urls:
                    payload["image_urls"] = self.attachment_urls

            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            append_log(f"🎨 [IMAGE REQ] {interaction.user.name} 請求繪圖 ({engine}): 比例={actual_size} 畫質={actual_res} | {self.clean_prompt[:25]}...")
            
            response = await asyncio.to_thread(requests.post, api_url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                resp_json = response.json()
                img_urls = []
                task_id = None
                
                img_urls = extract_image_urls(resp_json)
                
                if not img_urls:
                    data_obj = resp_json.get("data", {})
                    if isinstance(data_obj, list) and len(data_obj) > 0:
                        first_item = data_obj[0]
                        if isinstance(first_item, dict):
                            task_id = first_item.get("task_id") or first_item.get("id")
                    elif isinstance(data_obj, dict):
                        task_id = data_obj.get("task_id") or data_obj.get("id")
                        
                    if not task_id:
                        task_id = resp_json.get("task_id") or resp_json.get("id")
                        
                if task_id and not img_urls:
                    poll_url = f"https://api.apimart.ai/v1/tasks/{task_id}"
                    
                    append_log(f"⏳ [IMAGE POLL] 取得 task_id: {task_id}，等待 15 秒後開始輪詢...")
                    await asyncio.sleep(15)
                    
                    for attempt in range(60):
                        try:
                            poll_resp = await asyncio.to_thread(requests.get, poll_url, headers=headers, timeout=15)
                        except Exception as e:
                            append_log(f"⚠️ [IMAGE POLL WARN] 輪詢請求發生異常 (嘗試 {attempt+1}): {e}")
                            await asyncio.sleep(5)
                            continue 
                            
                        if poll_resp.status_code == 200:
                            raw_json = poll_resp.json()
                            data_obj = raw_json.get("data", {})
                            
                            if isinstance(data_obj, list) and len(data_obj) > 0:
                                data_obj = data_obj[0]
                            elif not isinstance(data_obj, dict):
                                data_obj = {}
                            
                            status = str(raw_json.get("status", data_obj.get("status", ""))).lower()
                            
                            if status == "completed":
                                img_urls = extract_image_urls(raw_json)
                                if not img_urls:
                                    raise Exception(f"✅ 任務顯示 completed，但解析不到圖片！回傳: {str(raw_json)[:200]}")
                                break
                                
                            elif status == "failed":
                                err_info = raw_json.get("error", data_obj.get("error", {}))
                                err_msg = err_info.get("message", "未知失敗原因") if isinstance(err_info, dict) else str(err_info)
                                raise Exception(f"APIMart 任務生成失敗 (原因: {err_msg[:100]})")
                                
                            elif status in ["submitted", "processing"]:
                                pass
                            else:
                                append_log(f"⚠️ [IMAGE POLL INFO] 收到未知狀態 '{status}'，繼續輪詢...")
                                
                        await asyncio.sleep(5)
                    
                    if not img_urls:
                        raise Exception("生成任務超時未完成 (已等候超過 5 分鐘)，請稍後再試！")
                
                if not img_urls:
                    raise Exception(f"未知的 API 回傳格式！無法解析圖片網址。回傳: {str(resp_json)[:150]}")

                update_api_stats(is_image=True)
                
                save_dir = os.path.join("assets", "ai_draws")
                if not os.path.exists(save_dir): 
                    os.makedirs(save_dir)
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                files_to_send = []
                for i, url in enumerate(img_urls):
                    try:
                        img_resp = await asyncio.to_thread(requests.get, url, timeout=30)
                        if img_resp.status_code == 200:
                            img_bytes = img_resp.content
                            
                            try:
                                save_path = os.path.join(save_dir, f"{timestamp_str}_{interaction.user.name}_{engine.replace(' ', '')}_{i}.png")
                                with open(save_path, "wb") as f:
                                    f.write(img_bytes)
                            except Exception as save_err:
                                append_log(f"⚠️ [IMAGE SAVE WARN] 無法保存圖片至硬碟: {save_err}")
                                
                            files_to_send.append(discord.File(io.BytesIO(img_bytes), filename=f"ai_draw_{i}.png"))
                        else:
                            append_log(f"⚠️ [IMAGE FETCH WARN] 下載圖片 {i} 失敗，HTTP {img_resp.status_code}")
                    except Exception as e:
                        append_log(f"⚠️ [IMAGE FETCH WARN] 抓取圖片 {i} 發生例外: {e}")
                
                if not files_to_send:
                    raise Exception("雖然成功獲取了網址，但是圖片無法下載 (可能是網址失效或網路問題)！")

                success_emoji = get_emoji_file("smug")
                
                embed_title = f"👑 [GM特權] 小布的畫廊 ({engine})" if self.is_gm else f"🎨 小布的得意之作 ({engine})"
                embed_desc = f"**大俠的要求**：`{self.clean_prompt}`"
                
                if engine == "GPT Image 2":
                    embed_desc += f"\n*(📐 比例: {actual_size} | 🎞️ 畫質: {actual_res.upper()})*"
                
                if actual_cost > 0 and not self.is_gm:
                    embed_desc += f"\n*(消耗了 {actual_cost} 張繪圖券)*"
                if len(files_to_send) > 1:
                    embed_desc += f"\n*(✨ 這次為您畫了 {len(files_to_send)} 張喔！)*"
                if self.attachment_urls:
                    embed_desc += f"\n*(📎 使用了 {len(self.attachment_urls)} 張參考圖進行圖生圖)*"
                
                embed = discord.Embed(title=embed_title, description=embed_desc, color=0xffb6c1)
                embed.set_image(url="attachment://ai_draw_0.png")
                
                if success_emoji: 
                    if len(files_to_send) < 10:
                        files_to_send.append(success_emoji)

                if self.message:
                    try: await self.message.delete()
                    except: pass
                    
                await interaction.channel.send(content=interaction.user.mention, embed=embed, files=files_to_send)
                append_log(f"✅ [IMAGE RES] {interaction.user.name} 畫圖成功！({engine}, 共 {len(files_to_send)-1 if success_emoji else len(files_to_send)} 張)")
                
            else:
                if actual_cost > 0 and not self.is_gm:
                    data["inventory"]["繪圖券"] = data["inventory"].get("繪圖券", 0) + actual_cost
                    save_users(users)

                if self.message:
                    try: await self.message.delete()
                    except: pass
                    
                try:
                    err_json = response.json()
                    err_info = err_json.get("error", {})
                    error_detail = err_info.get("message", response.text[:100]) if isinstance(err_info, dict) else str(err_info)
                except:
                    error_detail = response.text[:100]
                
                cry_emoji = get_emoji_file("cry")
                err_text = f"{interaction.user.mention} 嗚嗚，**{engine}** 的畫筆斷掉了...\n*(API連線錯誤：HTTP {response.status_code})*\n`原因：{error_detail}`"
                if actual_cost > 0 and not self.is_gm:
                    err_text += "\n*(🎟️ 繪圖券已退還給您)*"
                err_text += "\n*(🧹 此錯誤訊息將於 30 秒後自動清理)*"
                
                await interaction.channel.send(err_text, file=cry_emoji, delete_after=30.0)
                append_log(f"❌ [IMAGE ERROR] {engine} 提交失敗 HTTP {response.status_code} - {error_detail}")

        except Exception as e:
            if actual_cost > 0 and not self.is_gm:
                data["inventory"]["繪圖券"] = data["inventory"].get("繪圖券", 0) + actual_cost
                save_users(users)

            if self.message:
                try: await self.message.delete() 
                except: pass
            
            cry_emoji = get_emoji_file("cry")
            err_text = f"{interaction.user.mention} 嗚嗚，**{engine}** 的連線斷掉了，畫筆也飛走了...\n`{e}`"
            if actual_cost > 0 and not self.is_gm:
                err_text += "\n*(🎟️ 繪圖券已退還給您)*"
            err_text += "\n*(🧹 此錯誤訊息將於 30 秒後自動清理)*"
            
            await interaction.channel.send(err_text, file=cry_emoji, delete_after=30.0)
            append_log(f"❌ [IMAGE SYSTEM ERROR] {engine} 系統異常: {e}")

    @discord.ui.button(label="Grok 小畫家", style=discord.ButtonStyle.primary, emoji="🤖")
    async def btn_grok(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.generate_image(interaction, "Grok")

    @discord.ui.button(label="GPT Image 2", style=discord.ButtonStyle.success, emoji="✨")
    async def btn_gptimage2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.generate_image(interaction, "GPT Image 2")

    async def on_timeout(self):
        if self.message:
            try: await self.message.delete()
            except: pass

# ==========================================
# 📝 模板填寫與編輯視窗 (Modal)
# ==========================================
class TemplateEditModal(discord.ui.Modal):
    def __init__(self, author_id, template_name, original_prompt, attachment_urls, is_gm, original_message):
        super().__init__(title=f"編輯模板：{template_name[:15]}")
        self.author_id = author_id
        self.attachment_urls = attachment_urls
        self.is_gm = is_gm
        self.original_message = original_message

        self.prompt_input = discord.ui.TextInput(
            label="您可以直接修改下方提示詞中的設定：",
            style=discord.TextStyle.paragraph,
            default=original_prompt,
            required=True,
            max_length=3000
        )
        self.add_item(self.prompt_input)

    async def on_submit(self, interaction: discord.Interaction):
        edited_prompt = self.prompt_input.value.strip()
        await interaction.response.defer()
        
        await AIImage.send_drawing_interface(
            interaction.channel, 
            interaction.user, 
            edited_prompt, 
            self.attachment_urls, 
            self.is_gm, 
            self.original_message
        )

# ==========================================
# 📑 模板選擇下拉選單 (View)
# ==========================================
class TemplateSelectView(discord.ui.View):
    def __init__(self, author_id, config, attachment_urls, is_gm=False):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.config = config
        self.attachment_urls = attachment_urls
        self.is_gm = is_gm
        self.message = None
        
        templates = load_templates()
        options = []
        for name, prompt in list(templates.items())[:25]:
            preview = prompt[:45] + "..." if len(prompt) > 45 else prompt
            options.append(discord.SelectOption(label=name, description=preview, value=name, emoji="📝"))
            
        if not options:
            options.append(discord.SelectOption(label="目前沒有儲存的模板", value="none"))

        select = discord.ui.Select(placeholder="👇 請選擇一個提示詞模板...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 請自己輸入繪圖指令來選擇模板喔！", ephemeral=True)
            
        val = self.children[0].values[0]
        if val == "none":
            return await interaction.response.send_message("❌ 目前沒有可用的模板。", ephemeral=True)
            
        templates = load_templates()
        selected_prompt = templates.get(val, "")
        
        if not selected_prompt:
            return await interaction.response.send_message("❌ 找不到該模板！可能剛剛被刪除了。", ephemeral=True)
            
        await interaction.response.send_modal(TemplateEditModal(
            self.author_id, 
            val, 
            selected_prompt, 
            self.attachment_urls, 
            self.is_gm, 
            self.message
        ))

    async def on_timeout(self):
        if self.message:
            try: await self.message.delete()
            except: pass

# ==========================================
# 🖼️ 主模組：AI 生圖與模板管理
# ==========================================
class AIImage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def send_drawing_interface(channel, user, prompt, attachment_urls, is_gm, original_message_to_delete=None):
        clean_prompt = prompt
        detected_size = "auto"
        detected_res = "1k"
        
        size_match = re.search(r'(16:9|9:16|4:3|3:4|1:1|3:2|2:3|5:4|4:5|2:1|1:2|21:9|9:21)', clean_prompt)
        if size_match:
            detected_size = size_match.group(1)
            clean_prompt = clean_prompt.replace(detected_size, "").strip()
            
        res_match = re.search(r'(4k|2k|1k)', clean_prompt, re.IGNORECASE)
        if res_match:
            detected_res = res_match.group(1).lower()
            clean_prompt = re.sub(r'(4k|2k|1k)', '', clean_prompt, flags=re.IGNORECASE).strip()

        # 🌟 非 GM 玩家高畫質防呆降級
        is_downgraded_for_normal_user = False
        if not is_gm and detected_res in ["2k", "4k"]:
            detected_res = "1k"
            is_downgraded_for_normal_user = True
            
        supported_4k_sizes = ["16:9", "9:16", "2:1", "1:2", "21:9", "9:21", "auto"]
        if detected_res == "4k" and detected_size not in supported_4k_sizes:
            detected_res = "2k"

        config = load_config()
        users = load_users()
        data = get_user_data(user.id, users)
        cost = config.get("ai_image_ticket_cost", 1)

        if not is_gm and data["inventory"].get("繪圖券", 0) < cost:
            file = get_emoji_file("sad")
            return await channel.send(f"{user.mention} ❌ 您的【繪圖券】不足！(需要 {cost} 張，您目前有 {data['inventory'].get('繪圖券', 0)} 張)", file=file, delete_after=15.0)

        desc = f"大俠的要求：`{clean_prompt}`\n"
        if detected_size != "auto" or detected_res != "1k":
            desc += f"*(📐 比例: {detected_size} | 🎞️ 畫質: {detected_res.upper()})*\n"
        if attachment_urls:
            desc += f"*(📎 已附帶 {len(attachment_urls)} 張參考圖)*\n"
            
        if is_downgraded_for_normal_user:
            desc += "\n🛡️ *(系統提示：2K / 4K 高畫質目前僅開放給 GM 特權使用，已自動為您切換為標準 1K 畫質)*\n"
            
        if is_gm:
            desc += "\n*(👑 此為 GM 無限特權，不消耗任何繪圖券)*\n"
            desc += "*(💡 **GM 專屬秘技**：您可直接在提示詞中加入 `16:9`、`4K` 來解鎖最高畫質與調整比例！)*\n"
        else:
            desc += "\n小布認識兩位厲害的畫家，請選擇您要指派哪一位？\n*(🎟️ 繪圖券將在成功畫出後才會扣除)*\n"
        
        if detected_res in ["2k", "4k"]:
            warning_title = "【GM 嚴重警告】" if is_gm else "【嚴重警告】"
            desc += f"\n⚠️ **{warning_title}**\n您選擇了 `{detected_res.upper()}` 高畫質！\n若指派 **GPT Image 2** 繪製：\n1️⃣ **API 成本價格飆升 3 倍** "
            desc += "(無限制)" if is_gm else f"(將扣除 {cost * 3} 張繪圖券)"
            desc += "\n2️⃣ **生成時間較長** (需等候 1~3 分鐘)\n👉 *大俠請耐心等候！*"

        title = "👑 [GM特權] 請選擇小畫家" if is_gm else "🎨 請選擇小畫家"
        embed = discord.Embed(title=title, description=desc, color=0xffd700 if is_gm else 0x5865F2)
        embed.set_footer(text="*(🧹 此選單將於 60 秒後自動清理)*")

        view = DrawEngineView(user.id, clean_prompt, detected_size, detected_res, cost, config, attachment_urls, is_gm)
        
        if original_message_to_delete:
            try: await original_message_to_delete.delete()
            except: pass
            
        msg = await channel.send(content=user.mention, embed=embed, view=view, delete_after=60.0)
        view.message = msg

    @commands.command(name="儲存模板", aliases=["存模板", "新增模板", "save_template"])
    async def save_prompt_template(self, ctx, template_name: str = "", *, prompt: str = ""):
        try: await ctx.message.delete(delay=15.0)
        except: pass
        
        if not template_name or not prompt:
            file = get_emoji_file("angry")
            return await ctx.send(f"{ctx.author.mention} 格式錯誤啦！\n*(請輸入：`!儲存模板 <模板名稱> <提示詞內容>`)*", file=file, delete_after=15.0)
            
        templates = load_templates()
        
        if len(templates) >= 25 and template_name not in templates:
            file = get_emoji_file("sad")
            return await ctx.send(f"{ctx.author.mention} ❌ 模板數量已達上限 (25個)，請先刪除一些舊的模板喔！", file=file, delete_after=15.0)
            
        templates[template_name] = prompt
        save_templates(templates)
        
        file = get_emoji_file("happy")
        await ctx.send(f"✅ {ctx.author.mention} 太棒了！小布已經把神級模板 **【{template_name}】** 記下來囉！\n*(下次打 `!畫` 不加提示詞就能直接呼叫它！)*", file=file, delete_after=15.0)

    @commands.command(name="刪除模板", aliases=["移除模板", "del_template"])
    async def delete_prompt_template(self, ctx, template_name: str = ""):
        try: await ctx.message.delete(delay=15.0)
        except: pass
        
        if not template_name:
            return await ctx.send(f"{ctx.author.mention} 格式錯誤！\n*(請輸入：`!刪除模板 <模板名稱>`)*", delete_after=15.0)
            
        templates = load_templates()
        if template_name in templates:
            del templates[template_name]
            save_templates(templates)
            await ctx.send(f"🗑️ {ctx.author.mention} 已成功將模板 **【{template_name}】** 丟進垃圾桶！", delete_after=15.0)
        else:
            await ctx.send(f"❌ {ctx.author.mention} 找不到名為 **【{template_name}】** 的模板喔！", delete_after=15.0)

    # 🌟 新增 60 秒 CD 限制 (以防洗版)
    @commands.command(name="畫", aliases=["畫圖", "生圖"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def draw_image(self, ctx, *, prompt: str = ""):
        attachment_urls = [
            a.url for a in ctx.message.attachments 
            if a.content_type and a.content_type.startswith('image/')
        ]

        if attachment_urls:
            async def delayed_delete():
                await asyncio.sleep(60.0)
                try: await ctx.message.delete()
                except: pass
            ctx.bot.loop.create_task(delayed_delete())
        else:
            try: await ctx.message.delete()
            except: pass

        if not prompt:
            config = load_config()
            embed = discord.Embed(
                title="📑 智能模板選擇庫",
                description=f"{ctx.author.mention} 大俠似乎不知道畫什麼，小布這裡有些珍藏的「神級提示詞模板」，要直接套用嗎？\n\n*(如果您想自己想，請輸入 `!畫 <提示詞>`)*",
                color=0x5865F2
            )
            if attachment_urls:
                embed.description += f"\n\n*(📎 小布偵測到您上傳了 {len(attachment_urls)} 張圖片，選定模板後將直接進行圖生圖！)*"
                
            embed.set_footer(text="*(🧹 此選單將於 60 秒後自動清理)*")
            
            view = TemplateSelectView(ctx.author.id, config, attachment_urls, is_gm=False)
            msg = await ctx.send(content=ctx.author.mention, embed=embed, view=view, delete_after=60.0)
            view.message = msg
            return

        await self.send_drawing_interface(ctx.channel, ctx.author, prompt, attachment_urls, is_gm=False)

    # 🌟 處理生圖 CD 時的錯誤訊息
    @draw_image.error
    async def draw_image_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            file = get_emoji_file("cry")
            try: await ctx.message.delete()
            except: pass
            await ctx.send(f"⏳ {ctx.author.mention} 畫師的手還在抽筋呢！請等待 **{int(error.retry_after)}** 秒後再呼叫小布！", file=file, delete_after=15.0)

    @commands.command(name="GM畫", aliases=["gm畫", "gm_draw"])
    async def gm_draw_image(self, ctx, *, prompt: str = ""):
        attachment_urls = [
            a.url for a in ctx.message.attachments 
            if a.content_type and a.content_type.startswith('image/')
        ]

        if attachment_urls:
            async def delayed_delete():
                await asyncio.sleep(60.0)
                try: await ctx.message.delete()
                except: pass
            ctx.bot.loop.create_task(delayed_delete())
        else:
            try: await ctx.message.delete()
            except: pass

        config = load_config()
        if str(ctx.author.id) not in config.get('admin_ids', []):
            file = get_emoji_file("angry")
            return await ctx.send(f"{ctx.author.mention} ❌ 警告：你不是 GM，無法使用此神聖特權指令！", file=file, delete_after=15.0)

        if not prompt:
            embed = discord.Embed(
                title="👑 [GM特權] 智能模板選擇庫",
                description=f"{ctx.author.mention} GM 大俠，請選擇要測試的神級模板！",
                color=0xffd700
            )
            if attachment_urls:
                embed.description += f"\n\n*(📎 小布偵測到您上傳了 {len(attachment_urls)} 張圖片，選定模板後將直接進行圖生圖！)*"
                
            embed.set_footer(text="*(🧹 此選單將於 60 秒後自動清理)*")
            
            view = TemplateSelectView(ctx.author.id, config, attachment_urls, is_gm=True)
            msg = await ctx.send(content=ctx.author.mention, embed=embed, view=view, delete_after=60.0)
            view.message = msg
            return

        await self.send_drawing_interface(ctx.channel, ctx.author, prompt, attachment_urls, is_gm=True)

async def setup(bot):
    await bot.add_cog(AIImage(bot))