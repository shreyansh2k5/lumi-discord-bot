# cogs/deadchat_cmds.py

import discord
from discord import app_commands
from discord.ext import commands
import moderation.automod as automod


# ── Interval preset options ─────────────────────────────────────────
INTERVAL_PRESETS = [
    ("10 minutes",  10),
    ("30 minutes",  30),
    ("1 hour",      60),
    ("2 hours",    120),
    ("3 hours",    180),
    ("6 hours",    360),
    ("12 hours",   720),
    ("24 hours",  1440),
]


def _fmt_minutes(minutes: int) -> str:
    if minutes >= 60 and minutes % 60 == 0:
        return f"{minutes // 60}h"
    elif minutes >= 60:
        return f"{minutes // 60}h {minutes % 60}m"
    return f"{minutes}m"


def _build_embed(guild: discord.Guild, gs: dict, *, saved: bool = False) -> discord.Embed:
    ids = automod.get_revive_channels(guild.id, gs)
    if ids:
        parts = []
        for cid in ids:
            ch = guild.get_channel(cid)
            parts.append(ch.mention if ch else f"~~`{cid}`~~ *(deleted)*")
        channels_str = "\n".join(f"• {p}" for p in parts)
    else:
        channels_str = "*None configured*"

    minutes = automod.get_revive_threshold(guild.id, gs)
    threshold_str = _fmt_minutes(minutes)

    desc = (
        "✅ **Settings saved!** Here's your updated configuration."
        if saved
        else "Use the menus below to update settings, then press **💾 Save**.\nUnchanged fields keep their current values."
    )

    embed = discord.Embed(
        title="💬  Dead Chat Configuration",
        description=desc,
        color=discord.Color.from_rgb(180, 140, 255),
    )
    embed.add_field(
        name="⏱️ Silence Interval",
        value=f"`{threshold_str}` of inactivity before Lumi revives chat",
        inline=False,
    )
    embed.add_field(
        name="📢 Revival Channels",
        value=channels_str,
        inline=False,
    )
    if not saved:
        embed.set_footer(text="Changes apply only when you click Save  •  Times out in 2 minutes")
    return embed


# ── UI Components ───────────────────────────────────────────────────

class IntervalSelect(discord.ui.Select):
    def __init__(self, current_minutes: int):
        options = [
            discord.SelectOption(
                label=label,
                value=str(value),
                default=(value == current_minutes),
            )
            for label, value in INTERVAL_PRESETS
        ]
        super().__init__(
            placeholder="⏱️ Change silence interval…",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_interval = int(self.values[0])
        for opt in self.options:
            opt.default = (opt.value == self.values[0])
        await interaction.response.edit_message(view=self.view)


class AddChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="➕ Add revival channel(s)…",
            min_values=1,
            max_values=25,
            channel_types=[discord.ChannelType.text],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_add_channels = [c.id for c in self.values]
        await interaction.response.edit_message(view=self.view)


class RemoveChannelSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild, current_ids: list[int]):
        if current_ids:
            options = []
            for cid in current_ids:
                ch = guild.get_channel(cid)
                name = f"#{ch.name}" if ch else f"deleted-{cid}"
                options.append(discord.SelectOption(label=name, value=str(cid)))
            disabled = False
        else:
            options = [discord.SelectOption(label="No channels configured", value="__none__")]
            disabled = True

        super().__init__(
            placeholder="🗑️ Remove revival channel(s)…",
            min_values=1,
            max_values=len(options),
            options=options,
            disabled=disabled,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_remove_channels = [
            int(v) for v in self.values if v != "__none__"
        ]
        await interaction.response.edit_message(view=self.view)


class SaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="💾  Save Settings",
            style=discord.ButtonStyle.success,
            row=4,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: DeadChatConfigView = self.view

        guild_id = interaction.guild_id
        await automod.ensure_guild_settings_in_cache(guild_id)
        gs = automod._guild_settings_cache.get(guild_id)

        # Apply pending changes
        if view.pending_interval is not None:
            await automod.set_revive_threshold(guild_id, view.pending_interval, gs)

        for cid in view.pending_add_channels:
            await automod.add_revive_channel(guild_id, cid, gs)

        for cid in view.pending_remove_channels:
            await automod.remove_revive_channel(guild_id, cid, gs)

        # Disable all components and stop the view
        for item in view.children:
            item.disabled = True
        view.stop()

        embed = _build_embed(interaction.guild, gs, saved=True)
        await interaction.edit_original_response(embed=embed, view=view)


# ── View ────────────────────────────────────────────────────────────

class DeadChatConfigView(discord.ui.View):
    def __init__(self, guild: discord.Guild, gs: dict, interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.pending_interval: int | None = None
        self.pending_add_channels: list[int] = []
        self.pending_remove_channels: list[int] = []

        current_minutes = automod.get_revive_threshold(guild.id, gs)
        current_channels = automod.get_revive_channels(guild.id, gs)

        self.add_item(IntervalSelect(current_minutes))
        self.add_item(AddChannelSelect())
        self.add_item(RemoveChannelSelect(guild, current_channels))
        self.add_item(SaveButton())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.interaction.edit_original_response(view=self)
        except Exception:
            pass


# ── Cog ─────────────────────────────────────────────────────────────

class DeadChatCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="deadchat_configuration",
        description="View and configure Lumi's dead-chat revival settings 💬",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def deadchat_configuration(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)

        embed = _build_embed(interaction.guild, gs)
        view = DeadChatConfigView(interaction.guild, gs, interaction)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @deadchat_configuration.error
    async def _config_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need the **Manage Server** permission to use this command.",
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(DeadChatCmds(bot))
