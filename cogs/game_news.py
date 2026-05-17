from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import discord
import feedparser
import requests
from bs4 import BeautifulSoup
from discord.ext import commands, tasks

from utils import load_config


def _env_or_config(config: dict[str, Any], env_name: str, config_name: str, default: str = "") -> str:
    return (os.getenv(env_name) or config.get(config_name) or default or "").strip()


def _strip_html(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def _entry_to_embed(entry: Any, title_prefix: str = "🎮 遊戲資訊") -> discord.Embed:
    title = getattr(entry, "title", "未命名公告")
    link = getattr(entry, "link", "")
    summary = _strip_html(getattr(entry, "summary", ""))[:800]
    published = getattr(entry, "published", "") or getattr(entry, "updated", "")
    embed = discord.Embed(title=f"{title_prefix}｜{title}", description=summary or "無摘要", color=0x58A6FF, url=link or None)
    if published:
        embed.add_field(name="發布時間", value=published, inline=False)
    if link:
        embed.add_field(name="連結", value=link, inline=False)
    return embed


class GameNews(commands.Cog):
    """遊戲新資訊查詢與定時公告。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_seen_links: set[str] = set()
        self.news_loop.start()

    def cog_unload(self):
        self.news_loop.cancel()

    def _feed_urls(self) -> list[str]:
        config = load_config()
        raw = config.get("game_news_feeds", [])
        if isinstance(raw, str):
            urls = [x.strip() for x in raw.replace(",", "\n").splitlines() if x.strip()]
        elif isinstance(raw, list):
            urls = [str(x).strip() for x in raw if str(x).strip()]
        else:
            urls = []
        if not urls and config.get("rss_feed_url"):
            urls = [str(config.get("rss_feed_url")).strip()]
        return urls

    async def _fetch_feeds(self) -> list[Any]:
        entries: list[Any] = []
        for url in self._feed_urls()[:10]:
            parsed = await asyncio.to_thread(feedparser.parse, url)
            entries.extend(parsed.entries[:5])
        return entries

    async def _search_with_api(self, keyword: str) -> str:
        config = load_config()
        api_url = _env_or_config(config, "GAME_SEARCH_API_URL", "game_search_api_url")
        api_key = _env_or_config(config, "GAME_SEARCH_API_KEY", "game_search_api_key")
        if not api_url:
            return ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"query": keyword, "limit": 5}
        resp = await asyncio.to_thread(requests.post, api_url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Search API HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return str(data.get("answer") or data.get("result") or data)[:1800]

    @commands.command(name="遊戲資訊", aliases=["新資訊", "公告查詢", "查公告", "gameinfo"])
    async def game_info(self, ctx: commands.Context, *, keyword: str = ""):
        wait_msg = await ctx.reply("🔎 小布正在查詢遊戲資訊...", mention_author=False)
        try:
            api_answer = await self._search_with_api(keyword) if keyword else ""
            if api_answer:
                return await wait_msg.edit(content=api_answer)

            entries = await self._fetch_feeds()
            if keyword:
                key = keyword.lower()
                entries = [e for e in entries if key in getattr(e, "title", "").lower() or key in _strip_html(getattr(e, "summary", "")).lower()]
            if not entries:
                hint = "請先在 `config.json` 設定 `game_news_feeds`，或設定 `GAME_SEARCH_API_URL` 接搜尋服務。"
                return await wait_msg.edit(content=f"❌ 沒查到相關資訊。{hint}")
            await wait_msg.delete()
            for entry in entries[:3]:
                await ctx.send(embed=_entry_to_embed(entry))
        except Exception as exc:
            await wait_msg.edit(content=f"❌ 查詢失敗：`{exc}`")

    @tasks.loop(minutes=10)
    async def news_loop(self):
        await self.bot.wait_until_ready()
        config = load_config()
        if not config.get("enable_game_news_auto", False):
            return
        channel_id = str(config.get("game_news_channel_id", "")).strip()
        if not channel_id:
            return
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return
        try:
            entries = await self._fetch_feeds()
            for entry in reversed(entries[:5]):
                link = getattr(entry, "link", "") or getattr(entry, "id", "") or getattr(entry, "title", "")
                if not link or link in self.last_seen_links:
                    continue
                if len(self.last_seen_links) < 5:
                    self.last_seen_links.add(link)
                    continue
                self.last_seen_links.add(link)
                self.last_seen_links = set(list(self.last_seen_links)[-50:])
                await channel.send(embed=_entry_to_embed(entry, "📢 遊戲新公告"))
        except Exception:
            return

    @news_loop.before_loop
    async def before_news_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(GameNews(bot))
