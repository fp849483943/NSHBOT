import discord
from discord.ext import commands
import os

# ==========================================
# 📖 系統預設道具圖鑑資料庫
# ==========================================
ITEM_DEX = {
    "天賞石": {
        "emoji": "💎",
        "color": 0x38bdf8,
        "local_icon": "stone.png", 
        "description": "**【極致稀有的天命神物】**\n散發著令人目眩的璀璨光芒，據說只有被命運眷顧的歐皇才能獲得。\n\n🔹 **使用效果**：\n可選擇 **「舔石頭」** 嘲諷全服；或使用 **「洪荒之力按壓」** 將其引爆，化作漫天金雨隨機派發巨額銅幣給在場群友！\n\n🔹 **商會回收價**：`20,000` 銅幣"
    },
    "大當家的黑絲襪": {
        "emoji": "🖤",
        "color": 0x2b2d31,
        "local_icon": "socks.png", 
        "description": "**【大當家私藏的極品原味】**\n散發著淡淡的幽香，是公會裡無數紳士夢寐以求的迷因神物。\n\n🔹 **使用效果**：\n使用後，小布會替您潛入大當家的衣櫃，竊取並發送一張**極品高畫質的黑絲美腿照**供大俠欣賞。\n\n🔹 **商會回收價**：`5,000` 銅幣"
    },
    "足球": {
        "emoji": "⚽",
        "color": 0x4ade80,
        "local_icon": "football.png",
        "description": "**【充滿活力的運動用品】**\n看著它，就有一種想大力踢飛別人的衝動。\n\n🔹 **使用效果**：\n可指定一名公會成員用力踢去！\n結果將會隨機判定：可能被對方**帥氣接住**、直接**命中臉部**，甚至讓對方**跟著球飛出地球**！"
    },
    "審判小錘錘": {
        "emoji": "⚖️",
        "color": 0xfacc15,
        "local_icon": "hammer.png",
        "description": "**【絕對正義的法庭之槌】**\n賦予你審判群友的無上權力。\n\n🔹 **使用效果**：\n指定一名對象並寫下罪狀，立刻展開**「誅伏賜死」領域**！全服群友將直接進行公審投票，若有罪票過半，犯人將遭到 **禁言 3 分鐘** 的天罰！"
    },
    "嗷嗷交配證": {
        "emoji": "💦",
        "color": 0xffb6c1,
        "local_icon": "ticket.png",
        "description": "**【神秘的特種行業票券】**\n閃爍著奇異的光澤，背面印著嗷嗷的簽名。\n\n🔹 **使用效果**：\n無情發動全服廣播！強制標記呼叫「嗷嗷」出來接客配種，是炒熱群組氣氛（與迫害嗷嗷）的最佳利器。"
    },
    "樁·小花": {
        "emoji": "🌸",
        "color": 0xd8b4e2,
        "local_icon": "dummy.png",
        "description": "**【普通的練功木樁】**\n江湖人士最愛拿來測試傷害的木頭疙瘩。\n\n🔹 **使用效果**：\n在聊天室裡放出一具堅固的木樁，並開啟 **60 秒集火挑戰**！全服群友皆可點擊參與攻擊，看看大家能不能在限時內打爛它！"
    },
    "大人的證明": {
        "emoji": "💳",
        "color": 0x000000,
        "local_icon": "blackcard.png",
        "description": "**【頂級黑卡・VIP 專屬憑證】**\n黑市裡的傳說級身分證，代表著你已經是個成熟的大人了。\n\n🔹 **被動效果**：\n只要將其放在背包中，即可於深夜時段自動解鎖小布的 **「成人模式」**，並獲得開啟 **「深夜私密包廂」** 的特權。"
    },
    "望月的襪子": {
        "emoji": "🧦",
        "color": 0xd1d5db,
        "local_icon": "moon_socks.png",
        "description": "**【象徵自由的恩賜】**\n相傳只要收到這隻襪子，就能獲得真正的自由（雖然上面可能有腳臭味）。\n\n🔹 **使用效果**：\n選擇一名用戶並將這隻襪子贈送給他，宣告他正式獲得自由！這會無情地消耗掉望月的一隻襪子。\n\n🔹 **商會回收價**：`100` 銅幣"
    }
}

# ==========================================
# 🔍 互動選單與 60 秒自動刪除邏輯
# ==========================================
class DexSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for item_name, data in ITEM_DEX.items():
            options.append(discord.SelectOption(label=item_name, emoji=data["emoji"]))
        
        super().__init__(placeholder="👇 點擊這裡選擇想查看的道具...", min_values=1, max_values=1, options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.author_id:
            return await interaction.response.send_message("❌ 這不是您的圖鑑喔！想看的話請自己輸入 `!圖鑑` 查詢。", ephemeral=True)

        item_name = self.values[0]
        data = ITEM_DEX[item_name]
        
        embed = discord.Embed(
            title=f"{data['emoji']} 道具圖鑑：{item_name}",
            description=data["description"],
            color=data["color"]
        )
        embed.set_footer(text="萬事屋百寶圖鑑 | 60 秒無操作將自動銷毀")

        # 讀取本地 Icon 圖片
        icon_filename = data.get("local_icon", "")
        file_path = os.path.join("assets", "icons", icon_filename) if icon_filename else ""
        if os.path.exists(file_path):
            file = discord.File(file_path, filename="icon.png")
            embed.set_thumbnail(url="attachment://icon.png")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self.view)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self.view)

class DexView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=60.0)
        self.author_id = author_id
        self.message = None
        self.add_item(DexSelect())

    async def on_timeout(self):
        if self.message:
            try: 
                await self.message.delete()
            except Exception:
                pass

# ==========================================
# 🔧 主指令模組
# ==========================================
class ItemDex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="圖鑑", aliases=["道具說明", "物品說明", "百科"])
    async def show_dex(self, ctx):
        try: 
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="📚 萬事屋百寶圖鑑",
            description=f"{ctx.author.mention} 大俠，請透過下方選單選擇想查看的道具！\n*(此圖鑑為您專屬鎖定，若 60 秒未操作將自動銷毀)*",
            color=0x5865F2
        )
        
        main_icon = os.path.join("assets", "icons", "dex_main.png")
        view = DexView(ctx.author.id)
        
        if os.path.exists(main_icon):
            file = discord.File(main_icon, filename="dex_main.png")
            embed.set_thumbnail(url="attachment://dex_main.png")
            msg = await ctx.send(content=ctx.author.mention, embed=embed, file=file, view=view)
        else:
            msg = await ctx.send(content=ctx.author.mention, embed=embed, view=view)
            
        view.message = msg

async def setup(bot):
    await bot.add_cog(ItemDex(bot))