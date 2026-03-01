# economy/ui.py
# Discord UI components for economy games (buttons, views, etc.)

import discord
import random

from economy.transactions import update_user_data
from economy.config import LUNA_NAME, BJ_PAYOUT, BJ_BLACKJACK_PAYOUT


class BlackjackView(discord.ui.View):
    """Interactive Hit / Stand buttons for the Blackjack game."""

    def __init__(self, ctx, user_id: str, bet: int, user_data: dict):
        super().__init__(timeout=60)
        self.ctx       = ctx
        self.user_id   = user_id
        self.bet       = bet
        self.user_data = user_data

        # Standard deck (Aces = 11, face cards = 10)
        self.deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(self.deck)

        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    def get_score(self, hand: list[int]) -> int:
        """Calculates hand total, converting Aces from 11→1 when needed."""
        score = sum(hand)
        aces  = hand.count(11)
        while score > 21 and aces:
            score -= 10
            aces  -= 1
        return score

    async def end_game(self, interaction: discord.Interaction, result_text: str, color: discord.Color):
        """Finalises the game, updates balance, and shows the result embed."""
        new_bal      = self.user_data["coins"]
        player_score = self.get_score(self.player_hand)

        result_lower = result_text.lower()
        if "won" in result_lower or "busts" in result_lower:
            # Natural blackjack (21 in 2 cards) pays 2.5x; otherwise 2x
            payout   = int(self.bet * (BJ_BLACKJACK_PAYOUT if player_score == 21 and len(self.player_hand) == 2 else BJ_PAYOUT))
            new_bal += payout - self.bet
        elif "push" in result_lower or "tie" in result_lower:
            pass  # Coins returned — no change
        else:
            new_bal -= self.bet

        await update_user_data(self.user_id, {"coins": new_bal})

        embed = discord.Embed(title="🃏  Blackjack Results", description=result_text, color=color)
        embed.add_field(name="Your Hand",  value=f"{self.player_hand} (Total: {player_score})")
        embed.add_field(name="Lumi's Hand", value=f"{self.dealer_hand} (Total: {self.get_score(self.dealer_hand)})")
        embed.set_footer(text=f"💰 New balance: {new_bal:,} {LUNA_NAME}")

        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)

        self.player_hand.append(self.deck.pop())
        if self.get_score(self.player_hand) > 21:
            await self.end_game(interaction, "💥 **Bust!** You went over 21. Lumi wins!", discord.Color.red())
        else:
            await self._update_board(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.grey)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)

        while self.get_score(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        p = self.get_score(self.player_hand)
        d = self.get_score(self.dealer_hand)

        if   d > 21:  await self.end_game(interaction, "🎊 **Lumi Busts!** You won!", discord.Color.green())
        elif p > d:   await self.end_game(interaction, "🏆 **You won!** Your hand was stronger.", discord.Color.green())
        elif p < d:   await self.end_game(interaction, "📉 **Lumi wins!** Better luck next time.", discord.Color.red())
        else:         await self.end_game(interaction, "🤝 **Push!** It's a tie — coins returned.", discord.Color.orange())

    async def _update_board(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🃏  Blackjack", description=f"Bet: `{self.bet:,}` {LUNA_NAME}", color=discord.Color.blue())
        embed.add_field(name="Your Hand",  value=f"{self.player_hand} (Score: {self.get_score(self.player_hand)})")
        embed.add_field(name="Lumi's Hand", value=f"[{self.dealer_hand[0]}, ?]")
        await interaction.response.edit_message(embed=embed, view=self)
