import discord
from discord.ext import commands
from datetime import datetime
import asyncio
from utils import load_users, save_users, get_user_data, load_config

config_data = load_config()

# ==========================================
# 📦 私密包裹黑科技：讓背包變成隱藏訊息
# ==========================================
class SecretBackpackWrapperView(discord.ui.View):
    def __init__(self, author_id, data, pity_remaining, daily_earned, daily_limit, bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.data = data
        self.pity_remaining = pity_remaining
        self.daily_earned = daily_earned
        self.daily_limit = daily_limit
        self.bot = bot

    @discord.ui.button(label="📦 私密查看行囊", style=discord.ButtonStyle.primary)
    async def open_secret(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這是別人的背包，請不要偷看！", ephemeral=True)
        
        msg = f"🎒 **{interaction.user.name}** 的行囊：\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += f"💰 **銅幣總量**：{self.data['coins']}\n"
        if self.daily_earned >= self.daily_limit:
            msg += f"💬 **今日收益**：{self.daily_earned} / {self.daily_limit} (已達今日上限 🛑)\n"
        else:
            msg += f"💬 **今日收益**：{self.daily_earned} / {self.daily_limit} (聊天獲取)\n"
        msg += f"🔮 **天賞保底**：再抽 {self.pity_remaining} 次必得天賞\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        has_items = False
        for item, qty in self.data["inventory"].items():
            if qty > 0: 
                msg += f"📦 **{item}** x {qty}\n"
                has_items = True
                
        if not has_items:
            msg += "🪹 背包空空如也！\n"
            
        msg += "\n*(💡 提示：此為隱藏訊息，關閉 Discord 或重整後會自動消失)*"
            
        from cogs.item_use import BackpackUseView
        view = BackpackUseView(self.author_id, self.data["inventory"], self.bot)
        
        await interaction.response.send_message(msg, view=view if len(view.children) > 0 else None, ephemeral=True)
        try: await interaction.message.delete()
        except: pass

# ==========================================
# 📦 私密包裹黑科技：讓幫助菜單變成隱藏訊息
# ==========================================
class SecretHelpWrapperView(discord.ui.View):
    def __init__(self, author_id, embeds):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.embeds = embeds

    @discord.ui.button(label="📖 私密查看全功能指南", style=discord.ButtonStyle.primary, emoji="📦")
    async def open_secret(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這是專屬包裹，請自己輸入 `!幫助` 索取一份喔！", ephemeral=True)
        
        await interaction.response.send_message(embeds=self.embeds, ephemeral=True)
        try: await interaction.message.delete()
        except: pass


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==========================================
    # 🌟 新增：每日聊天收益監聽器 (群友對話自動給錢)
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if message.content.startswith('!'): return
        if message.content.startswith('！'): return

        users = load_users()
        data = get_user_data(message.author.id, users)
        config = load_config()

        if config.get("enable_economy", True):
            daily_limit = config.get("coin_daily_limit", 500)
            coin_per_msg = config.get("coin_per_message", 5)
            
            if data["daily_coins_earned"] < daily_limit:
                add_amount = min(coin_per_msg, daily_limit - data["daily_coins_earned"])
                data["daily_coins_earned"] += add_amount
                data["coins"] += add_amount
                save_users(users)


    # ==========================================
    # 🎒 背包系統 (私密包裹黑科技版)
    # ==========================================
    @commands.command(name=config_data.get('cmd_backpack', '背包'))
    async def backpack(self, ctx):
        try: await ctx.message.delete()
        except: pass
        
        config = load_config()
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        
        pity_remaining = config.get('gacha_pity_count', 180) - data.get('pity_count', 0)
        if pity_remaining < 0: pity_remaining = 0

        daily_earned = data.get('daily_coins_earned', 0)
        daily_limit = config.get('coin_daily_limit', 500)
            
        wrapper_view = SecretBackpackWrapperView(ctx.author.id, data, pity_remaining, daily_earned, daily_limit, self.bot)
        await ctx.send(f"{ctx.author.mention} 📦 **[專屬包裹]** 小布已經把您的行囊打包好送來了，請點擊按鈕私密開啟！\n*(🧹 此包裹將於 30 秒後自動銷毀)*", view=wrapper_view, delete_after=30.0)


    # ==========================================
    # 🌟 每日簽到系統
    # ==========================================
    @commands.command(name=config_data.get('cmd_sign', '簽到'))
    async def daily_sign(self, ctx):
        try: await ctx.message.delete()
        except: pass
        
        config = load_config()
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        today = str(datetime.now().date())
        
        if data.get("last_sign_in") == today:
            return await ctx.send(f"📅 {ctx.author.mention} 你今天已經簽到過囉，明天再來吧！", delete_after=15.0)
            
        sign_coins = config.get('daily_sign_coins', 500)
        data["last_sign_in"] = today
        data["coins"] += sign_coins
        
        save_users(users)
        await ctx.send(f"✅ {ctx.author.mention} **簽到成功！** 獲得 **{sign_coins}** 銅幣！\n*(🧹 此訊息將於 1 分鐘後自動清理)*", delete_after=60.0)


    # ==========================================
    # 📖 系統幫助指令 (全面升級版)
    # ==========================================
    @commands.command(name=config_data.get('cmd_help', '幫助'), aliases=['功能', '指令', '說明', '菜單'])
    async def help_menu(self, ctx):
        try: await ctx.message.delete()
        except: pass
        
        config = load_config()
        bot_name = config.get("bot_name", "小布")
        
        # --- 頁面一：經濟與對話 ---
        embed1 = discord.Embed(
            title=f"📜 {bot_name} 功能指南 (1/3) - 經濟與對話", 
            description="萬事屋已全面升級為「點擊式 UI 介面」，告別繁瑣的打字！", 
            color=0x5865F2
        )
        embed1.add_field(name="💬 聊天與互動", 
                         value=f"🔸 `@機器人 <文字>` - 進行智慧對話 (會帶表情喔！)\n"
                               f"🔸 `!領取繪圖券` - 新手必備，免費領取 10 張畫布！\n"
                               f"🔸 `!自我介紹` - 看看 {bot_name} 的可愛登場動畫\n"
                               f"🔸 `!忘記` - 清除當前頻道的對話記憶，重新開始", 
                         inline=False)
        embed1.add_field(name="💰 財富與道具", 
                         value=f"🔸 `!{config.get('cmd_sign', '簽到')}` - 每日領取銅幣薪水\n"
                               f"🔸 `!{config.get('cmd_backpack', '背包')}` - 🌟 查看行囊餘額，並可**直接點擊使用道具**\n"
                               f"🔸 `!{config.get('cmd_shop', '商店')}` - 呼叫互動商行買賣，每週四開啟【黑市商人】\n"
                               f"🔸 `!圖鑑` - 查看所有惡搞道具的超瞎效果說明", 
                         inline=False)
        embed1.add_field(name="🎰 抽獎與運勢", 
                         value=f"🔸 `!{config.get('cmd_gacha', '神鑿')}` - 消耗神鑿抽獎，看看能不能出天賞！\n"
                               f"🔸 `!{config.get('cmd_divination', '機運')}` - 每日運勢測吉凶 (大富翁隨機事件)", 
                         inline=False)

        # --- 頁面二：繪圖與深夜包廂 ---
        embed2 = discord.Embed(
            title=f"📜 {bot_name} 功能指南 (2/3) - 繪圖與角色扮演", 
            color=0xffb6c1
        )
        embed2.add_field(name="🎨 AI 魔法繪圖大師", 
                         value=f"🔸 `!畫 <提示詞>` - 消耗繪圖券生成高畫質圖片 (支援圖生圖)\n"
                               f"🔸 `!畫` - (不加文字) 呼叫「智能模板選擇庫」一鍵套用畫風\n"
                               f"🔸 `!儲存模板 <名稱> <提示詞>` - 儲存神級畫風設定\n"
                               f"🔸 `!刪除模板 <名稱>` - 丟棄不需要的模板", 
                         inline=False)
        embed2.add_field(name="🔞 深夜包廂與伴侶 (需大人的證明)", 
                         value=f"*(需於 23:00~05:00 間使用)*\n"
                               f"🔸 `!伴侶設定` - 自訂 AI 伴侶名稱、專屬稱呼與隱藏人格\n"
                               f"🔸 `!深夜包廂` - 創建絕對私密的兩人世界 (包廂內對話**免標記 @**)\n"
                               f"🔸 `!進包廂 <密碼>` - 輸入 4 位數密碼加入別人的包廂", 
                         inline=False)
        
        # --- 頁面三：實用工具與特權 ---
        embed3 = discord.Embed(
            title=f"📜 {bot_name} 功能指南 (3/3) - 實用工具", 
            color=0x4ade80
        )
        embed3.add_field(name="🚨 生活與情報", 
                         value=f"🔸 `!最新地震` (或 `!eew`) - 獲取中央氣象署最新地震報告\n"
                               f"🔸 *(自動功能)* - 官網公告與 YouTube 影片自動推播點評", 
                         inline=False)
        embed3.add_field(name="👑 GM 專屬特權指令", 
                         value=f"🔸 `!切換大腦` - 在 Grok 與 LM Studio (本地模型) 間切換\n"
                               f"🔸 `!大腦測試` - 測試本地端 LM Studio 是否連線正常\n"
                               f"🔸 `!gm畫 <提示詞>` - 免扣券無限繪圖，並解鎖 4K 畫質\n"
                               f"🔸 `!緊急關機` - 強制系統斷線休眠", 
                         inline=False)
        embed3.set_footer(text="💡 提示：此為隱藏說明書，關閉 Discord 後會自動消失。")
        
        wrapper_view = SecretHelpWrapperView(ctx.author.id, [embed1, embed2, embed3])
        await ctx.send(f"{ctx.author.mention} 📦 **[系統包裹]** 完整功能指南已送達，請點擊按鈕私密開啟！\n*(🧹 此包裹將於 30 秒後自動銷毀)*", view=wrapper_view, delete_after=30.0)

async def setup(bot):
    await bot.add_cog(Economy(bot))