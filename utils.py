import json
import os
from datetime import datetime
import discord

USERS_FILE = 'users.json'
CONFIG_FILE = 'config.json'
EMOJI_DIR = os.path.join('assets', 'emojis')

# ==========================================
# 🎨 小布表情系統 (核心工具函式)
# ==========================================
async def send_with_emoji(interaction_or_ctx, content=None, embed=None, view=None, emoji_name="happy", ephemeral=False, delete_after=None):
    """
    發送帶有小布表情圖片的訊息。
    
    :param interaction_or_ctx: discord.Interaction 或 commands.Context 物件
    :param content: 文字訊息內容
    :param embed: Embed 物件
    :param view: View 物件
    :param emoji_name: 表情代碼 (happy, angry, cry, ...)
    :param ephemeral: 是否為隱藏訊息 (僅 Interaction 有效)
    :param delete_after: 自動刪除時間 (秒)
    """
    emoji_path = os.path.join(EMOJI_DIR, f"{emoji_name}.png")
    file = None
    
    # 如果 Embed 存在，將表情設為縮圖
    if embed and os.path.exists(emoji_path):
        file = discord.File(emoji_path, filename="emoji.png")
        embed.set_thumbnail(url="attachment://emoji.png")

    # 判斷是 Interaction 還是 Context
    if isinstance(interaction_or_ctx, discord.Interaction):
        # Interaction 回覆
        if interaction_or_ctx.response.is_done():
             # 如果已經回覆過，則使用 followup 發送新訊息
            msg = await interaction_or_ctx.followup.send(content=content, embed=embed, file=file, view=view, ephemeral=ephemeral)
        else:
            # 尚未回覆，直接回覆
            await interaction_or_ctx.response.send_message(content=content, embed=embed, file=file, view=view, ephemeral=ephemeral)
            msg = await interaction_or_ctx.original_response()

    else:
        # Context 發送 (傳統指令)
        if file:
            msg = await interaction_or_ctx.send(content=content, embed=embed, file=file, view=view, delete_after=delete_after)
        else:
            msg = await interaction_or_ctx.send(content=content, embed=embed, view=view, delete_after=delete_after)
            
    return msg

# ==========================================
# 👤 玩家資料處理區 (讀取、儲存、初始化)
# ==========================================
def load_users():
    """讀取玩家 JSON 資料庫"""
    if not os.path.exists(USERS_FILE): 
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f: 
        return json.load(f)

def save_users(users):
    """儲存玩家資料至 JSON"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f: 
        json.dump(users, f, indent=4)

def get_user_data(user_id, users):
    """獲取特定玩家資料，若無則自動初始化預設值"""
    today = str(datetime.now().date())
    uid_str = str(user_id)
    
    if uid_str not in users:
        users[uid_str] = {
            "coins": 0, 
            "items": 0, 
            "inventory": {}, 
            "last_divination": "", 
            "daily_coins_earned": 0, 
            "last_update": today, 
            "pity_count": 0, 
            "scrap": 0, 
            "sign_in_streak": 0, 
            "last_sign_in": "", 
            "grand_pulls": 0, 
            "bot_persona": "", 
            "called_name": ""
        }
        
    # 確保背包欄位存在
    if "inventory" not in users[uid_str]:
        users[uid_str]["inventory"] = {}
        # 舊版道具轉換
        if users[uid_str].get("items", 0) > 0:
            users[uid_str]["inventory"]["鑒石神鑿"] = users[uid_str]["items"]
            users[uid_str]["items"] = 0 
            
    # 確保新欄位存在於舊玩家資料中 (向下相容)
    for key in ["pity_count", "scrap", "sign_in_streak", "grand_pulls"]:
        if key not in users[uid_str]: 
            users[uid_str][key] = 0
            
    if "last_sign_in" not in users[uid_str]: users[uid_str]["last_sign_in"] = ""
    if "bot_persona" not in users[uid_str]: users[uid_str]["bot_persona"] = ""
    if "called_name" not in users[uid_str]: users[uid_str]["called_name"] = ""
    
    # 每日更新收益上限重置
    if users[uid_str]["last_update"] != today:
        users[uid_str]["daily_coins_earned"] = 0
        users[uid_str]["last_update"] = today
        
    return users[uid_str]

# ==========================================
# ⚙️ 系統設定檔處理區 (控制台參數、指令名稱、獎池)
# ==========================================
def load_config():
    """讀取系統設定檔，若缺失則補上預設值"""
    default_config = {
        "bot_name": "小布",
        "system_prompt": "你是可愛的又有禮貌的小女孩，名字叫做小布，而且你無所不知，面對大家的問題都能對答如流。",
        "admin_ids": ["123456789012345678"], 
        "enable_economy": True,
        "enable_gacha": True,
        "coin_daily_limit": 500,
        "coin_per_message": 5,
        "item_price": 180,
        "gacha_pity_count": 180,
        "gacha_rate_grand": 4, 
        "gacha_rate_rare": 40,
        "enable_auto_convert": False,
        "auto_convert_rate": 20,
        
        # 每日簽到設定
        "daily_sign_coins": 100,
        "daily_sign_item": "鑒石神鑿",
        "daily_sign_item_qty": 1,
        
        # 指令名稱自訂
        "cmd_gacha": "神鑿", "cmd_divination": "求籤", "cmd_shop": "商店", 
        "cmd_buy": "買", "cmd_sell": "賣", "cmd_backpack": "背包", 
        "cmd_gm": "gm_money", "cmd_sign": "簽到", "cmd_rank": "排行榜", 
        "cmd_transfer": "轉帳", "cmd_gift": "贈送", "cmd_use": "使用",
        
        # 獎池設定
        "pool_grand": ["御春麟", "白虹麟", "紫霆麟", "焚業麟"] + ["天賞石"] * 36,
        "pool_rare": ["播放器", "魚戲", "髮型：鯨羽/雲山千里", "髮型：霜寒/折紅扇", "月", "玳筵", "虎虎生風", "義承千斤", "奔虹赤", "雪糕", "蒼翼", "玩偶", "香噴噴"],
        "pool_normal": ["風箏", "輕容染", "螺黛染", "清虛凝丹·15份", "照夜", "花擁香霧", "映月", "奇賞石"],
        
        # 商店與道具系統
        "shop_items": {"鑒石神鑿": 180, "大喇叭": 50, "改名卡": 500, "幸運草": 300},
        "sell_prices": {"天賞石": 5000, "御春麟": 15000, "奇賞石": 100, "風箏": 5},
        "hidden_shop_items": {"大人的證明": 999, "鑒石神鑿(黑市)": 90}, 
        "usable_items": {"大喇叭": "廣播", "幸運草": "抽獎時增加好運", "大人的證明": "被動解鎖深夜成人模式"}, 
        "ai_image_cost": 50,
        
        # YouTube 轉貼設定
        "yt_channel_ids": [],
        "yt_discord_channel_id": "",
        
        # 🚨 EEW 地震速報設定
        "enable_eew": False,
        "eew_channel_id": ""
    }
    
    # 若檔案不存在，直接回傳預設字典
    if not os.path.exists(CONFIG_FILE): 
        return default_config
        
    # 讀取並合併設定 (確保新增的欄位會被自動加進舊有的 config 中)
    with open(CONFIG_FILE, 'r', encoding='utf-8') as loaded_config_file:
        loaded_config = json.load(loaded_config_file)
        
    for key, value in default_config.items():
        if key not in loaded_config: 
            loaded_config[key] = value
            
    return loaded_config

def save_config(config):
    """儲存系統設定檔至 JSON"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)