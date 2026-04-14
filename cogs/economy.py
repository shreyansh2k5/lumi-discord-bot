# cogs/economy.py

import discord
from discord.ext import commands
from discord import app_commands
import random
from collections import Counter

from economy.transactions import (
    get_user_data, update_user_data,
    atomic_give, atomic_raid, atomic_purchase,
)
from economy.config import (
    DAILY_REWARD, BJ_MAX_BET, LUNA_NAME,
    STARTING_BALANCE, PET_SHOP, RAID_SUCCESS_CHANCE,
)
from economy.logic import (
    get_beg_earnings, process_flip,
    process_roll, calculate_raid_result,
)
from economy.ui import BlackjackView
from economy.transactions import db  # for leaderboard query
from core.embeds import send_intro, result_embed, PINK, GOLD, BLUE


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── HELP ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="help", description="Full list of Lumi commands 📖")
    async def help_command(self, ctx: commands.Context):
        embed = discord.Embed(
            title="✨  Lumi — Command Guide",
            description="Use `$command` or `/command` — both work!\nAdmin-only commands are marked with 🔒",
            color=PINK
        )
        embed.add_field(name="💰 Economy", value=(
            "`daily` — Claim 5,000 coins every 24h\n"
            "`beg` — Beg for random coins (5m cooldown)\n"
            "`balance` — Check your wallet\n"
            "`give <@user> <amt>` — Send coins to someone\n"
            "`profile` — View your stats & pets\n"
            "`leaderboard` — Top 10 richest users"
        ), inline=False)
        embed.add_field(name="🎲 Games", value=(
            "`blackjack <bet>` — Play 21 against Lumi\n"
            "`flip <bet>` — 50/50 coin flip\n"
            "`roll <bet>` — Roll a dice (6 = 6x jackpot!)\n"
            "`raid <@user>` — Steal up to 25% of their wallet"
        ), inline=False)
        embed.add_field(name="🛡️ Bank", value=(
            "`bank_deposit` — Safe Mode: immune to raids for 24h\n"
            "`bank_withdraw` — Leave Safe Mode"
        ), inline=False)
        embed.add_field(name="🐾 Pet Shop", value=(
            "`shop` — Browse available pets\n"
            "`shop buy <pet>` — Adopt a pet"
        ), inline=False)
        embed.add_field(name="🎵 Music", value=(
            "`play <song/URL>` — Play from YouTube\n"
            "`play` — Show all music commands\n"
            "`search <query>` — Pick from 5 results\n"
            "`skip` — Skip current song\n"
            "`pause` / `resume` — Toggle pause\n"
            "`remove` — Remove last queued song"
        ), inline=False)
        embed.add_field(name="ℹ️ Server", value=(
            "`/status` — Lumi's uptime & latency\n"
            "`/server_info` — Info about this server"
        ), inline=False)
        embed.add_field(name="🔒 Admin Only", value=(
            "`/mute` `/unmute` `/kick` `/ban`\n"
            "`/badword` — Manage word filter\n"
            "`/deadchat` — Configure dead chat revival\n"
            "`/exception` — Manage filter-exempt roles"
        ), inline=False)
        embed.set_footer(text="Tip: @mention or reply to Lumi to chat with her! 🌸")
        await ctx.send(embed=embed)

    # ── DAILY ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="daily", description="Claim your daily coins 🎁")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx: commands.Context):
        intro = await send_intro(ctx, "🎁", "Daily Reward", f"*Checking your account, {ctx.author.display_name}...*")
        user_id = str(ctx.author.id)
        data    = await get_user_data(user_id)
        new_bal = data["coins"] + DAILY_REWARD
        await update_user_data(user_id, {"coins": new_bal})
        await intro.edit(embed=result_embed(
            "🎁  Daily Reward Claimed!",
            f"**+`{DAILY_REWARD:,}` {LUNA_NAME}** added!\n\n💰 New balance: `{new_bal:,}` {LUNA_NAME}\n⏰ Come back in **24 hours**.",
            author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)
        ))

    # ── BEG ───────────────────────────────────────────────────────

    @commands.hybrid_command(name="beg", description="Beg for some coins 🙏")
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def beg(self, ctx: commands.Context):
        intro = await send_intro(ctx, "🙏", "Begging...", f"*{ctx.author.display_name} holds out their hand...*")
        amt     = get_beg_earnings()
        data    = await get_user_data(str(ctx.author.id))
        new_bal = data["coins"] + amt
        await update_user_data(str(ctx.author.id), {"coins": new_bal})
        await intro.edit(embed=result_embed(
            "🙏  Someone was generous!",
            f"You received **`{amt:,}` {LUNA_NAME}**!\n\n💰 New balance: `{new_bal:,}` {LUNA_NAME}",
            author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)
        ))

    # ── FLIP ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="flip", description="Flip a coin — double or nothing 🪙")
    async def flip(self, ctx: commands.Context, amount: int):
        data = await get_user_data(str(ctx.author.id))
        if amount <= 0 or data["coins"] < amount:
            return await ctx.send(embed=discord.Embed(description="❌ You don't have enough coins!", color=discord.Color.red()), ephemeral=True)
        intro = await send_intro(ctx, "🪙", "Coin Flip", f"*{ctx.author.display_name} flips a coin for `{amount:,}` {LUNA_NAME}...*", color=GOLD)
        win, delta = process_flip(amount)
        new_bal    = data["coins"] + delta
        await update_user_data(str(ctx.author.id), {"coins": new_bal})
        await intro.edit(embed=result_embed(
            "🪙  Heads! You Win!" if win else "🪙  Tails! You Lose!",
            (f"✅ **+`{amount:,}` {LUNA_NAME}**\n\n💰 New balance: `{new_bal:,}` {LUNA_NAME}" if win
             else f"❌ **-`{amount:,}` {LUNA_NAME}**\n\n💰 New balance: `{new_bal:,}` {LUNA_NAME}"),
            color=discord.Color.green() if win else discord.Color.red(),
            author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)
        ))

    # ── ROLL ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="roll", description="Roll a dice — jackpot on 6 🎲")
    async def roll(self, ctx: commands.Context, amount: int):
        data = await get_user_data(str(ctx.author.id))
        if amount <= 0 or data["coins"] < amount:
            return await ctx.send(embed=discord.Embed(description="❌ You don't have enough coins!", color=discord.Color.red()), ephemeral=True)
        intro = await send_intro(ctx, "🎲", "Dice Roll", f"*{ctx.author.display_name} shakes the dice for `{amount:,}` {LUNA_NAME}...*", color=GOLD)
        val, jackpot, delta = process_roll(amount)
        new_bal = data["coins"] + delta
        await update_user_data(str(ctx.author.id), {"coins": new_bal})
        if jackpot:
            await intro.edit(embed=result_embed("🎲  JACKPOT! Rolled a 6!", f"🎉 **+`{delta:,}` {LUNA_NAME}** (6x payout!)\n\n💰 New balance: `{new_bal:,}` {LUNA_NAME}", color=discord.Color.gold(), author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))
        else:
            await intro.edit(embed=result_embed(f"🎲  Rolled a {val}", f"❌ **-`{amount:,}` {LUNA_NAME}**\n\n💰 New balance: `{new_bal:,}` {LUNA_NAME}\n*Roll a 6 for a 6x jackpot!*", color=discord.Color.red(), author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))

    # ── BLACKJACK ─────────────────────────────────────────────────

    @commands.hybrid_command(name="blackjack", description="Play a game of Blackjack 🃏")
    async def blackjack(self, ctx: commands.Context, bet: int):
        data = await get_user_data(str(ctx.author.id))
        if bet < 10 or bet > BJ_MAX_BET or data["coins"] < bet:
            return await ctx.send(embed=discord.Embed(description=f"❌ Bet must be between `10` and `{BJ_MAX_BET:,}` {LUNA_NAME}, and you must have the funds.", color=discord.Color.red()), ephemeral=True)
        intro = await send_intro(ctx, "🃏", "Blackjack", f"*Dealer shuffling for {ctx.author.display_name}...*\n`Bet: {bet:,} {LUNA_NAME}`", color=BLUE)
        await intro.delete()
        view  = BlackjackView(ctx, str(ctx.author.id), bet, data)
        embed = discord.Embed(title="🃏  Blackjack", color=BLUE)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Your Hand",   value=f"{view.player_hand} ({view.get_score(view.player_hand)})")
        embed.add_field(name="Dealer",      value=f"[{view.dealer_hand[0]}, ?]")
        embed.set_footer(text=f"Bet: {bet:,} {LUNA_NAME} • Lumi Economy ✨")
        await ctx.send(embed=embed, view=view)

    # ── RAID ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="raid", description="Steal coins from another user 🥷")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def raid(self, ctx: commands.Context, target: discord.User):
        if target.id == ctx.author.id:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=discord.Embed(description="❌ You can't raid yourself!", color=discord.Color.red()))
        intro = await send_intro(ctx, "🥷", "Raid", f"*{ctx.author.display_name} sneaks toward {target.display_name}'s vault...*", color=discord.Color.dark_grey())
        r_id, t_id = str(ctx.author.id), str(target.id)
        r_d, t_d   = await get_user_data(r_id), await get_user_data(t_id)
        if r_d["isBanked"] or t_d.get("isBanked"):
            ctx.command.reset_cooldown(ctx)
            return await intro.edit(embed=result_embed("🛡️  Raid Blocked!", "Safe Mode is active. No coins moved.", color=BLUE))
        success = random.random() < RAID_SUCCESS_CHANCE
        amt     = calculate_raid_result(r_d["coins"], t_d["coins"], success)
        await atomic_raid(r_id, t_id, amt, success)
        if success:
            await intro.edit(embed=result_embed("🥷  Raid Successful!", f"You stole **`{amt:,}` {LUNA_NAME}** from {target.mention}!\n\n⏰ Next raid available in **1 hour**.", color=discord.Color.green(), author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))
        else:
            await intro.edit(embed=result_embed("😵  Caught!", f"You paid {target.mention} **`{amt:,}` {LUNA_NAME}** as hush money.\n\n⏰ Try again in **1 hour**.", color=discord.Color.red(), author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))

    # ── GIVE ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="give", description="Send coins to another user 💸")
    async def give(self, ctx: commands.Context, target: discord.User, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ Amount must be positive.", color=discord.Color.red()))
        intro   = await send_intro(ctx, "💸", "Transferring Coins", f"*Sending `{amount:,}` {LUNA_NAME} to {target.display_name}...*")
        
        is_sender_owner = await self.bot.is_owner(ctx.author)
        is_receiver_owner = await self.bot.is_owner(target)
        
        success, msg = await atomic_give(str(ctx.author.id), str(target.id), amount, is_sender_owner, is_receiver_owner)
        if success:
            await intro.edit(embed=result_embed("💸  Transfer Complete!", f"Sent **`{amount:,}` {LUNA_NAME}** to {target.mention}!", color=discord.Color.green(), author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))
        else:
            await intro.edit(embed=result_embed("❌  Transfer Failed", msg, color=discord.Color.red()))

    # ── BALANCE ───────────────────────────────────────────────────

    @commands.hybrid_command(name="balance", description="Check your coin balance 💰")
    async def balance(self, ctx: commands.Context, user: discord.User = None):
        target = user or ctx.author
        intro  = await send_intro(ctx, "💰", "Checking Balance", f"*Fetching {target.display_name}'s account...*")
        data   = await get_user_data(str(target.id))
        e      = result_embed("💰  Wallet", f"**`{data['coins']:,}` {LUNA_NAME}**")
        e.add_field(name="Status", value="🛡️ Safe Mode" if data.get("isBanked") else "⚔️ Raid Mode")
        e.set_author(name=target.display_name, icon_url=str(target.display_avatar.url))
        e.set_thumbnail(url=str(target.display_avatar.url))
        await intro.edit(embed=e)

    # ── PROFILE ───────────────────────────────────────────────────

    @commands.hybrid_command(name="profile", description="View your full profile 🌸")
    async def profile(self, ctx: commands.Context, user: discord.User = None):
        target = user or ctx.author
        intro  = await send_intro(ctx, "🌸", "Loading Profile", f"*Pulling up {target.display_name}'s profile...*")
        data   = await get_user_data(str(target.id))
        pets   = data.get("pets", [])
        pet_txt = (
            "\n".join(f"{PET_SHOP.get(p, {}).get('emoji', '🐾')} {p.capitalize()} (x{c})" for p, c in Counter(pets).items())
            if pets else "None yet — visit `/shop`!"
        )
        e = result_embed(f"🌸  {target.display_name}'s Profile", "")
        e.add_field(name="💰 Balance", value=f"`{data['coins']:,}` {LUNA_NAME}", inline=False)
        e.add_field(name="🚦 Status",  value="🛡️ Safe Mode" if data.get("isBanked") else "⚔️ Raid Mode", inline=True)
        e.add_field(name="🐾 Pets",    value=pet_txt, inline=False)
        if target.avatar: e.set_thumbnail(url=target.avatar.url)
        await intro.edit(embed=e)

    # ── BANK DEPOSIT ──────────────────────────────────────────────

    @commands.hybrid_command(name="bank_deposit", description="Activate Safe Mode 🛡️")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def bank_deposit(self, ctx: commands.Context):
        data = await get_user_data(str(ctx.author.id))
        if data.get("isBanked"):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=result_embed("🛡️  Already in Safe Mode", "You are already protected!", color=BLUE))
        intro = await send_intro(ctx, "🛡️", "Activating Safe Mode", f"*Locking {ctx.author.display_name}'s vault...*", color=BLUE)
        await update_user_data(str(ctx.author.id), {"isBanked": True})
        await intro.edit(embed=result_embed("🛡️  Safe Mode Activated!", "Your coins are now **protected from raids**.\n⚠️ You also cannot raid others.\n⏰ Withdrawable after **24 hours**.", color=BLUE, author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))

    # ── BANK WITHDRAW ─────────────────────────────────────────────

    @commands.hybrid_command(name="bank_withdraw", description="Deactivate Safe Mode 🔓")
    async def bank_withdraw(self, ctx: commands.Context):
        intro = await send_intro(ctx, "🔓", "Deactivating Safe Mode", f"*Unlocking {ctx.author.display_name}'s vault...*", color=GOLD)
        await update_user_data(str(ctx.author.id), {"isBanked": False})
        await intro.edit(embed=result_embed("🔓  Safe Mode Deactivated!", "You are back in **Raid Mode**.\n⚔️ You can raid and be raided again!", color=GOLD, author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))

    # ── SHOP ──────────────────────────────────────────────────────

    @commands.hybrid_group(name="shop", fallback="list")
    async def shop(self, ctx: commands.Context):
        intro = await send_intro(ctx, "🐾", "Lumi's Pet Shop", "*Browsing the shop...*")
        sorted_pets = sorted(PET_SHOP.items(), key=lambda x: x[1]["price"])
        lines = [
            f"`{i:>2}.` {info['emoji']} **{name.capitalize()}** — `{info['price']:,}` {LUNA_NAME}"
            for i, (name, info) in enumerate(sorted_pets, start=1)
        ]
        e = discord.Embed(
            title="🐾  Lumi's Pet Shop",
            description="Sorted by price · Use `$shop buy <pet>` to adopt!\n\n" + "\n".join(lines),
            color=PINK
        )
        e.set_footer(text="Lumi Economy ✨")
        await intro.edit(embed=e)

    @shop.command(name="buy")
    async def buy_pet(self, ctx: commands.Context, pet: str):
        pet = pet.lower().strip()
        if pet not in PET_SHOP:
            return await ctx.send(embed=discord.Embed(description="❌ That pet doesn't exist!", color=discord.Color.red()))
        info  = PET_SHOP[pet]
        intro = await send_intro(ctx, info["emoji"], f"Buying {pet.capitalize()}", f"*Processing purchase of `{pet.capitalize()}` for `{info['price']:,}` {LUNA_NAME}...*")
        ok    = await atomic_purchase(str(ctx.author.id), pet, info["price"])
        if ok:
            await intro.edit(embed=result_embed(f"{info['emoji']}  Purchase Successful!", f"You adopted a **{pet.capitalize()}**! 🎉\nView it with `/profile`.", color=discord.Color.green(), author_name=ctx.author.display_name, author_icon=str(ctx.author.display_avatar.url)))
        else:
            await intro.edit(embed=result_embed("❌  Not Enough Coins", f"You need `{info['price']:,}` {LUNA_NAME}.", color=discord.Color.red()))

    # ── LEADERBOARD ───────────────────────────────────────────────

    @commands.hybrid_command(name="leaderboard", description="Top 10 richest users 🏆")
    async def leaderboard(self, ctx: commands.Context):
        intro = await send_intro(ctx, "🏆", "Loading Leaderboard", "*Counting everyone's coins...*", color=GOLD)
        docs  = await db.collection("users").order_by("coins", direction="DESCENDING").limit(10).get()
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, doc in enumerate(docs, start=1):
            u    = self.bot.get_user(int(doc.id))
            name = u.name if u else f"User_{doc.id[:5]}"
            medal = medals[i - 1] if i <= 3 else f"`#{i}`"
            lines.append(f"{medal} **{name}** — `{doc.to_dict().get('coins', 0):,}` {LUNA_NAME}")
        e = discord.Embed(title="🏆  Top 10 Richest Users", description="\n".join(lines) or "*No users found.*", color=GOLD)
        e.set_footer(text="Lumi Economy ✨")
        await intro.edit(embed=e)


async def setup(bot):
    await bot.add_cog(Economy(bot))
