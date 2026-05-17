import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print('=================================')
    print(f'✅ 成功登入為 {bot.user}')
    print('=================================')

# 自動載入 cogs 資料夾裡的所有模組
async def load_extensions():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"📦 模組載入成功：{filename}")
            except Exception as e:
                print(f"❌ 模組載入失敗 {filename}: {e}")

async def main():
    async with bot:
        await load_extensions()
        # ⚠️ 請在下方換上你的 Discord Bot Token
        await bot.start('Discord Bot Token')

if __name__ == '__main__':
    asyncio.run(main())