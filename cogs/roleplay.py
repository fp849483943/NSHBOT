import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime
from utils import load_users, save_users, get_user_data, load_config

# ==========================================
# 🔞 包廂控制按鈕 (銷毀房間)
# ==========================================
class RoomView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💥 銷毀包廂", style=discord.ButtonStyle.danger, emoji="💥")
    async def destroy_room(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("💥 包廂將在 5 秒後銷毀...", ephemeral=False)
        await asyncio.sleep(5)
        try:
            # 刪除活躍房間密碼紀錄
            for pwd, cid in list(interaction.client.active_rooms.items()):
                if cid == interaction.channel.id:
                    del interaction.client.active_rooms[pwd]
            await interaction.channel.delete()
        except:
            pass

# ==========================================
# ⚙️ 伴侶設定彈出表單 (Modal)
# ==========================================
class SetupModal(discord.ui.Modal):
    def __init__(self, author_id):
        super().__init__(title="伴侶專屬設定")
        self.author_id = author_id

        self.bot_name = discord.ui.TextInput(
            label="伴侶名稱 (如：小布)",
            default="小布",
            required=False,
            max_length=20
        )
        self.called_name = discord.ui.TextInput(
            label="對您的稱呼 (如：主人、大俠)",
            default="主人",
            required=False,
            max_length=20
        )
        self.persona = discord.ui.TextInput(
            label="隱藏人格設定 (選填)",
            style=discord.TextStyle.paragraph,
            placeholder="例如：傲嬌、病嬌、溫柔體貼...",
            required=False,
            max_length=200
        )
        
        self.add_item(self.bot_name)
        self.add_item(self.called_name)
        self.add_item(self.persona)

    async def on_submit(self, interaction: discord.Interaction):
        users = load_users()
        data = get_user_data(self.author_id, users)
        
        data["bot_custom_name"] = self.bot_name.value.strip() or "小布"
        data["called_name"] = self.called_name.value.strip() or "主人"
        data["bot_persona"] = self.persona.value.strip()
        
        save_users(users)
        await interaction.response.send_message(f"✅ 設定完成！以後 **{data['bot_custom_name']}** 會稱呼您為 **{data['called_name']}**！", ephemeral=True)

# ==========================================
# ⚙️ 伴侶設定面板 (View)
# ==========================================
class SetupView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=60)
        self.author_id = author_id

    @discord.ui.button(label="⚙️ 開啟設定表單", style=discord.ButtonStyle.primary)
    async def open_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 您不能修改別人的設定喔！", ephemeral=True)
        await interaction.response.send_modal(SetupModal(self.author_id))


# ==========================================
# 🎭 角色扮演核心模組
# ==========================================
class Roleplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, 'active_rooms'):
            self.bot.active_rooms = {}

    def has_adult_access(self, user_data):
        config = load_config()
        if not config.get('enable_late_night_mode', True): 
            return False
            
        has_black_card = user_data["inventory"].get("大人的證明", 0) > 0
        if not has_black_card: 
            return False

        start_h = int(config.get('late_night_start', 23))
        end_h = int(config.get('late_night_end', 5))
        current_h = datetime.now().hour
        
        if start_h > end_h: 
            return current_h >= start_h or current_h < end_h
        else: 
            return start_h <= current_h < end_h

    @commands.command(name="深夜包廂", aliases=["開房間", "專屬房間"])
    async def create_private_room(self, ctx):
        try: await ctx.message.delete(delay=60.0)
        except: pass
        
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        
        if not self.has_adult_access(data):
            return await ctx.reply("❌ 噓...現在還不是時候。 (需要處於設定的深夜時段，且持有「大人的證明💳」才可開啟私密包廂喔！)", delete_after=15.0)

        guild = ctx.guild
        if not guild: 
            return await ctx.reply("❌ 此指令只能在伺服器中使用。", delete_after=15.0)
        
        room_name = f"🔞私密包廂-{ctx.author.name}"
        
        # 設定頻道權限：預設隱藏，只對開啟者與機器人開放
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        try:
            channel = await guild.create_text_channel(room_name, overwrites=overwrites, nsfw=True)
            room_password = str(random.randint(1000, 9999))
            self.bot.active_rooms[room_password] = channel.id
            
            bot_name = data.get("bot_custom_name") or "小布"
            call_name = data.get("called_name") or "主人"
            
            await channel.send(
                f"💋 {ctx.author.mention}，歡迎來到您的專屬私密包廂...\n"
                f"*(這個空間已被結界封鎖，任何人皆無法窺視。)*\n"
                f"🔑 **本包廂專屬密碼：`{room_password}`**\n"
                f"*(若想邀請朋友同樂，請他在外面大廳輸入 `!進包廂 {room_password}`)*\n\n"
                f"*(我是您的伴侶 **{bot_name}**，請盡情吩咐 {call_name}。)*\n"
                f"*(結束後請點擊下方按鈕銷毀房間)*", 
                view=RoomView()
            )
            await ctx.reply(f"✅ 已為您準備好專屬包廂，請進：{channel.mention}", delete_after=60.0)
        except discord.Forbidden:
            await ctx.reply("❌ 小布沒有「管理頻道」的權限，無法為您創建包廂！請通知伺服器主。", delete_after=15.0)

    @commands.command(name="進包廂", aliases=["進入房間", "進房", "加入包廂"])
    async def join_room(self, ctx, password: str = ""):
        try: await ctx.message.delete(delay=60.0)
        except: pass
        
        if not password: 
            return await ctx.reply("❌ 請輸入密碼！格式：`!進包廂 <4位數密碼>`", delete_after=15.0)
            
        if not hasattr(self.bot, 'active_rooms') or password not in self.bot.active_rooms:
            return await ctx.reply("❌ 密碼錯誤，或是該包廂已經結束銷毀了！", delete_after=15.0)
            
        channel_id = self.bot.active_rooms[password]
        channel = ctx.guild.get_channel(channel_id)
        
        if not channel:
            del self.bot.active_rooms[password]
            return await ctx.reply("❌ 該包廂似乎已經不見了。", delete_after=15.0)
            
        # 賦予使用者觀看頻道權限
        await channel.set_permissions(ctx.author, view_channel=True, read_messages=True, send_messages=True)
        await ctx.reply(f"✅ 密碼正確！已為您悄悄打開大門：{channel.mention}", delete_after=60.0)
        await channel.send(f"👋 貴賓 {ctx.author.mention} 輸入了正確的密碼，悄悄溜進了包廂...")

    @commands.command(name="伴侶設定", aliases=["專屬設定", "我的設定", "設定伴侶", "設定人格"])
    async def companion_setup(self, ctx):
        try: await ctx.message.delete(delay=60.0)
        except: pass
        await ctx.reply("⚙️ 請點擊下方按鈕來開啟您的「專屬伴侶設定表」：\n*(🧹 此設定畫面將於 1 分鐘後自動清理)*", view=SetupView(ctx.author.id), delete_after=60.0)

    # ==========================================
    # 👑 GM 專屬緊急斷電休眠指令
    # ==========================================
    @commands.command(name="緊急關機", aliases=["shutdown", "關機", "強制休眠", "緊急休眠"])
    async def emergency_shutdown(self, ctx):
        try: await ctx.message.delete(delay=10.0)
        except: pass
        
        config = load_config()
        # 1. 安全攔截：非設定檔內指定的 GM，無權使用此指令
        if str(ctx.author.id) not in config.get('admin_ids', []):
            return await ctx.reply("❌ 警告：你不是 GM，沒有權限強制關閉系統！", delete_after=15.0)

        # 2. 斷電廣播
        await ctx.reply("⚠️ **【系統緊急廣播】**\n接收到 GM 的最高優先級指令。小布即將切斷電源進入強制休眠模式，各位大俠晚安... 💤")
        
        # 3. 延遲 2 秒確保訊息成功送出到 Discord 頻道後，安全結束連線
        await asyncio.sleep(2)
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(Roleplay(bot))