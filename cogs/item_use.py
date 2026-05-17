import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import os
import io
import re
import requests
import random
from utils import load_users, save_users, get_user_data, load_config, save_config

# ==========================================
# 📝 實體獎勵兌換彈出視窗 (Modal)
# ==========================================
class RedeemModal(discord.ui.Modal):
    def __init__(self, item_name, bot, original_message=None):
        super().__init__(title=f"實體獎勵兌換：{item_name[:15]}")
        self.item_name = item_name
        self.bot = bot
        self.original_message = original_message

        self.server_input = discord.ui.TextInput(label="您的遊戲伺服器", placeholder="例如：江湖/紫禁之巔", required=True, max_length=50)
        self.id_input = discord.ui.TextInput(label="您的遊戲角色 ID", placeholder="請輸入正確的數字 ID 以便發放", required=True, max_length=50)
        self.name_input = discord.ui.TextInput(label="您的遊戲暱稱", placeholder="例如：王大明", required=True, max_length=50)

        self.add_item(self.server_input)
        self.add_item(self.id_input)
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        users = load_users()
        data = get_user_data(interaction.user.id, users)

        if data["inventory"].get(self.item_name, 0) < 1:
            return await interaction.response.send_message("❌ 您的背包中該道具數量不足，兌換失敗！", ephemeral=True)

        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        await interaction.response.send_message(f"✅ **兌換登記成功！**\n您已消耗 1 個 **{self.item_name}**。小布已經將資料飛鴿傳書給當家了，請靜候發放！", ephemeral=True)

        data["inventory"][self.item_name] -= 1
        if data["inventory"][self.item_name] <= 0: del data["inventory"][self.item_name]
        save_users(users)

        config = load_config()
        admin_ids = config.get("admin_ids", [])
        
        embed = discord.Embed(title="🎁 玩家實體獎勵兌換通知！", color=0xffd700, timestamp=datetime.now())
        embed.add_field(name="申請人", value=f"{interaction.user.mention} (`{interaction.user.name}`)", inline=False)
        embed.add_field(name="申請道具", value=f"**{self.item_name}**", inline=False)
        embed.add_field(name="🌐 伺服器", value=f"`{self.server_input.value}`", inline=True)
        embed.add_field(name="🆔 角色 ID", value=f"`{self.id_input.value}`", inline=True)
        embed.add_field(name="👤 遊戲暱稱", value=f"`{self.name_input.value}`", inline=True)

        for admin_id in admin_ids:
            try:
                admin_user = await self.bot.fetch_user(int(admin_id))
                if admin_user: await admin_user.send(embed=embed)
            except: pass

        await asyncio.sleep(5)
        try: await interaction.delete_original_response()
        except: pass


# ==========================================
# 🔢 數量詢問彈出視窗 (Modal) 用於木樁與交配證
# ==========================================
class ItemQtyModal(discord.ui.Modal):
    def __init__(self, item_name, bot, original_message=None):
        super().__init__(title=f"準備使用：{item_name[:15]}")
        self.item_name = item_name
        self.bot = bot
        self.original_message = original_message
        
        self.qty_input = discord.ui.TextInput(
            label="請輸入使用數量",
            default="1",
            required=True,
            max_length=4,
            placeholder="請輸入正整數，例如: 10"
        )
        self.add_item(self.qty_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            use_qty = int(self.qty_input.value)
            if use_qty <= 0: raise ValueError
        except:
            return await interaction.response.send_message("❌ 數量請輸入正整數！", ephemeral=True)

        users = load_users()
        data = get_user_data(interaction.user.id, users)

        if data["inventory"].get(self.item_name, 0) < use_qty:
            return await interaction.response.send_message(f"❌ 數量不足！您的行囊裡只有 **{data['inventory'].get(self.item_name, 0)}** 個。", ephemeral=True)

        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        data["inventory"][self.item_name] -= use_qty
        if data["inventory"][self.item_name] <= 0: del data["inventory"][self.item_name]
        save_users(users)

        await interaction.response.send_message(f"✅ 成功發動 **{self.item_name}** x{use_qty}！", ephemeral=True)
        
        channel = interaction.channel
        user = interaction.user

        if self.item_name == "樁·小花":
            # 🌟 根據數量設定打擊次數需求與圖片
            if use_qty >= 50:
                max_hits = 20
                file_path = os.path.join("assets", "items", "wooden_dummy_50.png")
                title_text = "🌸 史詩級木樁大軍降臨！"
                desc_text = f"🔥 **{user.mention}** 瘋狂地砸出了 **{use_qty}** 個【樁·小花】！\n木樁堆成了一座堅不可摧的木頭山！"
                announce = "📢 **史詩級木樁大軍出現啦！**"
            elif use_qty >= 10:
                max_hits = 10
                file_path = os.path.join("assets", "items", "wooden_dummy_10.png")
                title_text = "🌸 樁·小花 陣型展開！"
                desc_text = f"**{user.mention}** 豪氣地撒下了 **{use_qty}** 個【樁·小花】！\n木樁排成了壯觀的陣型！"
                announce = "📢 **木樁陣型出現了！**"
            else:
                max_hits = 5
                file_path = os.path.join("assets", "items", "wooden_dummy.png")
                qty_text = f" **{use_qty}** 個" if use_qty > 1 else "一個"
                title_text = "🌸 樁·小花 出現了！"
                desc_text = f"**{user.mention}** 在地上立了{qty_text}【樁·小花】！\n這木樁看起來挺結實的。"
                announce = "📢 **有人放出了木樁！**"
                
            embed = discord.Embed(
                title=title_text,
                description=desc_text + f"\n\n*(💡 每位大俠限打一次，只要全服累計成功發動 **{max_hits} 次有效打擊** 就能破壞它！)*",
                color=0xd8b4e2
            )
            
            view = DummyGameView(use_qty, max_hits)
            
            if os.path.exists(file_path):
                discord_file = discord.File(file_path, filename="dummy.png")
                embed.set_image(url="attachment://dummy.png")
                msg = await channel.send(content=announce, embed=embed, file=discord_file, view=view)
            else:
                msg = await channel.send(content=announce, embed=embed, view=view)
                
            view.message = msg

        elif self.item_name == "嗷嗷交配證":
            mention_str = "<@845962912656261182>"
            
            qty_text = f"一口氣掏出了 **{use_qty}** 張閃亮亮的" if use_qty > 1 else "掏出了一張閃亮亮的"
            await channel.send(f"📢 **{user.mention}** {qty_text}【嗷嗷交配證】！\n👉 {mention_str}，大爺/大娘點你台了，還不快點出來接客配種！💦")


# ==========================================
# 🌸 樁·小花 (多階層技能動態盲盒版 - 無痕防卡頓)
# ==========================================
class DummyGameView(discord.ui.View):
    def __init__(self, qty, max_hits):
        super().__init__(timeout=None)
        self.qty = qty
        self.max_hits = max_hits
        self.hit_count = 0
        self.is_broken = False
        self.participants = {}

    @discord.ui.button(label="🥊 痛扁木樁", style=discord.ButtonStyle.danger)
    async def attack_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_broken:
            return await interaction.response.send_message("🪵 木樁已經碎滿地了，放過它吧！", ephemeral=True)

        if interaction.user.id in self.participants:
            return await interaction.response.send_message("❌ 你已經揍過這波木樁了，把機會留給其他人吧！", ephemeral=True)

        rand_val = random.random()
        hits_added = 0
        
        if self.qty >= 50:
            if rand_val < 0.01:
                msg_text = "☄️ **埼玉附體！**你使出【認真毆打】，拳風瞬間摧毀了成堆的木樁！*(造成 5 次有效打擊)*"
                hits_added = 5
            elif rand_val < 0.06:
                msg_text = "🔥 **天火降臨！**你召喚了巨大隕石砸向木樁山，瞬間木屑橫飛！*(造成 4 次有效打擊)*"
                hits_added = 4
            elif rand_val < 0.16:
                msg_text = "🌪️ **劍刃風暴！**你化作一道龍捲風捲入木樁堆中，大肆破壞！*(造成 3 次有效打擊)*"
                hits_added = 3
            elif rand_val < 0.31:
                msg_text = "💣 **藝術就是爆炸！**你往木樁堆裡扔了一顆霹靂堂特製炸彈！*(造成 2 次有效打擊)*"
                hits_added = 2
            elif rand_val < 0.41:
                msg_text = "😱 木樁實在太多了！你被密密麻麻的木樁淹沒，完全找不到出手的空間... *(無效打擊)*"
                hits_added = 0
            elif rand_val < 0.51:
                msg_text = "💦 爬木樁山太累了，你喘了口氣，決定坐下來吃瓜。*(無效打擊)*"
                hits_added = 0
            else:
                msg_text = "🥊 命中！你隨便挑了一根木樁，狠狠地給了它一拳！*(造成 1 次有效打擊)*"
                hits_added = 1
                
        elif self.qty >= 10:
            if rand_val < 0.01:
                msg_text = "☄️ **埼玉附體！**你使出【連續普通拳】，瞬間掃斷一片木樁！*(造成 5 次有效打擊)*"
                hits_added = 5
            elif rand_val < 0.06:
                msg_text = "🌪️ **橫掃千軍！**你拔出武器一陣狂舞，一口氣掃斷了好幾根木樁！*(造成 3 次有效打擊)*"
                hits_added = 3
            elif rand_val < 0.21:
                msg_text = "🥷 **漫天花雨！**你甩出大把暗器，精準命中多個木樁！*(造成 2 次有效打擊)*"
                hits_added = 2
            elif rand_val < 0.31:
                msg_text = "🤕 木樁太多了！你不小心被其中一根絆倒，摔了個四腳朝天... *(無效打擊)*"
                hits_added = 0
            elif rand_val < 0.50:
                msg_text = "😵 陣型太密集，你一時不知道該打哪一個，反而錯失了出手機會。*(無效打擊)*"
                hits_added = 0
            else:
                msg_text = "🥊 你找準空隙，扎扎實實地揍了其中一根木樁！*(造成 1 次有效打擊)*"
                hits_added = 1
                
        else:
            if rand_val < 0.01:
                msg_text = "☄️ **埼玉附體！**你使出【認真毆打】，一拳把木樁打飛到了大氣層外！*(造成 5 次有效打擊)*"
                hits_added = 5
            elif rand_val < 0.05:
                msg_text = "😜 你對著木樁做了一個極度嘲諷的鬼臉，木樁如果會說話一定會罵你。*(無效打擊)*"
                hits_added = 0
            elif rand_val < 0.15:
                msg_text = "💨 你轉過身，對著木樁放了一個震天響的連環水屁... 木樁聞起來臭臭的。*(造成 1 次有效打擊)*"
                hits_added = 1
            elif rand_val < 0.30:
                msg_text = "💦 揮空了！你腳底一滑，在木樁面前摔了個狗吃屎... *(無效打擊)*"
                hits_added = 0
            elif rand_val < 0.40:
                msg_text = "💥 **爆擊！**你使出江湖失傳已久的絕學，對木樁造成了成噸的傷害！*(造成 2 次有效打擊)*"
                hits_added = 2
            else:
                msg_text = "🥊 命中！你扎扎實實地揍了木樁一拳，手感挺不錯的！*(造成 1 次有效打擊)*"
                hits_added = 1
        
        self.hit_count += hits_added
        self.participants[interaction.user.id] = hits_added

        try:
            await interaction.response.send_message(msg_text, ephemeral=True)
            async def auto_delete():
                await asyncio.sleep(10.0)
                try: await interaction.delete_original_response()
                except: pass
            interaction.client.loop.create_task(auto_delete())
        except discord.HTTPException:
            pass

        if self.hit_count >= self.max_hits and not self.is_broken:
            self.is_broken = True
            button.label = "💥 已經碎成木屑了"
            button.disabled = True
            self.stop()
            
            try:
                embed = interaction.message.embeds[0]
                embed.title = "💥 樁·小花 被徹底打爛啦！"
                embed.color = 0x4ade80
                embed.description = f"🪵 經過大俠們的輪番轟炸 (累計 {self.hit_count} 次有效打擊)，木樁陣終於承受不住，化為滿地的木屑了..."
                embed.set_footer(text=f"🏆 完成最後一擊：{interaction.user.display_name}")
                
                file_path = os.path.join("assets", "items", "wooden_dummy_broken.png")
                if os.path.exists(file_path):
                    file = discord.File(file_path, filename="dummy_broken.png")
                    embed.set_image(url="attachment://dummy_broken.png")
                    await interaction.message.edit(embed=embed, view=self, attachments=[file])
                else:
                    await interaction.message.edit(embed=embed, view=self)
            except Exception:
                pass


# ==========================================
# 🎯 指定對象下拉選單 (View) 用於絲帶抽打
# ==========================================
class WhipTargetView(discord.ui.View):
    def __init__(self, bot, author_id, original_message=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.author_id = author_id
        self.original_message = original_message

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👉 點擊此處，選擇你要抽打的公會成員...")
    async def select_target(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這不是你的道具！", ephemeral=True)

        target = select.values[0]
        users = load_users()
        data = get_user_data(interaction.user.id, users)

        if data["inventory"].get("姑姑的絲帶抽打", 0) < 1:
            return await interaction.response.send_message("❌ 數量不足！背包裡已經沒有【姑姑的絲帶抽打】了。", ephemeral=True)

        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        data["inventory"]["姑姑的絲帶抽打"] -= 1
        if data["inventory"]["姑姑的絲帶抽打"] <= 0: del data["inventory"]["姑姑的絲帶抽打"]
        save_users(users)

        await interaction.response.edit_message(content=f"✅ 已鎖定目標 **{target.display_name}**！準備處刑...", view=None)

        embed = discord.Embed(
            description=f"🎀 **{interaction.user.display_name}** 揮舞著【姑姑的絲帶】，狠狠地抽打了 **{target.display_name}**！", 
            color=0xff0055
        )
        embed.set_image(url="https://media.tenor.com/P40r8m_x3rAAAAAC/whip-punish.gif") 
        await interaction.channel.send(content=f"{target.mention}", embed=embed)

        await asyncio.sleep(3)
        try: await interaction.delete_original_response()
        except: pass


# ==========================================
# ⚽ 指定對象下拉選單 (View) 用於足球
# ==========================================
class FootballTargetView(discord.ui.View):
    def __init__(self, bot, author_id, original_message=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.author_id = author_id
        self.original_message = original_message

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👉 點擊此處，選擇你想踢向的目標...")
    async def select_target(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這不是你的足球！", ephemeral=True)

        target = select.values[0]
        users = load_users()
        data = get_user_data(interaction.user.id, users)

        if data["inventory"].get("足球", 0) < 1:
            return await interaction.response.send_message("❌ 數量不足！背包裡已經沒有【足球】了。", ephemeral=True)

        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        data["inventory"]["足球"] -= 1
        if data["inventory"]["足球"] <= 0: del data["inventory"]["足球"]
        save_users(users)

        await interaction.response.edit_message(content=f"✅ 已鎖定目標 **{target.display_name}**！起腳射門...", view=None)

        outcomes = [
            {
                "text": f"卻被 **{target.display_name}** 帥氣地接到了！😎", 
                "gif": "https://media.tenor.com/G55nIWe_1dEAAAAC/blue-lock-seishiro-nagi.gif", 
                "color": 0x4ade80
            },
            {
                "text": f"**{target.display_name}** 來不及反應，球直接「啪！」一聲巴在了臉上！💥🤕", 
                "gif": "https://media.tenor.com/w2Yv2P_3J94AAAAC/headshot-soccer.gif", 
                "color": 0xfacc15
            },
            {
                "text": f"**{target.display_name}** 完全來不及反應，整個人跟著球一起飛離了地球！🚀🌍", 
                "gif": "https://media.tenor.com/o1P5x0Y2bXoAAAAC/team-rocket-blasting-off-again.gif", 
                "color": 0xf87171
            }
        ]
        outcome = random.choice(outcomes)

        embed = discord.Embed(
            description=f"⚽ **{interaction.user.display_name}** 運足了洪荒之力，將【足球】大力踢向了 **{target.display_name}**！\n\n結果：{outcome['text']}", 
            color=outcome['color']
        )
        embed.set_image(url=outcome['gif']) 
        
        await interaction.channel.send(content=f"{target.mention}", embed=embed)

        await asyncio.sleep(3)
        try: await interaction.delete_original_response()
        except: pass


# ==========================================
# 🧦 指定對象下拉選單 (View) 用於望月的襪子
# ==========================================
class SocksTargetView(discord.ui.View):
    def __init__(self, bot, author_id, original_message=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.author_id = author_id
        self.original_message = original_message

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👉 點擊此處，選擇你要賜予自由的對象...")
    async def select_target(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這不是你的襪子！", ephemeral=True)

        target = select.values[0]
        users = load_users()
        data = get_user_data(interaction.user.id, users)

        if data["inventory"].get("望月的襪子", 0) < 1:
            return await interaction.response.send_message("❌ 數量不足！背包裡已經沒有【望月的襪子】了。", ephemeral=True)

        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        # 扣除發動者的襪子
        data["inventory"]["望月的襪子"] -= 1
        if data["inventory"]["望月的襪子"] <= 0: del data["inventory"]["望月的襪子"]
        save_users(users)

        await interaction.response.edit_message(content=f"✅ 已鎖定目標 **{target.display_name}**！賦予自由中...", view=None)

        embed = discord.Embed(
            description=f"🧦 **{interaction.user.display_name}** 送給了 **{target.display_name}** 【望月的襪子】！\n現在 **{target.display_name}** 自由了！\n\n*(然後 <@597022209705902092> 的襪子數量 -1)*", 
            color=0xd1d5db
        )
        
        file_path = os.path.join("assets", "items", "free_socks.gif")
        if os.path.exists(file_path):
            discord_file = discord.File(file_path, filename="free_socks.gif")
            embed.set_image(url="attachment://free_socks.gif")
            await interaction.channel.send(content=f"{target.mention}", embed=embed, file=discord_file)
        else:
            embed.set_image(url="https://media.tenor.com/6V7y08s3A9AAAAAC/dobby-is-free.gif") 
            await interaction.channel.send(content=f"{target.mention}", embed=embed)

        await asyncio.sleep(3)
        try: await interaction.delete_original_response()
        except: pass


# ==========================================
# ⚖️ 審判小錘錘 - 投票與處刑邏輯 (View)
# ==========================================
class JudgmentVoteView(discord.ui.View):
    def __init__(self, target_member, author, crime_reason):
        super().__init__(timeout=60)
        self.target_member = target_member
        self.author = author
        self.crime_reason = crime_reason
        self.guilty_votes = set()
        self.not_guilty_votes = set()
        self.message = None

    @discord.ui.button(label="💀 有罪 (0)", style=discord.ButtonStyle.danger)
    async def vote_guilty(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.not_guilty_votes:
            self.not_guilty_votes.remove(interaction.user.id)
        self.guilty_votes.add(interaction.user.id)
        
        button.label = f"💀 有罪 ({len(self.guilty_votes)})"
        self.children[1].label = f"👼 無罪 ({len(self.not_guilty_votes)})"
        
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="👼 無罪 (0)", style=discord.ButtonStyle.success)
    async def vote_not_guilty(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.guilty_votes:
            self.guilty_votes.remove(interaction.user.id)
        self.not_guilty_votes.add(interaction.user.id)
        
        self.children[0].label = f"💀 有罪 ({len(self.guilty_votes)})"
        button.label = f"👼 無罪 ({len(self.not_guilty_votes)})"
        
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        if not self.message: return
        
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except: pass

        g_count = len(self.guilty_votes)
        n_count = len(self.not_guilty_votes)

        if g_count > n_count:
            try:
                guild_member = self.message.guild.get_member(self.target_member.id)
                if not guild_member:
                    guild_member = await self.message.guild.fetch_member(self.target_member.id)
                    
                if guild_member:
                    await guild_member.timeout(timedelta(minutes=3), reason=f"審判小錘錘判定有罪: {self.crime_reason}")
                    result_msg = f"⚖️ **審判結果出爐！**\n【有罪】**{g_count}** 票 vs 【無罪】**{n_count}** 票\n💀 根據民意，**{self.target_member.mention} 被判定為有罪！**\n執行刑罰：**領域內禁言 3 分鐘**！"
                else:
                    result_msg = f"⚖️ **審判結果出爐！有罪！**\n但犯人 {self.target_member.display_name} 已經潛逃出境了！(強制抓取失敗)"
            except discord.Forbidden:
                result_msg = f"⚖️ **審判結果出爐！**\n【有罪】**{g_count}** 票 vs 【無罪】**{n_count}** 票\n💀 **{self.target_member.mention} 被判定為有罪！**\n*(但對方的靈壓太強 / 小布沒被賦予隔離權限，無法執行禁言，算你走運！)*"
            except discord.HTTPException:
                result_msg = f"⚖️ **審判結果出爐！有罪！**\n但犯人 {self.target_member.display_name} 已經潛逃出境了！(網路錯誤)"
        else:
            result_msg = f"⚖️ **審判結果出爐！**\n【有罪】**{g_count}** 票 vs 【無罪】**{n_count}** 票\n👼 **證據不足，{self.target_member.mention} 當庭無罪釋放！**"

        await self.message.channel.send(result_msg)


# ==========================================
# ⚖️ 審判小錘錘 - 輸入罪狀彈出視窗 (Modal)
# ==========================================
class JudgeCrimeModal(discord.ui.Modal):
    def __init__(self, bot, author_id, target_member):
        super().__init__(title=f"審判對象：{target_member.display_name[:15]}")
        self.bot = bot
        self.author_id = author_id
        self.target_member = target_member
        
        self.crime_input = discord.ui.TextInput(
            label="請列出對方的罪狀",
            style=discord.TextStyle.paragraph,
            placeholder="例如：在群裡天天曬卡、偷吃別人的布丁...",
            required=True,
            max_length=200
        )
        self.add_item(self.crime_input)

    async def on_submit(self, interaction: discord.Interaction):
        crime = self.crime_input.value
        
        users = load_users()
        data = get_user_data(self.author_id, users)
        if data["inventory"].get("審判小錘錘", 0) < 1:
            return await interaction.response.send_message("❌ 你的【審判小錘錘】不見了！", ephemeral=True)
        
        data["inventory"]["審判小錘錘"] -= 1
        if data["inventory"]["審判小錘錘"] <= 0: del data["inventory"]["審判小錘錘"]
        save_users(users)
        
        embed = discord.Embed(
            title="⚖️ 領域展開：誅伏賜死",
            description=f"**原告**：{interaction.user.mention}\n**被告**：{self.target_member.mention}\n\n📜 **【被控罪狀】**\n```{crime}```\n\n📢 **請陪審團（全體群友）在 60 秒內投下神聖的一票！**",
            color=0x2b2d31
        )
        
        file_path = os.path.join("assets", "system", "domain_expansion.gif")
        discord_file = None
        if os.path.exists(file_path):
            discord_file = discord.File(file_path, filename="domain_expansion.gif")
            embed.set_image(url="attachment://domain_expansion.gif")
        else:
            embed.set_image(url="https://media.tenor.com/O2fMv0J8O-sAAAAC/domain-expansion-deadly-sentencing.gif")
        
        view = JudgmentVoteView(self.target_member, interaction.user, crime)
        
        await interaction.response.send_message("✅ 審判領域已展開！", ephemeral=True)
        
        target_role = None
        if interaction.guild:
            for role in interaction.guild.roles:
                if "幫會成員" in role.name:
                    target_role = role
                    break
        
        mention_str = target_role.mention if target_role else "@幫會成員"

        if discord_file:
            msg = await interaction.channel.send(
                content=f"{mention_str} ⚖️ **最高法庭開庭啦！**", 
                embed=embed, 
                view=view,
                file=discord_file,
                allowed_mentions=discord.AllowedMentions(roles=True)
            )
        else:
            msg = await interaction.channel.send(
                content=f"{mention_str} ⚖️ **最高法庭開庭啦！**\n*(系統提示：未偵測到本地領域圖片，使用備用網址)*", 
                embed=embed, 
                view=view,
                allowed_mentions=discord.AllowedMentions(roles=True)
            )
            
        view.message = msg


# ==========================================
# ⚖️ 審判小錘錘 - 指定對象下拉選單 (View)
# ==========================================
class JudgeTargetView(discord.ui.View):
    def __init__(self, bot, author_id, original_message=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.author_id = author_id
        self.original_message = original_message

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👉 點擊此處，選擇你要審判的對象...")
    async def select_target(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這不是你的錘錘！", ephemeral=True)

        target_member = select.values[0]
        
        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        await interaction.response.send_modal(JudgeCrimeModal(self.bot, self.author_id, target_member))


# ==========================================
# 💎 天賞石/奇賞石 專屬選項按鈕 (View)
# ==========================================
class StoneChoiceView(discord.ui.View):
    def __init__(self, author_id, item_name, bot, original_message=None):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.item_name = item_name
        self.bot = bot
        self.original_message = original_message

    @discord.ui.button(label="👅 舔石頭一下", style=discord.ButtonStyle.primary)
    async def lick_stone(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 走開啦，這不是你的石頭！", ephemeral=True)
            
        users = load_users()
        data = get_user_data(self.author_id, users)
        if data["inventory"].get(self.item_name, 0) < 1:
            return await interaction.response.edit_message(content="❌ 你的石頭已經不見了！", view=None)
            
        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        await interaction.response.edit_message(content="✅ 已舔拭石頭！(石頭依然完好如初，請放心)", view=None)
        await interaction.channel.send(f"👅 **{interaction.user.mention}** 掏出了閃亮亮的 **{self.item_name}**，當眾舔了一口並大喊：\n「哎呀你看這 **{self.item_name}** 好香啊～～」")

        await asyncio.sleep(3)
        try: await interaction.delete_original_response()
        except: pass

    @discord.ui.button(label="💥 用洪荒之力按壓", style=discord.ButtonStyle.danger)
    async def crush_stone(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 你無法按壓別人的石頭！", ephemeral=True)
            
        users = load_users()
        data = get_user_data(self.author_id, users)
        if data["inventory"].get(self.item_name, 0) < 1:
            return await interaction.response.edit_message(content="❌ 你的石頭已經不見了！", view=None)
            
        if self.original_message:
            try: await self.original_message.delete()
            except: pass

        data["inventory"][self.item_name] -= 1
        if data["inventory"][self.item_name] <= 0: del data["inventory"][self.item_name]
        
        config = load_config()
        sell_prices = config.get("sell_prices", {})
        fallback_price = 20000 if "天賞" in self.item_name else 100
        price = int(sell_prices.get(self.item_name, fallback_price))
        total_pool = int(price * 2 / 3)

        guild_members = [m for m in interaction.guild.members if not m.bot]
        if not guild_members: guild_members = [interaction.user]
        
        num_winners = min(30, len(guild_members))
        winners = random.sample(guild_members, num_winners)
        
        if num_winners <= 1:
            amounts = [total_pool]
        else:
            breakpoints = sorted([random.randint(0, total_pool) for _ in range(num_winners - 1)])
            breakpoints = [0] + breakpoints + [total_pool]
            amounts = [breakpoints[i+1] - breakpoints[i] for i in range(num_winners)]
            
        for winner, amount in zip(winners, amounts):
            if amount > 0:
                w_data = get_user_data(winner.id, users)
                w_data["coins"] += amount

        save_users(users)
        
        msg = f"💥 **{interaction.user.mention}** 用洪荒之力按壓了 **{self.item_name}**...\n"
        msg += f"✨ **石頭發出一陣強烈的光芒，爆開了！**\n"
        msg += f"化作漫天金雨，隨機灑落在 **{num_winners}** 位幸運兒身上，總計送出了 **{total_pool}** 銅幣！"
        
        await interaction.response.edit_message(content="💥 石頭已順利爆開，發送金雨！", view=None)
        await interaction.channel.send(msg)

        await asyncio.sleep(3)
        try: await interaction.delete_original_response()
        except: pass


# ==========================================
# 🌟 共用的道具執行路由邏輯
# ==========================================
async def handle_item_interaction(interaction: discord.Interaction, item_name: str, bot, author_id: int, original_message: discord.Message = None):
    users = load_users()
    data = get_user_data(author_id, users)
    
    if data["inventory"].get(item_name, 0) < 1:
        return await interaction.response.send_message(f"❌ 行囊裡已經沒有 **{item_name}** 囉！", ephemeral=True)

    if item_name == "姑姑的絲帶抽打":
        return await interaction.response.send_message("🎀 **請在下方選單挑選一名受害者：**", view=WhipTargetView(bot, author_id, original_message), ephemeral=True)
        
    elif item_name == "足球":
        return await interaction.response.send_message("⚽ **請在下方選單挑選你想踢飛的目標：**", view=FootballTargetView(bot, author_id, original_message), ephemeral=True)

    elif item_name == "審判小錘錘":
        return await interaction.response.send_message("⚖️ **請在下方選單挑選你要審判的對象：**", view=JudgeTargetView(bot, author_id, original_message), ephemeral=True)

    elif item_name == "望月的襪子":
        return await interaction.response.send_message("🧦 **請在下方選單挑選你想賜予自由的對象：**", view=SocksTargetView(bot, author_id, original_message), ephemeral=True)

    elif item_name in ["樁·小花", "嗷嗷交配證"]:
        return await interaction.response.send_modal(ItemQtyModal(item_name, bot, original_message))
        
    elif item_name in ["天賞石", "奇賞石"]:
        return await interaction.response.send_message(f"💎 你拿出了 **{item_name}**，打算怎麼做？", view=StoneChoiceView(author_id, item_name, bot, original_message), ephemeral=True)

    elif item_name == "大當家的黑絲襪":
        config = load_config()
        api_key = config.get("grok_api_key", "")
        if not api_key:
            return await interaction.response.send_message("❌ 系統尚未設定 Grok API Key，無法施展黑絲召喚術！", ephemeral=True)
        
        if original_message:
            try: await original_message.delete()
            except: pass

        await interaction.response.send_message("✅ 發動成功！正在召喚黑絲...", ephemeral=True)
        wait_msg = await interaction.channel.send("🖤 正在為您潛入大當家的衣櫃，竊取極品黑絲畫面，請稍候...")

        data["inventory"]["大當家的黑絲襪"] -= 1
        if data["inventory"]["大當家的黑絲襪"] <= 0: del data["inventory"]["大當家的黑絲襪"]
        save_users(users)

        try:
            api_url = "https://api.x.ai/v1/images/generations"
            payload = {
                "model": "grok-imagine-image", 
                "prompt": "Close up of beautiful legs wearing elegant black pantyhose, seductive, high quality, highly detailed, realistic [safe for work]"
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            response = await asyncio.to_thread(requests.post, api_url, headers=headers, json=payload, timeout=25)
            
            if response.status_code == 200:
                img_url = response.json().get("data", [{}])[0].get("url")
                img_response = await asyncio.to_thread(requests.get, img_url, timeout=15)
                img_bytes = img_response.content
                
                save_dir = os.path.join("assets", "black_silks")
                if not os.path.exists(save_dir): os.makedirs(save_dir)
                    
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(save_dir, f"{timestamp_str}_{interaction.user.name}_black_silk.png")
                try:
                    with open(save_path, "wb") as f:
                        f.write(img_bytes)
                except: pass
                
                file = discord.File(io.BytesIO(img_bytes), filename="black_silk.png")
                await wait_msg.delete()
                await interaction.channel.send(f"🖤 **大當家賞你的！{interaction.user.mention} 拿去好好欣賞吧！**", file=file)
            else:
                await wait_msg.edit(content=f"❌ 獲取失敗：大當家今天不想穿黑絲。 (Grok API Error: {response.status_code})")
        except Exception as e:
            await wait_msg.edit(content=f"❌ 發生錯誤，大當家的衣櫃鎖死了：{e}")
            
        try: await interaction.delete_original_response()
        except: pass
        return

    await interaction.response.send_modal(RedeemModal(item_name, bot, original_message))


# ==========================================
# 🎒 背包專用：動態生成使用按鈕的面板 (View)
# ==========================================
class BackpackUseView(discord.ui.View):
    def __init__(self, author_id, inventory, bot):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.bot = bot
        
        redeemable_keywords = ["月卡", "1880券", "2880券", "卡", "券"]
        interactive_items = ["大當家的黑絲襪", "嗷嗷交配證", "樁·小花", "姑姑的絲帶抽打", "天賞石", "奇賞石", "足球", "審判小錘錘", "望月的襪子"]
        
        count = 0
        for item, qty in inventory.items():
            is_redeem = any(kw in item for kw in redeemable_keywords)
            is_interactive = item in interactive_items
            
            if qty > 0 and (is_redeem or is_interactive) and item not in ["繪圖券", "改名卡"]:
                btn = discord.ui.Button(label=f"🎟️ 使用 {item}", style=discord.ButtonStyle.success)
                btn.callback = self.create_callback(item)
                self.add_item(btn)
                count += 1
                if count >= 25: break

    def create_callback(self, item_name):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ 這是別人的背包喔！", ephemeral=True)
            await handle_item_interaction(interaction, item_name, self.bot, self.author_id, interaction.message)
        return callback


# ==========================================
# 🔽 !使用 專用：互動式下拉選單 (View)
# ==========================================
class UseSelectView(discord.ui.View):
    def __init__(self, author_id, inventory, bot):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.bot = bot
        
        options = []
        redeemable_keywords = ["月卡", "1880券", "2880券", "卡", "券"]
        interactive_items = ["大當家的黑絲襪", "嗷嗷交配證", "樁·小花", "姑姑的絲帶抽打", "天賞石", "奇賞石", "足球", "審判小錘錘", "望月的襪子"]
        
        for item, qty in inventory.items():
            is_redeem = any(kw in item for kw in redeemable_keywords)
            is_interactive = item in interactive_items
            
            if qty > 0 and (is_redeem or is_interactive) and item not in ["繪圖券", "改名卡"]:
                options.append(discord.SelectOption(label=item, description=f"擁有數量: {qty}", value=item, emoji="🎒"))
                if len(options) >= 25: break
        
        if not options:
            options.append(discord.SelectOption(label="沒有可使用的道具", value="none"))

        select = discord.ui.Select(placeholder="👇 請選擇要發動的道具...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這是別人的選單喔！", ephemeral=True)
        
        val = self.children[0].values[0]
        if val == "none":
            return await interaction.response.send_message("❌ 您目前沒有可使用的道具。", ephemeral=True)
        
        await handle_item_interaction(interaction, val, self.bot, self.author_id, interaction.message)


# ==========================================
# 🔘 呼叫兌換表單的按鈕 (單一道具)
# ==========================================
class RedeemView(discord.ui.View):
    def __init__(self, author_id, item_name, bot):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.item_name = item_name
        self.bot = bot

    @discord.ui.button(label="📝 填寫兌換資料", style=discord.ButtonStyle.primary, emoji="✍️")
    async def fill_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這不是您的兌換單喔！", ephemeral=True)
        await interaction.response.send_modal(RedeemModal(self.item_name, self.bot, interaction.message))


# ==========================================
# 📦 隱私包裹轉發面板 (解決 ! 指令無法直接隱藏的問題)
# ==========================================
class SecretUseWrapperView(discord.ui.View):
    def __init__(self, author_id, inventory, bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.inventory = inventory
        self.bot = bot

    @discord.ui.button(label="📦 私密展開道具選單", style=discord.ButtonStyle.primary)
    async def open_secret(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 這是別人的包裹，請不要偷看！", ephemeral=True)
        
        # 展開隱藏選單
        await interaction.response.send_message(
            "🎒 **請選擇您要發動的道具：**\n*(此為隱藏訊息，只有您能看見，關閉 Discord 即消失)*", 
            view=UseSelectView(self.author_id, self.inventory, self.bot), 
            ephemeral=True
        )
        # 點開後自動銷毀原本的包裹按鈕
        try: await interaction.message.delete()
        except: pass


# ==========================================
# 🔧 主要使用指令與全域符號攔截器
# ==========================================
class ItemUse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🌟 全域防呆黑科技：自動將全形「！」轉換為半形「!」
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: 
            return
        # 只要開頭是全形的驚嘆號，就幫他換掉並重送！
        if message.content.startswith('！'):
            message.content = '!' + message.content[1:]
            await self.bot.process_commands(message)

    def normalize_name(self, name):
        return re.sub(r'[\s·\-._]', '', name).replace('椿', '樁')

    # ==========================================
    # 👑 GM 專屬特權指令區
    # ==========================================
    @commands.command(name="gm_給予", aliases=["gm_give"])
    async def gm_give(self, ctx, member: discord.Member, item_name: str, amount: int = 1):
        try: await ctx.message.delete(delay=30.0)
        except: pass
        
        config = load_config()
        if str(ctx.author.id) not in config.get('admin_ids', []):
            return await ctx.reply("❌ 警告：你不是 GM，無法使用此神聖指令！", delete_after=15.0)
        
        users = load_users()
        data = get_user_data(member.id, users)
        data["inventory"][item_name] = data["inventory"].get(item_name, 0) + amount
        save_users(users)
        await ctx.reply(f"👑 **【GM 權限強制啟動】**\n✅ 已強制將 **{item_name}** x{amount} 塞入 {member.mention} 的行囊中！", delete_after=30.0)


    # ==========================================
    # 一般使用指令
    # ==========================================
    @commands.command(name=load_config().get('cmd_use', '使用'))
    async def use_item(self, ctx, *, raw_input: str = ""):
        # 第一時間把大俠的指令刪掉，保持版面乾淨
        try: await ctx.message.delete()
        except: pass
        
        users = load_users()
        data = get_user_data(ctx.author.id, users)
        
        # 🌟 如果沒有輸入特定道具，呼叫「私密包裹黑科技」
        if not raw_input:
            wrapper_view = SecretUseWrapperView(ctx.author.id, data["inventory"], self.bot)
            return await ctx.send(f"{ctx.author.mention} 📦 **[專屬包裹]** 您的道具選單已送達，請點擊按鈕私密開啟！\n*(🧹 此包裹將於 30 秒後自動銷毀)*", view=wrapper_view, delete_after=30.0)

        clean_input = re.sub(r'<@!?\d+>', '', raw_input).strip()
        use_qty = 1
        match = re.search(r'\s+(\d+)$', clean_input) 
        if match:
            use_qty = int(match.group(1))
            clean_input = clean_input[:match.start()].strip()
        else:
            match2 = re.search(r'(\d+)$', clean_input) 
            if match2:
                use_qty = int(match2.group(1))
                clean_input = clean_input[:match2.start()].strip()

        if use_qty <= 0: use_qty = 1
        norm_input = self.normalize_name(clean_input)
        real_item = None
        
        if clean_input in data["inventory"]: real_item = clean_input
        else:
            for inv_item in data["inventory"].keys():
                if self.normalize_name(inv_item) == norm_input:
                    real_item = inv_item
                    break
            if not real_item:
                for inv_item in data["inventory"].keys():
                    if norm_input in self.normalize_name(inv_item):
                        real_item = inv_item
                        break

        if not real_item:
            return await ctx.send(f"❌ {ctx.author.mention}，您的行囊裡沒有找到與「**{clean_input}**」相符的道具喔！", delete_after=15.0)
            
        current_qty = data["inventory"].get(real_item, 0)
        if current_qty < use_qty:
            return await ctx.send(f"❌ {ctx.author.mention}，數量不足！您的行囊裡只有 **{current_qty}** 個 **{real_item}**。", delete_after=15.0)

        interactive_items = ["大當家的黑絲襪", "嗷嗷交配證", "樁·小花", "姑姑的絲帶抽打", "天賞石", "奇賞石", "足球", "審判小錘錘", "望月的襪子"]

        if real_item in interactive_items:
            if real_item == "嗷嗷交配證":
                data["inventory"][real_item] -= use_qty
                if data["inventory"][real_item] <= 0: del data["inventory"][real_item]
                save_users(users)
                
                mention_str = "<@845962912656261182>"
                
                qty_text = f"一口氣掏出了 **{use_qty}** 張閃亮亮的" if use_qty > 1 else "掏出了一張閃亮亮的"
                await ctx.send(f"📢 **{ctx.author.mention}** {qty_text}【嗷嗷交配證】！\n👉 {mention_str}，大爺/大娘點你台了，還不快點出來接客配種！💦")
                return
            return await ctx.send(f"💡 {ctx.author.mention}，**{real_item}** 現在已經全面升級為視覺化操作囉！\n👉 請直接輸入 `!使用` (不要加名稱)，並透過點擊包裹開啟選單來施展！", delete_after=30.0)

        redeemable_keywords = ["月卡", "1880券", "2880券", "卡", "券"]
        if any(kw in real_item for kw in redeemable_keywords) and real_item not in ["繪圖券", "改名卡"]:
            embed = discord.Embed(
                title="🎟️ 實體獎勵兌換中心",
                description=f"大俠，您正在申請兌換 **{real_item}**！\n請點擊下方按鈕，填寫您的遊戲帳號資料，小布會立刻幫您轉交給兩位當家處理！\n*(🧹 此畫面將於 2 分鐘後自動清理)*",
                color=0x5865F2
            )
            await ctx.send(content=f"{ctx.author.mention}", embed=embed, view=RedeemView(ctx.author.id, real_item, self.bot), delete_after=120.0)
        else:
            data["inventory"][real_item] -= use_qty
            if data["inventory"][real_item] <= 0: del data["inventory"][real_item]
            save_users(users)
            await ctx.send(f"🔧 **{ctx.author.mention}** 使用了 **{use_qty}** 個 **{real_item}**！*(目前此道具沒有特殊的自動效果喔)*", delete_after=60.0)

async def setup(bot):
    await bot.add_cog(ItemUse(bot))