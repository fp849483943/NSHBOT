from __future__ import annotations

import asyncio
import os
from typing import Any

import discord
import requests
from discord.ext import commands

from utils import load_config


def _env_or_config(config: dict[str, Any], env_name: str, config_name: str, default: str = "") -> str:
    return (os.getenv(env_name) or config.get(config_name) or default or "").strip()


def _extract_text(payload: dict[str, Any]) -> str:
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
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in content).strip()
    return ""


def _collect_image_urls(message: discord.Message) -> list[str]:
    urls: list[str] = []
    for attachment in message.attachments:
        content_type = attachment.content_type or ""
        if content_type.startswith("image/") or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            urls.append(attachment.url)
    for embed in message.embeds:
        if embed.image and embed.image.url:
            urls.append(embed.image.url)
        if embed.thumbnail and embed.thumbnail.url:
            urls.append(embed.thumbnail.url)
    return list(dict.fromkeys(urls))


class VisionTools(commands.Cog):
    """Grok 圖片識別與圖片問答。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resolve_image_urls(self, ctx: commands.Context) -> list[str]:
        urls = _collect_image_urls(ctx.message)
        if urls:
            return urls
        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                ref = ctx.message.reference.resolved
                if ref is None or isinstance(ref, discord.DeletedReferencedMessage):
                    ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if isinstance(ref, discord.Message):
                    urls.extend(_collect_image_urls(ref))
            except Exception:
                pass
        return list(dict.fromkeys(urls))

    async def call_grok_vision(self, prompt: str, image_urls: list[str]) -> str:
        config = load_config()
        api_key = _env_or_config(config, "XAI_API_KEY", "grok_api_key")
        if not api_key:
            raise RuntimeError("尚未設定 XAI_API_KEY / Grok API Key。")

        api_url = _env_or_config(config, "XAI_API_URL_TEXT", "grok_api_url_text", "https://api.x.ai/v1/responses")
        model = _env_or_config(config, "XAI_VISION_MODEL", "grok_vision_model", config.get("grok_model", "grok-4.3"))

        content: list[dict[str, str]] = [{"type": "input_text", "text": prompt or "請詳細描述這張圖片，並指出重點。"}]
        for url in image_urls[:4]:
            content.append({"type": "input_image", "image_url": url})

        payload = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": "你是 Discord 圖片識別助手。請用繁體中文回答，能辨識畫面內容、文字、構圖、角色特徵與可疑細節。不要憑空捏造看不到的內容。",
                },
                {"role": "user", "content": content},
            ],
        }

        response = await asyncio.to_thread(
            requests.post,
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Grok Vision HTTP {response.status_code}: {response.text[:500]}")
        text = _extract_text(response.json())
        return text or "模型沒有回傳可用文字。"

    @commands.command(name="看圖", aliases=["識圖", "圖片分析", "問圖", "vision"])
    async def vision(self, ctx: commands.Context, *, prompt: str = ""):
        image_urls = await self._resolve_image_urls(ctx)
        if not image_urls:
            return await ctx.reply(
                "❌ 請在訊息附上一張圖片，或回覆一則有圖片的訊息再輸入 `!看圖 你想問的問題`。",
                mention_author=False,
            )
        wait_msg = await ctx.reply("👀 小布正在用 Grok 讀圖，請稍候...", mention_author=False)
        try:
            async with ctx.typing():
                answer = await self.call_grok_vision(prompt, image_urls)
            await wait_msg.edit(content=answer[:1900])
        except Exception as exc:
            await wait_msg.edit(content=f"❌ 圖片識別失敗：`{exc}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(VisionTools(bot))
