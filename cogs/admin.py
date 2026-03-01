# cogs/admin.py
# Owner-only hidden commands for managing the economy.

import os
import discord
from discord.ext import commands

from economy.transactions import get_user_data, update_user_data
from economy.config import STARTING_BALANCE


class AdminTools(commands.Cog):
    def __init__(self, bot):
        self.bot     = bot
        self.owner_id = int(os.getenv("BOT_OWNER_ID", 0))

    def _is_owner(self, ctx: commands.Context) -> bool:
        return ctx.author.id == self.owner_id

    @commands.command(name="add_coins", hidden=True)
    async def add_coins(self, ctx: commands.Context, user: discord.User, amount: int):
        if not self._is_owner(ctx): return
        data = await get_user_data(str(user.id))
        await update_user_data(str(user.id), {"coins": data["coins"] + amount})
        await ctx.message.delete()
        await ctx.send(f"✅ Added `{amount:,}` to **{user.name}**.", delete_after=5)

    @commands.command(name="deduct_coins", hidden=True)
    async def deduct_coins(self, ctx: commands.Context, user: discord.User, amount: int):
        if not self._is_owner(ctx): return
        data    = await get_user_data(str(user.id))
        new_bal = max(0, data["coins"] - amount)
        await update_user_data(str(user.id), {"coins": new_bal})
        await ctx.message.delete()
        await ctx.send(f"✅ Deducted `{amount:,}` from **{user.name}**.", delete_after=5)

    @commands.command(name="set_coins", hidden=True)
    async def set_coins(self, ctx: commands.Context, user: discord.User, amount: int):
        if not self._is_owner(ctx): return
        await update_user_data(str(user.id), {"coins": amount})
        await ctx.message.delete()
        await ctx.send(f"✅ Set **{user.name}**'s balance to `{amount:,}`.", delete_after=5)

    @commands.command(name="reset_user", hidden=True)
    async def reset_user(self, ctx: commands.Context, user: discord.User):
        if not self._is_owner(ctx): return
        await update_user_data(str(user.id), {"coins": STARTING_BALANCE, "pets": [], "isBanked": False})
        await ctx.message.delete()
        await ctx.send(f"🧹 Reset profile for **{user.name}**.", delete_after=5)


async def setup(bot):
    await bot.add_cog(AdminTools(bot))
