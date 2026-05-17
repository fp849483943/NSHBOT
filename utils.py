from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import discord

ROOT_DIR = Path(__file__).resolve().parent
USERS_FILE = ROOT_DIR / "users.json"
CONFIG_FILE = ROOT_DIR / "config.json"
EMOJI_DIR = ROOT_DIR / "assets" / "emojis"


def _safe_read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + ".broken")
        try:
            path.replace(backup)
        except Exception:
            pass
        return default
    except Exception:
        return default


def _safe_write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    tmp.replace(path)


def get_emoji_path(emoji_name: str) -> Path | None:
    for ext in (".gif", ".png", ".jpg", ".jpeg", ".webp"):
        p = EMOJI_DIR / f"{emoji_name}{ext}"
        if p.exists():
            return p
    return None


def get_emoji_file(emoji_name: str) -> discord.File | None:
    p = get_emoji_path(emoji_name)
    if not p:
        return None
    return discord.File(str(p), filename=f"emoji_{emoji_name}{p.suffix}")


async def send_with_emoji(interaction_or_ctx, content=None, embed=None, view=None, emoji_name="happy", ephemeral=False, delete_after=None):
    emoji_path = get_emoji_path(emoji_name)
    file = None
    if embed and emoji_path:
        file = discord.File(str(emoji_path), filename="emoji.png")
        embed.set_thumbnail(url="attachment://emoji.png")
    if isinstance(interaction_or_ctx, discord.Interaction):
        if interaction_or_ctx.response.is_done():
            return await interaction_or_ctx.followup.send(content=content, embed=embed, file=file, view=view, ephemeral=ephemeral)
        await interaction_or_ctx.response.send_message(content=content, embed=embed, file=file, view=view, ephemeral=ephemeral)
        return await interaction_or_ctx.original_response()
    return await interaction_or_ctx.send(content=content, embed=embed, file=file, view=view, delete_after=delete_after)


def load_users() -> dict[str, Any]:
    return _safe_read_json(USERS_FILE, {})


def save_users(users: dict[str, Any]):
    _safe_write_json(USERS_FILE, users)


def get_user_data(user_id, users: dict[str, Any]) -> dict[str, Any]:
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
            "called_name": "",
            "claimed_free_draw_tickets": False,
        }
    data = users[uid_str]
    if "inventory" not in data or not isinstance(data.get("inventory"), dict):
        data["inventory"] = {}
    if data.get("items", 0) > 0:
        data["inventory"]["鑒石神鑿"] = data["inventory"].get("鑒石神鑿", 0) + data["items"]
        data["items"] = 0
    defaults = {
        "coins": 0,
        "items": 0,
        "last_divination": "",
        "daily_coins_earned": 0,
        "last_update": today,
        "pity_count": 0,
        "scrap": 0,
        "sign_in_streak": 0,
        "last_sign_in": "",
        "grand_pulls": 0,
        "bot_persona": "",
        "called_name": "",
        "claimed_free_draw_tickets": False,
    }
    for key, value in defaults.items():
        data.setdefault(key, value)
    if data["last_update"] != today:
        data["daily_coins_earned"] = 0
        data["last_update"] = today
    return data


def default_config() -> dict[str, Any]:
    return {
        "bot_name": "小布",
        "command_prefix": "!",
        "system_prompt": "你是可愛的又有禮貌的小女孩，名字叫做小布，而且你無所不知，面對大家的問題都能對答如流。",
        "admin_ids": ["123456789012345678"],
        "discord_token": "",
        "grok_api_key": "",
        "openai_api_key": "",
        "grok_model": os.getenv("XAI_MODEL", "grok-4.3"),
        "grok_vision_model": os.getenv("XAI_VISION_MODEL", "grok-4.3"),
        "grok_api_url_text": os.getenv("XAI_API_URL_TEXT", "https://api.x.ai/v1/responses"),
        "lm_studio_url": "http://127.0.0.1:1234/v1/chat/completions",
        "video_api_url": os.getenv("VIDEO_API_URL", ""),
        "video_api_key": os.getenv("VIDEO_API_KEY", ""),
        "video_model": os.getenv("VIDEO_MODEL", ""),
        "video_duration_seconds": 5,
        "video_aspect_ratio": "16:9",
        "video_ticket_cost": 5,
        "video_api_timeout": 180,
        "game_news_feeds": [],
        "enable_game_news_auto": False,
        "game_news_channel_id": "",
        "game_search_api_url": os.getenv("GAME_SEARCH_API_URL", ""),
        "game_search_api_key": os.getenv("GAME_SEARCH_API_KEY", ""),
        "activity_reminders": [],
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
        "daily_sign_coins": 500,
        "daily_sign_item": "鑒石神鑿",
        "daily_sign_item_qty": 1,
        "cmd_gacha": "神鑿",
        "cmd_divination": "機運",
        "cmd_shop": "商店",
        "cmd_buy": "買",
        "cmd_sell": "賣",
        "cmd_backpack": "背包",
        "cmd_gm": "gm_money",
        "cmd_sign": "簽到",
        "cmd_rank": "排行榜",
        "cmd_transfer": "轉帳",
        "cmd_gift": "贈送",
        "cmd_use": "使用",
        "cmd_help": "幫助",
        "pool_grand": ["御春麟", "白虹麟", "紫霆麟", "焚業麟"] + ["天賞石"] * 36,
        "pool_rare": ["播放器", "魚戲", "髮型：鯨羽/雲山千里", "髮型：霜寒/折紅扇", "月", "玳筵", "虎虎生風", "義承千斤", "奔虹赤", "雪糕", "蒼翼", "玩偶", "香噴噴"],
        "pool_normal": ["風箏", "輕容染", "螺黛染", "清虛凝丹·15份", "照夜", "花擁香霧", "映月", "奇賞石"],
        "shop_items": {"鑒石神鑿": 180, "大喇叭": 50, "改名卡": 500, "幸運草": 300, "繪圖券": 50},
        "sell_prices": {"天賞石": 5000, "御春麟": 15000, "奇賞石": 100, "風箏": 5},
        "hidden_shop_items": {"大人的證明": 999, "鑒石神鑿(黑市)": 90},
        "usable_items": {"大喇叭": "廣播", "幸運草": "抽獎時增加好運", "大人的證明": "被動解鎖深夜成人模式"},
        "ai_image_cost": 50,
        "ai_image_ticket_cost": 1,
        "ai_image_daily_limit": 50,
        "enable_grand_effect": True,
        "enable_late_night_mode": True,
        "late_night_start": 23,
        "late_night_end": 5,
        "late_night_prompt": "請切換為成人模式，語氣成熟、溫柔、帶有大人魅力。",
        "rss_feed_url": "",
        "rss_channel_id": "",
        "rss_chat_channel_id": "",
        "yt_channel_ids": [],
        "yt_discord_channel_id": "",
        "reminders": [],
        "enable_eew": False,
        "enable_eew_ws": False,
        "eew_channel_id": "",
        "eew_websocket_url": "wss://ws-eew.teew.tw/",
        "cwa_api_key": os.getenv("CWA_API_KEY", ""),
        "bot_latitude": 22.68,
        "bot_longitude": 120.30,
    }


def load_config() -> dict[str, Any]:
    config = _safe_read_json(CONFIG_FILE, {})
    if not isinstance(config, dict):
        config = {}
    merged = default_config()
    merged.update(config)
    if isinstance(merged.get("admin_ids"), str):
        merged["admin_ids"] = [x.strip() for x in merged["admin_ids"].split(",") if x.strip()]
    if isinstance(merged.get("yt_channel_ids"), str):
        merged["yt_channel_ids"] = [x.strip() for x in merged["yt_channel_ids"].splitlines() if x.strip()]
    if isinstance(merged.get("game_news_feeds"), str):
        merged["game_news_feeds"] = [x.strip() for x in merged["game_news_feeds"].replace(",", "\n").splitlines() if x.strip()]
    if not isinstance(merged.get("reminders"), list):
        merged["reminders"] = []
    if not isinstance(merged.get("activity_reminders"), list):
        merged["activity_reminders"] = []
    return merged


def save_config(config: dict[str, Any]):
    merged = default_config()
    merged.update(config)
    _safe_write_json(CONFIG_FILE, merged)
