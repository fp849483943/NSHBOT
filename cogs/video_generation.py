from __future__ import annotations

import asyncio
import os
from typing import Any

import discord
import requests
from discord.ext import commands

from utils import load_config, load_users, get_user_data, save_users


def _env_or_config(config: dict[str, Any], env_name: str, config_name: str, default: str = "") -> str:
    return (os.getenv(env_name) or config.get(config_name) or default or "").strip()


def _extract_video_url(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("video_url", "url", "output_url", "download_url"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                found = _extract_video_url(item)
                if found:
                    return found
        elif isinstance(data, dict):
            found = _extract_video_url(data)
            if found:
                return found
        result = payload.get("result")
        if isinstance(result, (dict, list)):
            found = _extract_video_url(result)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_video_url(item)
            if found:
                return found
    return ""


class VideoGeneration(commands.Cog):
    """可配置的動畫 / 影片生成模組。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _collect_reference_images(self, message: discord.Message) -> list[str]:
        urls: list[str] = []
        for attachment in message.attachments:
            if (attachment.content_type or "").startswith("image/") or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                urls.append(attachment.url)
        return urls

    async def _call_video_api(self, prompt: str, image_urls: list[str]) -> str:
        config = load_config()
        api_url = _env_or_config(config, "VIDEO_API_URL", "video_api_url")
        api_key = _env_or_config(config, "VIDEO_API_KEY", "video_api_key")
        model = _env_or_config(config, "VIDEO_MODEL", "video_model", "")

        if not api_url or not api_key:
            raise RuntimeError("尚未設定 VIDEO_API_URL / VIDEO_API_KEY。這個模組是通用接口，可接 Runway、Kling、Luma 或其他第三方影片 API。")

        payload: dict[str, Any] = {
            "prompt": prompt,
            "model": model or None,
            "duration": int(config.get("video_duration_seconds", 5)),
            "aspect_ratio": config.get("video_aspect_ratio", "16:9"),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        if image_urls:
            payload["image_urls"] = image_urls[:2]

        response = await asyncio.to_thread(
            requests.post,
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=int(config.get("video_api_timeout", 180)),
        )
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(f"Video API HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        video_url = _extract_video_url(data)
        if video_url:
            return video_url
        task_id = data.get("task_id") or data.get("id") or (data.get("data") or {}).get("task_id") if isinstance(data.get("data"), dict) else None
        if task_id:
            return f"影片任務已建立：`{task_id}`。如果你的供應商需要輪詢，請把輪詢端點填入 README 後續規格再擴充。"
        return "影片任務已送出，但 API 沒有回傳影片網址或 task_id。"

    @commands.command(name="動畫", aliases=["生成動畫", "影片", "生影片", "video"])
    async def generate_video(self, ctx: commands.Context, *, prompt: str = ""):
        if not prompt:
            return await ctx.reply("❌ 用法：`!動畫 <動畫描述>`，可附上一張圖片作為參考。", mention_author=False)

        config = load_config()
        cost = int(config.get("video_ticket_cost", 5))
        is_admin = str(ctx.author.id) in config.get("admin_ids", [])
        if cost > 0 and not is_admin:
            users = load_users()
            data = get_user_data(ctx.author.id, users)
            if data["inventory"].get("繪圖券", 0) < cost:
                return await ctx.reply(f"❌ 生成動畫需要 {cost} 張【繪圖券】，你的數量不足。", mention_author=False)
            data["inventory"]["繪圖券"] -= cost
            if data["inventory"]["繪圖券"] <= 0:
                del data["inventory"]["繪圖券"]
            save_users(users)

        image_urls = self._collect_reference_images(ctx.message)
        wait_msg = await ctx.reply("🎬 小布正在送出動畫生成任務...", mention_author=False)
        try:
            result = await self._call_video_api(prompt, image_urls)
            if result.startswith("http"):
                await wait_msg.edit(content=f"🎬 動畫生成完成：\n{result}")
            else:
                await wait_msg.edit(content=f"🎬 {result}")
        except Exception as exc:
            await wait_msg.edit(content=f"❌ 動畫生成失敗：`{exc}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(VideoGeneration(bot))
