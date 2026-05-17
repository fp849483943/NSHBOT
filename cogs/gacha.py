import discord
from discord.ext import commands
import random
from datetime import datetime
import asyncio
from utils import load_users, save_users, get_user_data, load_config

# ==========================================
# 🎲 每日機會與命運系統 (View)
# ==========================================
class ChanceFateView(discord.ui.View):
    # 新增 is_gm_test 參數，用來判斷是否需要繞過每日限制
    def __init__(self, author_id, is_gm_test=False):
        super().__init__(timeout=120.0)
        self.author_id = author_id
        self.is_gm_test = is_gm_test
        self.message = None

    async def process_event(self, interaction: discord.Interaction, choice_type: str):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這不是你的命運選擇喔！", ephemeral=True)

        users = load_users()
        data = get_user_data(self.author_id, users)
        today = str(datetime.now().date())

        # 🌟 如果不是 GM 測試模式，才需要檢查今天是否已經抽過
        if not self.is_gm_test and data["last_divination"] == today:
            return await interaction.response.send_message("❌ 你今天已經選擇過命運了，請明天再來！", ephemeral=True)

        # 🌟 定義 15種機會 + 15種命運 (包含機率觸發的「事件反轉」機制)
        events = {
            "機會": [
                {"text": "🤑 你在路邊撿到一個沉甸甸的錢袋！", "coins": 300, "twists": [{"prob": 0.2, "text": "打開一看，裡面還有一張大額銀票！", "coins": 200}, {"prob": 0.1, "text": "結果發現是別人的惡作劇，裡面裝的都是石頭...", "coins": -300}]},
                {"text": "📈 你投資的萬事屋股票今天大漲！", "coins": 500},
                {"text": "💨 走路太急，不小心撞翻了路邊小販的攤子，賠了點錢。", "coins": -150, "twists": [{"prob": 0.3, "text": "小販看你骨骼精奇，偷偷送了你一本武功秘笈 (被你拿去賣了廢紙)。", "coins": 50}]},
                {"text": "🎲 參與地下賭局，運氣不佳輸了一筆。", "coins": -300, "twists": [{"prob": 0.25, "text": "不過你抓到了莊家出老千，不僅拿回本金還倒賺了一筆！", "coins": 450}]},
                {"text": "🧹 幫忙打掃公會大廳，在大當家沙發底下撿到私房錢。", "coins": 200},
                {"text": "💸 錢包破了個洞，走著走著錢就掉光了...", "coins": -250, "twists": [{"prob": 0.4, "text": "幸好有好心的大俠撿到，還給了你一半！", "coins": 125}]},
                {"text": "🦅 走在路上被從天而降的鳥糞砸中... 去洗衣服花了不少錢。", "coins": -50},
                {"text": "🍎 幫忙郊外的果農採收蘋果，獲得了豐厚的報酬。", "coins": 150},
                {"text": "🐶 在巷口被惡犬追了三條街，跑得鞋底都磨破了...", "coins": -100},
                {"text": "🎯 參加廟會的射箭比賽，百發百中贏得了頭獎！", "coins": 400},
                {"text": "🍷 在酒館喝多了，不僅被坑了酒錢，還吐了一身。", "coins": -200, "twists": [{"prob": 0.2, "text": "醒來後發現口袋裡莫名其妙多了一位富商給的小費。", "coins": 250}]},
                {"text": "🎣 去河邊釣魚，意外釣到一個生鏽的寶箱！", "coins": 250, "twists": [{"prob": 0.3, "text": "滿心歡喜打開一看，裡面居然只有一堆發臭的淤泥...", "coins": -250}]},
                {"text": "🎭 戴上面具在街頭賣藝，大受圍觀群眾歡迎！", "coins": 350},
                {"text": "🐎 買了匹劣馬，沒跑兩步就罷工，只好賤價賣出。", "coins": -180},
                {"text": "💰 收到了一封來歷不明的匿名捐款。", "coins": 100}
            ],
            "命運": [
                {"text": "✨ 扶老奶奶過馬路，沒想到她竟然是隱世富豪，給了你一筆豐厚的獎賞！", "coins": 400},
                {"text": "⚔️ 路上遇到山賊打劫，只好破財消災...", "coins": -350, "twists": [{"prob": 0.3, "text": "你越想越氣，回頭把山賊揍了一頓，連本帶利搶了回來！", "coins": 500}]},
                {"text": "🍀 出門看見彩虹，今天運氣爆棚，走路都能撿到錢！", "coins": 250},
                {"text": "🌧️ 突然下起暴雨，為躲雨進了黑店，被狠宰了一頓。", "coins": -200},
                {"text": "👼 夢見神明指點，醒來後在床頭發現了一袋銅幣！", "coins": 350, "twists": [{"prob": 0.1, "text": "咬了一口才發現，居然是巧克力金幣...", "coins": -350}]},
                {"text": "👻 晚上走夜路遇到阿飄，嚇得把身上的錢都扔了...", "coins": -300, "twists": [{"prob": 0.35, "text": "天亮後你鼓起勇氣回去找，居然順利撿回了一大半！", "coins": 200}]},
                {"text": "🌟 走在路上突然頓悟了武學真理，順手幫路人解決了麻煩，獲得謝禮。", "coins": 150},
                {"text": "🔮 找算命仙算了一卦，結果是上上籤，還順手摸走了算命仙的錢袋(X)。", "coins": 200},
                {"text": "🐍 在野外不小心被毒蛇咬傷，花大錢買了解毒劑...", "coins": -280},
                {"text": "👑 意外救了微服出巡的皇室成員，獲得重賞！", "coins": 600, "twists": [{"prob": 0.15, "text": "結果發現是詐騙集團，錢都是假的，還被騙了手續費...", "coins": -700}]},
                {"text": "🌋 誤入火山口，雖然沒死但裝備都烤焦了。", "coins": -150},
                {"text": "📜 破解了古老的藏寶圖，挖出了一批珍貴的古董！", "coins": 450},
                {"text": "💔 遭到無良商人詐騙，買到了假的神兵利器。", "coins": -400, "twists": [{"prob": 0.25, "text": "沒想到這把假兵器居然是開啟神秘遺跡的鑰匙，你在裡面大賺一筆！", "coins": 600}]},
                {"text": "🌙 月圓之夜吸收了天地靈氣，真氣化作了實質的財富！", "coins": 300},
                {"text": "👺 惹怒了當地的地頭蛇，被狠狠敲詐了一筆保護費。", "coins": -220}
            ]
        }

        # 隨機抽取事件
        event = random.choice(events[choice_type])
        event_text = event["text"]
        coin_delta = event["coins"]

        # 🌟 判斷是否觸發「事件反轉 (Twist)」
        if "twists" in event:
            for twist in event["twists"]:
                if random.random() < twist["prob"]:
                    event_text += f"\n\n**【事件反轉】** {twist['text']}"
                    coin_delta += twist["coins"]
                    break # 觸發一個反轉就結束判斷
        
        # 🌟 更新玩家數據與防負債機制
        # 如果是 GM 測試，不寫入 last_divination，避免影響正常的每日限制
        if not self.is_gm_test:
            data["last_divination"] = today
            
        original_coins = data["coins"]
        data["coins"] += coin_delta
        if data["coins"] < 0: data["coins"] = 0 
        actual_delta = data["coins"] - original_coins
        
        save_users(users)

        color = 0x4ade80 if actual_delta > 0 else (0xf87171 if actual_delta < 0 else 0x9ca3af)
        sign = "+" if actual_delta > 0 else ""
        
        # 如果是 GM 測試，在標題加上提示
        title_prefix = "👑 [GM測試] " if self.is_gm_test else ""
        
        embed = discord.Embed(
            title=f"{title_prefix}🎭 命運的齒輪開始轉動... 你選擇了【{choice_type}】",
            description=f"**{event_text}**\n\n💰 銅幣變動：**{sign}{actual_delta}**\n🪙 當前餘額：**{data['coins']}**",
            color=color
        )
        embed.set_footer(text="*(🧹 此結果將於 1 分鐘後自動清理)*")

        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=self)
        
        async def auto_delete():
            await asyncio.sleep(60.0)
            try: await interaction.message.delete()
            except: pass
        interaction.client.loop.create_task(auto_delete())

    # 🌟 大富翁風格的圖示
    @discord.ui.button(label="機會", style=discord.ButtonStyle.success, emoji="🎲")
    async def btn_chance(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_event(interaction, "機會")

    @discord.ui.button(label="命運", style=discord.ButtonStyle.primary, emoji="🃏")
    async def btn_fate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_event(interaction, "命運")

    async def on_timeout(self):
        try: await self.message.delete()
        except: pass


# ==========================================
# 讀取設定與處理撞名防護
# ==========================================
config_data = load_config()

CMD_DIVINATION = config_data.get('cmd_divination', '機運')
# 建立預期支援的別名清單，並動態移除與主要指令名稱重複的項目，避免 CommandRegistrationError
ALIASES_DIVINATION = ['機運', '求籤', '機會', '命運', '大富翁']
if CMD_DIVINATION in ALIASES_DIVINATION:
    ALIASES_DIVINATION.remove(CMD_DIVINATION)

CMD_GACHA = config_data.get('cmd_gacha', '神鑿')


class GachaView(discord.ui.View):
    def __init__(self, bot, author_id):
        super().__init__(timeout=60) 
        self.bot = bot
        self.author_id = author_id

    async def process_gacha(self, interaction: discord.Interaction, count: int):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 這不是你的開鑿選單喔！", ephemeral=True)
            return

        config = load_config()
        users = load_users()
        data = get_user_data(interaction.user.id, users)
        
        current_chisels = data["inventory"].get("鑒石神鑿", 0)
        if current_chisels < count:
            await interaction.response.send_message(f"❌ 道具不足！背包裡只有 {current_chisels} 個鑒石神鑿。", ephemeral=True)
            return

        data["inventory"]["鑒石神鑿"] -= count
        results = {"天賞": {}, "奇賞": {}, "凡賞": {}}
        auto_convert = config.get("enable_auto_convert", False)
        convert_rate = config.get("auto_convert_rate", 20)
        converted_count_this_roll = 0
        
        for _ in range(count):
            data["pity_count"] += 1
            roll = random.randint(1, 1000)
            
            if roll <= config.get('gacha_rate_grand', 4) or data["pity_count"] >= config.get('gacha_pity_count', 180):
                # 🌟 支援機率權重制天賞
                pool_g = config.get('pool_grand', {'天賞石': 100})
                if isinstance(pool_g, list):
                    item = random.choice(pool_g)
                else:
                    items = list(pool_g.keys())
                    weights = list(pool_g.values())
                    item = random.choices(items, weights=weights, k=1)[0]
                    
                results["天賞"][item] = results["天賞"].get(item, 0) + 1
                data["inventory"][item] = data["inventory"].get(item, 0) + 1
                data["pity_count"] = 0 
                
            elif roll <= (config.get('gacha_rate_grand', 4) + config.get('gacha_rate_rare', 40)):
                item = random.choice(config.get('pool_rare', ['奇賞石']))
                results["奇賞"][item] = results["奇賞"].get(item, 0) + 1
                if auto_convert: converted_count_this_roll += 1
                else: data["inventory"][item] = data["inventory"].get(item, 0) + 1
            else: 
                item = random.choice(config.get('pool_normal', ['凡賞物品']))
                results["凡賞"][item] = results["凡賞"].get(item, 0) + 1
                if auto_convert: converted_count_this_roll += 1
                else: data["inventory"][item] = data["inventory"].get(item, 0) + 1

        earned_coins = 0
        if auto_convert and converted_count_this_roll > 0:
            data["scrap"] = data.get("scrap", 0) + converted_count_this_roll
            earned_coins = data["scrap"] // convert_rate
            data["scrap"] = data["scrap"] % convert_rate  
            data["coins"] += earned_coins

        save_users(users)

        embed = discord.Embed(title=f"🎰 開鑿結果 - {count} 連抽", color=0xffd700 if results["天賞"] else 0x5865f2, timestamp=datetime.now())
        embed.set_footer(text=f"📊 當前保底水位：{data['pity_count']} / {config.get('gacha_pity_count', 180)}")

        if results["天賞"]:
            ts_text = "\n".join([f"✨ **{k}** x{v}" for k, v in results["天賞"].items()])
            embed.add_field(name="【天賞降臨】", value=ts_text, inline=False)
            
            # 🌟 天賞專屬全頻特效
            if config.get('enable_grand_effect', True):
                embed.description = "🎇 **【全服通報】天命降臨，神諭現世！**\n恭喜同門突破天際，一舉奪得稀世奇珍！"
                embed.color = 0xff0000
            else:
                embed.description = "🎉 **恭喜同門歐氣爆發，天命所歸！**\n*(天賞物品已自動存入背包)*"
        
        if auto_convert:
            if converted_count_this_roll > 0:
                scrap_text = f"本次抽出的 **{converted_count_this_roll}** 件奇/凡賞已自動化為碎片。\n"
                if earned_coins > 0: scrap_text += f"💰 兌換成功！獲得 **{earned_coins}** 銅幣\n"
                scrap_text += f"*(當前累積碎片: {data['scrap']} / {convert_rate})*"
                embed.add_field(name="♻️ 【神爐自動熔煉】", value=scrap_text, inline=False)
        else:
            if results["奇賞"]: embed.add_field(name="【奇賞清單】", value="\n".join([f"💎 {k} x{v}" for k, v in results["奇賞"].items()]), inline=False)
            if results["凡賞"]: embed.add_field(name="📦 【凡賞匯總】", value="、".join([f"{k} x{v}" for k, v in results["凡賞"].items()]), inline=False)

        self.stop()
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(label="單抽", style=discord.ButtonStyle.secondary, emoji="🔨")
    async def single_pull(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_gacha(interaction, 1)

    @discord.ui.button(label="10連抽", style=discord.ButtonStyle.success, emoji="⚔️")
    async def ten_pull(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_gacha(interaction, 10)

    @discord.ui.button(label="全力開鑿 (50抽)", style=discord.ButtonStyle.danger, emoji="🔥")
    async def fifty_pull(self, interaction: discord.Interaction, button: discord.ui.Button): await self.process_gacha(interaction, 50)


class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🌟 透過動態變數綁定，完美避開 Alias 重複問題
    @commands.command(name=CMD_DIVINATION, aliases=ALIASES_DIVINATION)
    async def divination(self, ctx):
        try: await ctx.message.delete(delay=120.0)
        except: pass
        
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        today = str(datetime.now().date())
        
        if data["last_divination"] == today: 
            return await ctx.reply(f"🎲 {ctx.author.mention} 今日已經選擇過命運了，明日再來吧！", delete_after=15.0)
            
        embed = discord.Embed(
            title="🎲 每日機會與命運",
            description=f"{ctx.author.mention} 大俠，新的一天開始了！\n請選擇您今天的挑戰，有機會獲得豐厚的銅幣，但也可能破財消災喔！\n\n👉 **請點擊下方按鈕做出選擇：**",
            color=0x5865F2
        )
        embed.set_footer(text="*(🧹 此面板將於 2 分鐘後自動清理)*")
        
        view = ChanceFateView(ctx.author.id)
        msg = await ctx.reply(embed=embed, view=view, delete_after=120.0)
        view.message = msg

    # ==========================================
    # 👑 GM 專屬無限測試指令
    # ==========================================
    @commands.command(name="gm_求籤", aliases=["gm_test_divination"])
    async def gm_test_divination(self, ctx):
        try: await ctx.message.delete(delay=30.0)
        except: pass

        config = load_config()
        if str(ctx.author.id) not in config.get('admin_ids', []):
            return await ctx.reply("❌ 警告：你不是 GM，無法使用此測試指令！", delete_after=15.0)

        embed = discord.Embed(
            title="👑 [GM測試] 機會與命運",
            description=f"{ctx.author.mention} 這是沒有次數限制的測試面板！\n點擊下方按鈕來測試各式各樣的事件吧！",
            color=0xffd700
        )
        
        # 🌟 啟動 GM 測試模式，不記錄 last_divination
        view = ChanceFateView(ctx.author.id, is_gm_test=True)
        msg = await ctx.reply(embed=embed, view=view)
        view.message = msg

    @commands.command(name=CMD_GACHA)
    async def gacha_menu(self, ctx):
        try: await ctx.message.delete(delay=120.0)
        except: pass
        
        config = load_config()
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        embed = discord.Embed(title="💎 鑒石開鑿 - 命運之輪", description=f"目前持有：**{data['inventory'].get('鑒石神鑿', 0)}** 個鑒石神鑿\n保底進度：**{data['pity_count']}** / {config.get('gacha_pity_count', 180)}", color=0x5865f2)
        embed.set_footer(text="*(🧹 此開鑿畫面將於 2 分鐘後自動清理)*")
        await ctx.reply(embed=embed, view=GachaView(self.bot, ctx.author.id), delete_after=120.0)

async def setup(bot): await bot.add_cog(Gacha(bot))