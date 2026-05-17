from __future__ import annotations

from datetime import datetime
from typing import Any

import discord
from discord.ext import commands, tasks

from utils import load_config, save_config

WEEKDAY_MAP = {
    "mon": 0, "monday": 0, "一": 0, "週一": 0, "星期一": 0,
    "tue": 1, "tuesday": 1, "二": 1, "週二": 1, "星期二": 1,
    "wed": 2, "wednesday": 2, "三": 2, "週三": 2, "星期三": 2,
    "thu": 3, "thursday": 3, "四": 3, "週四": 3, "星期四": 3,
    "fri": 4, "friday": 4, "五": 4, "週五": 4, "星期五": 4,
    "sat": 5, "saturday": 5, "六": 5, "週六": 5, "星期六": 5,
    "sun": 6, "sunday": 6, "日": 6, "天": 6, "週日": 6, "星期日": 6,
}


def _is_admin(ctx: commands.Context) -> bool:
    return str(ctx.author.id) in load_config().get("admin_ids", [])


def _parse_days(raw: str) -> list[int]:
    raw = raw.strip().lower()
    if raw in {"daily", "每天", "每日"}:
        return list(range(7))
    days: list[int] = []
    for part in raw.replace("、", ",").replace("，", ",").split(","):
        part = part.strip()
        if part in WEEKDAY_MAP:
            days.append(WEEKDAY_MAP[part])
    return sorted(set(days))


def _format_days(days: list[int]) -> str:
    names = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    if set(days) == set(range(7)):
        return "每日"
    return "、".join(names[d] for d in days if 0 <= d <= 6)


class ActivityReminders(commands.Cog):
    """Discord 每日 / 每週活動提醒。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sent_marks: set[str] = set()
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        await self.bot.wait_until_ready()
        now = datetime.now()
        config = load_config()
        reminders: list[dict[str, Any]] = config.get("activity_reminders", []) or []
        for item in reminders:
            if not item.get("enabled", True):
                continue
            channel_id = str(item.get("channel_id", "")).strip()
            time_text = str(item.get("time", "")).strip()
            days = item.get("days", list(range(7)))
            if not channel_id or not time_text or now.weekday() not in days:
                continue
            try:
                hour, minute = [int(x) for x in time_text.split(":", 1)]
            except Exception:
                continue
            if now.hour != hour or now.minute != minute:
                continue
            mark = f"{now.date()}:{channel_id}:{item.get('name','')}:{time_text}"
            if mark in self.sent_marks:
                continue
            self.sent_marks.add(mark)
            self.sent_marks = set(list(self.sent_marks)[-500:])
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                continue
            title = item.get("name", "活動提醒")
            message = item.get("message", "活動時間到了！")
            mention = item.get("mention", "")
            embed = discord.Embed(title=f"⏰ {title}", description=message, color=0xFACC15)
            embed.set_footer(text=f"提醒排程：{_format_days(days)} {time_text}")
            await channel.send(content=mention or None, embed=embed)

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    @commands.command(name="新增提醒", aliases=["活動提醒", "addreminder"])
    async def add_reminder(self, ctx: commands.Context, time_text: str, days: str, *, message: str):
        if not _is_admin(ctx):
            return await ctx.reply("❌ 只有 GM 可以新增活動提醒。", mention_author=False)
        parsed_days = _parse_days(days)
        if not parsed_days:
            return await ctx.reply("❌ 星期格式錯誤。例：`每日`、`週一,週三,週五`、`mon,wed,fri`。", mention_author=False)
        if ":" not in time_text:
            return await ctx.reply("❌ 時間格式錯誤。例：`20:00`。", mention_author=False)
        config = load_config()
        reminders = config.get("activity_reminders", []) or []
        reminders.append({
            "enabled": True,
            "name": message[:30],
            "channel_id": str(ctx.channel.id),
            "time": time_text,
            "days": parsed_days,
            "message": message,
            "mention": "",
        })
        config["activity_reminders"] = reminders
        save_config(config)
        await ctx.reply(f"✅ 已新增提醒：{_format_days(parsed_days)} {time_text}｜{message}", mention_author=False)

    @commands.command(name="提醒列表", aliases=["活動列表", "listreminders"])
    async def list_reminders(self, ctx: commands.Context):
        reminders = load_config().get("activity_reminders", []) or []
        if not reminders:
            return await ctx.reply("目前沒有活動提醒。", mention_author=False)
        lines = []
        for idx, item in enumerate(reminders, start=1):
            state = "✅" if item.get("enabled", True) else "⛔"
            lines.append(f"`{idx}` {state} {_format_days(item.get('days', []))} {item.get('time')}｜{item.get('message')}")
        await ctx.reply("\n".join(lines)[:1900], mention_author=False)

    @commands.command(name="刪除提醒", aliases=["delreminder", "移除提醒"])
    async def delete_reminder(self, ctx: commands.Context, index: int):
        if not _is_admin(ctx):
            return await ctx.reply("❌ 只有 GM 可以刪除活動提醒。", mention_author=False)
        config = load_config()
        reminders = config.get("activity_reminders", []) or []
        if index < 1 or index > len(reminders):
            return await ctx.reply("❌ 找不到這個提醒編號。", mention_author=False)
        removed = reminders.pop(index - 1)
        config["activity_reminders"] = reminders
        save_config(config)
        await ctx.reply(f"✅ 已刪除提醒：{removed.get('message')}", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityReminders(bot))
