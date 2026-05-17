"""
NSHBOT Discord entrypoint.

新版重點：
- Discord Token 改用環境變數，避免把密鑰寫進 GitHub。
- 自動載入 cogs 內所有功能模組，保留舊版功能。
- 提供較清楚的啟動日誌與錯誤提示。
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv 是選配
    load_dotenv = None

from utils import load_config

ROOT_DIR = Path(__file__).resolve().parent
COGS_DIR = ROOT_DIR / "cogs"

if load_dotenv:
    load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("NSHBOT")


def get_prefix(bot: commands.Bot, message: discord.Message):
    config = load_config()
    prefix = os.getenv("COMMAND_PREFIX") or config.get("command_prefix") or "!"
    return commands.when_mentioned_or(prefix)(bot, message)


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    intents.reactions = True

    bot = commands.Bot(
        command_prefix=get_prefix,
        intents=intents,
        help_command=None,
        case_insensitive=False,
    )

    # 舊版 Roleplay/AIChat 會讀取 active_rooms；先初始化可避免載入順序問題。
    bot.active_rooms = {}

    return bot


bot = build_bot()


@bot.event
async def on_ready():
    logger.info("=================================")
    logger.info("✅ 成功登入為 %s / ID=%s", bot.user, bot.user.id if bot.user else "unknown")
    logger.info("✅ 已連線伺服器數：%s", len(bot.guilds))
    logger.info("=================================")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CommandOnCooldown):
        try:
            await ctx.reply(f"⏳ 冷卻中，請等待 {int(error.retry_after)} 秒後再試。", delete_after=15, mention_author=False)
        except Exception:
            pass
        return
    if isinstance(error, commands.MissingRequiredArgument):
        try:
            await ctx.reply(f"❌ 指令參數不足：`{ctx.prefix}{ctx.command} ...`", delete_after=15, mention_author=False)
        except Exception:
            pass
        return

    logger.exception("指令執行失敗：%s", error)
    try:
        await ctx.reply(f"❌ 指令執行時發生錯誤：`{error}`", delete_after=20, mention_author=False)
    except Exception:
        pass


async def load_extensions() -> None:
    if not COGS_DIR.exists():
        raise RuntimeError("找不到 cogs 資料夾，無法載入功能模組。")

    loaded = 0
    for file_path in sorted(COGS_DIR.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        extension_name = f"cogs.{file_path.stem}"
        try:
            await bot.load_extension(extension_name)
            loaded += 1
            logger.info("📦 模組載入成功：%s", extension_name)
        except Exception:
            logger.exception("❌ 模組載入失敗：%s", extension_name)

    logger.info("✅ Cog 載入完成，共 %s 個模組。", loaded)


def resolve_token() -> str:
    config = load_config()
    token = (
        os.getenv("DISCORD_BOT_TOKEN")
        or os.getenv("DISCORD_TOKEN")
        or config.get("discord_token")
        or config.get("bot_token")
        or ""
    ).strip()

    if not token or token in {"Discord Bot Token", "YOUR_DISCORD_BOT_TOKEN", "貼上你的DiscordBotToken"}:
        raise RuntimeError(
            "找不到 Discord Bot Token。請建立 .env 並設定 DISCORD_BOT_TOKEN，"
            "或在 config.json 設定 discord_token。"
        )
    return token


async def main() -> None:
    token = resolve_token()
    async with bot:
        await load_extensions()
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，Bot 已停止。")
