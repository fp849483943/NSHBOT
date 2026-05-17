import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from utils import load_config, save_config, load_users, save_users, get_user_data

config_data = load_config()

# ==========================================
# 🔢 數量輸入彈出視窗 (Modal)
# ==========================================
class QtyModal(discord.ui.Modal):
    def __init__(self, action, item_name, price, item_type="normal"):
        title_str = f"購買 {item_name}" if action == "buy" else f"賣出 {item_name}"
        super().__init__(title=title_str)
        self.action = action
        self.item_name = item_name
        self.price = price
        self.item_type = item_type
        
        self.qty_input = discord.ui.TextInput(
            label="請輸入數量",
            default="1",
            required=True,
            max_length=4,
            placeholder="請輸入正整數，例如: 10"
        )
        self.add_item(self.qty_input)

    # 核心黑科技：直接「編輯」背後的下拉選單訊息，讓選單瞬間替換成結果，並在 5 秒後刪除
    async def _send_result(self, interaction: discord.Interaction, content: str):
        await interaction.response.edit_message(content=content, view=None)
        await asyncio.sleep(5.0)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty_input.value)
            if qty <= 0: raise ValueError
        except:
            return await self._send_result(interaction, "❌ 數量請輸入正整數！")
        
        users = load_users()
        data = get_user_data(interaction.user.id, users)
        config = load_config()
        
        if self.action == "buy":
            # 檢查黑市庫存
            stock = float('inf')
            if self.item_type == "hidden":
                val = config.get("hidden_shop_items", {}).get(self.item_name)
                if val and isinstance(val, str) and ':' in val:
                    stock = int(val.split(':', 1)[1])
                    if qty > stock:
                        return await self._send_result(interaction, f"❌ 黑市庫存不足！該物品僅剩 **{stock}** 個。")

            total_cost = self.price * qty
            if data["coins"] < total_cost:
                return await self._send_result(interaction, f"❌ 銅幣不足！需要 **{total_cost}** 銅幣，您只有 **{data['coins']}** 銅幣。")
                
            data["coins"] -= total_cost
            data["inventory"][self.item_name] = data["inventory"].get(self.item_name, 0) + qty
            
            # 更新庫存
            if self.item_type == "hidden" and stock != float('inf'):
                config["hidden_shop_items"][self.item_name] = f"{self.price}:{stock - qty}"
                save_config(config)
                
            save_users(users)
            await self._send_result(interaction, f"🛒 **購買成功！**\n花費了 **{total_cost}** 銅幣，獲得 **{self.item_name}** x{qty}。\n💰 您的剩餘銅幣：**{data['coins']}**")
            
        elif self.action == "sell":
            current_qty = data["inventory"].get(self.item_name, 0)
            if current_qty < qty:
                return await self._send_result(interaction, f"❌ 你的背包裡沒有那麼多 **{self.item_name}**！(目前擁有: {current_qty} 個)")
                
            total_earn = self.price * qty
            data["inventory"][self.item_name] -= qty
            if data["inventory"][self.item_name] <= 0:
                del data["inventory"][self.item_name]
                
            data["coins"] += total_earn
            save_users(users)
            await self._send_result(interaction, f"⚖️ **回收成功！**\n賣出了 **{self.item_name}** x{qty}，獲得 **{total_earn}** 銅幣。\n💰 您的目前銅幣：**{data['coins']}**")

# ==========================================
# 🔽 購買與回收的下拉選單 (Select)
# ==========================================
class BuySelectView(discord.ui.View):
    def __init__(self, current_coins):
        super().__init__(timeout=60)
        config = load_config()
        options = []
        
        for item, price in config.get("shop_items", {}).items():
            options.append(discord.SelectOption(label=item, description=f"售價: {price} 銅幣", value=f"normal|{item}|{price}", emoji="📦"))
        
        if datetime.now().weekday() == 3:
            for item, val in config.get("hidden_shop_items", {}).items():
                if isinstance(val, str) and ':' in val:
                    p, s = val.split(':', 1)
                    options.append(discord.SelectOption(label=item, description=f"【黑市】售價: {p} 銅幣 (限量: {s})", value=f"hidden|{item}|{p}", emoji="🕵️‍♂️"))
                else:
                    options.append(discord.SelectOption(label=item, description=f"【黑市】售價: {val} 銅幣", value=f"hidden|{item}|{val}", emoji="🕵️‍♂️"))
        
        if not options:
            options.append(discord.SelectOption(label="目前沒有商品", value="none"))

        select = discord.ui.Select(placeholder=f"👇 請選擇商品 (您的銅幣: {current_coins})", options=options[:25])
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        val = self.children[0].values[0]
        if val == "none":
            await interaction.response.edit_message(content="❌ 目前沒有商品可購買。", view=None)
            await asyncio.sleep(5.0)
            try: await interaction.delete_original_response()
            except: pass
            return
        
        item_type, item_name, price = val.split('|')
        await interaction.response.send_modal(QtyModal(action="buy", item_name=item_name, price=int(price), item_type=item_type))


class SellSelectView(discord.ui.View):
    def __init__(self, inventory):
        super().__init__(timeout=60)
        config = load_config()
        options = []
        sell_prices = config.get("sell_prices", {})
        
        for item, qty in inventory.items():
            if qty > 0 and item in sell_prices:
                price = sell_prices[item]
                options.append(discord.SelectOption(label=item, description=f"您持有 {qty} 個 | 收購價: {price} 銅幣", value=f"{item}|{price}", emoji="💰"))
                
        if not options:
            options.append(discord.SelectOption(label="您的背包沒有可回收的商品", value="none"))

        select = discord.ui.Select(placeholder="👇 請點擊選擇要賣出的商品", options=options[:25])
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        val = self.children[0].values[0]
        if val == "none":
            await interaction.response.edit_message(content="❌ 目前沒有商品可回收。", view=None)
            await asyncio.sleep(5.0)
            try: await interaction.delete_original_response()
            except: pass
            return
        
        item_name, price = val.split('|')
        await interaction.response.send_modal(QtyModal(action="sell", item_name=item_name, price=int(price)))

# ==========================================
# 🔘 商店主面板 (Buttons)
# ==========================================
class ShopView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=120)
        self.author_id = author_id

    @discord.ui.button(label="🛒 購買道具", style=discord.ButtonStyle.success)
    async def btn_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 請自己輸入商店指令來使用喔！", ephemeral=True, delete_after=5.0)
            
        users = load_users()
        data = get_user_data(interaction.user.id, users)
        await interaction.response.send_message("請選擇您要 **購買** 的商品：", view=BuySelectView(data["coins"]), ephemeral=True, delete_after=45.0)

    @discord.ui.button(label="⚖️ 回收道具", style=discord.ButtonStyle.primary)
    async def btn_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ 請自己輸入商店指令來使用喔！", ephemeral=True, delete_after=5.0)
            
        users = load_users()
        data = get_user_data(interaction.user.id, users)
        await interaction.response.send_message("請選擇您要 **賣出** 的商品：", view=SellSelectView(data["inventory"]), ephemeral=True, delete_after=45.0)


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name=config_data.get('cmd_shop', '商店'))
    async def shop(self, ctx):
        try: await ctx.message.delete(delay=120.0)
        except: pass
        
        config = load_config()
        embed = discord.Embed(title="🛒 萬事屋商行", description="歡迎光臨！請點擊下方按鈕進行交易：", color=0x5865F2)
        
        normal_items = config.get("shop_items", {})
        if normal_items:
            desc = ""
            for item, price in normal_items.items():
                desc += f"🔸 **{item}** —— `{price}` 銅幣\n"
            embed.add_field(name="【常駐商品】", value=desc, inline=False)
            
        if datetime.now().weekday() == 3:
            hidden_items = config.get("hidden_shop_items", {})
            if hidden_items:
                desc = ""
                for item, val in hidden_items.items():
                    if isinstance(val, str) and ':' in val:
                        p, s = val.split(':', 1)
                        desc += f"🕵️‍♂️ **{item}** —— `{p}` 銅幣 (全服限量: {s}個)\n"
                    else:
                        desc += f"🕵️‍♂️ **{item}** —— `{val}` 銅幣\n"
                embed.add_field(name="🌚 【黑市商人】 (星期四限定)", value=desc, inline=False)
                
        embed.set_footer(text="💡 點擊下方按鈕開啟選單，交易過程只有您自己能看見！\n*(🧹 此商店畫面將於 2 分鐘後自動清理)*")
        
        await ctx.reply(embed=embed, view=ShopView(ctx.author.id), delete_after=120.0)

async def setup(bot):
    await bot.add_cog(Shop(bot))