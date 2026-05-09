# cogs/automod_cmds.py

import discord
from discord import app_commands
from discord.ext import commands
import moderation.automod as automod


# ── Helpers ─────────────────────────────────────────────────────────

def _build_badword_embed(guild: discord.Guild, gs: dict, *, saved: bool = False) -> discord.Embed:
    words = sorted(gs.get("bad_words", set()))
    roles = sorted(gs.get("exempt_roles", set()))

    words_str = (
        ", ".join(f"`{w}`" for w in words)
        if words
        else "*None configured*"
    )
    roles_str = (
        ", ".join(f"`{r}`" for r in roles)
        if roles
        else "*None configured*"
    )

    desc = (
        "✅ **Settings saved!** Here's your updated configuration."
        if saved
        else (
            "• Click **➕ Add Words** to open a text box and type words to ban.\n"
            "• Use the **🗑️ Remove** dropdown to delete existing words.\n"
            "• Use the **🛡️ Exempt Role** dropdown to toggle role exemptions.\n"
            "• Press **💾 Save** to apply all pending changes."
        )
    )

    embed = discord.Embed(
        title="🚫  Bad Word Configuration",
        description=desc,
        color=discord.Color.from_rgb(255, 120, 120),
    )
    embed.add_field(name="🚫 Blocked Words", value=words_str, inline=False)
    embed.add_field(name="🛡️ Exempt Roles", value=roles_str, inline=False)
    if not saved:
        embed.set_footer(text="Changes apply only when you click Save  •  Times out in 2 minutes")
    return embed


# ── Add Words Modal ──────────────────────────────────────────────────

class AddWordsModal(discord.ui.Modal, title="➕ Add Bad Words"):
    words_input = discord.ui.TextInput(
        label="Words to ban (comma-separated)",
        placeholder="e.g.  slur1, slur2, offensive-phrase",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    def __init__(self, view: "BadWordConfigView"):
        super().__init__()
        self._config_view = view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.words_input.value
        new_words = [w.strip().lower() for w in raw.split(",") if w.strip()]
        # Store pending adds (duplicates filtered at save time)
        self._config_view.pending_add_words.extend(new_words)
        # Deduplicate
        self._config_view.pending_add_words = list(dict.fromkeys(self._config_view.pending_add_words))
        preview = ", ".join(f"`{w}`" for w in self._config_view.pending_add_words)
        await interaction.response.send_message(
            f"📝 Queued to add: {preview}\nPress **💾 Save** to apply.",
            ephemeral=True,
        )


# ── Add Words Button ─────────────────────────────────────────────────

class AddWordsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="➕  Add Words",
            style=discord.ButtonStyle.primary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddWordsModal(self.view))


# ── Remove Words Select ──────────────────────────────────────────────

class RemoveWordSelect(discord.ui.Select):
    def __init__(self, current_words: list[str]):
        if current_words:
            options = [
                discord.SelectOption(label=w, value=w)
                for w in current_words[:25]          # Discord cap: 25 options
            ]
            disabled = False
        else:
            options = [discord.SelectOption(label="No words configured", value="__none__")]
            disabled = True

        super().__init__(
            placeholder="🗑️ Select words to remove…",
            min_values=1,
            max_values=len(options),
            options=options,
            disabled=disabled,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_remove_words = [v for v in self.values if v != "__none__"]
        # Highlight chosen options
        chosen = set(self.view.pending_remove_words)
        for opt in self.options:
            opt.default = opt.value in chosen
        await interaction.response.edit_message(view=self.view)


# ── Exempt Role Select ───────────────────────────────────────────────

class ExemptRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="🛡️ Toggle exempt role(s)…",
            min_values=1,
            max_values=25,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.pending_exempt_roles = [r.name for r in self.values]
        await interaction.response.edit_message(view=self.view)


# ── Save Button ──────────────────────────────────────────────────────

class SaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="💾  Save Settings",
            style=discord.ButtonStyle.success,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: BadWordConfigView = self.view

        guild_id = interaction.guild_id
        await automod.ensure_guild_settings_in_cache(guild_id)
        gs = automod._guild_settings_cache.get(guild_id)

        # Add words
        for word in view.pending_add_words:
            await automod.add_bad_word(word, guild_id, gs)

        # Remove words
        for word in view.pending_remove_words:
            await automod.remove_bad_word(word, guild_id, gs)

        # Replace exempt roles with the newly selected set (if any were chosen)
        if view.pending_exempt_roles is not None:
            # Clear existing roles and set the new selection
            current_roles = list(gs.get("exempt_roles", set()))
            for role in current_roles:
                await automod.remove_exception_role(guild_id, role, gs)
            for role in view.pending_exempt_roles:
                await automod.add_exception_role(guild_id, role, gs)

        # Disable everything and stop
        for item in view.children:
            item.disabled = True
        view.stop()

        embed = _build_badword_embed(interaction.guild, gs, saved=True)
        await interaction.edit_original_response(embed=embed, view=view)


# ── View ─────────────────────────────────────────────────────────────

class BadWordConfigView(discord.ui.View):
    def __init__(self, guild: discord.Guild, gs: dict, interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.pending_add_words: list[str] = []
        self.pending_remove_words: list[str] = []
        self.pending_exempt_roles: list[str] | None = None  # None = no change

        current_words = sorted(gs.get("bad_words", set()))

        self.add_item(AddWordsButton())
        self.add_item(RemoveWordSelect(current_words))
        self.add_item(ExemptRoleSelect())
        self.add_item(SaveButton())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.interaction.edit_original_response(view=self)
        except Exception:
            pass


# ── Cog ──────────────────────────────────────────────────────────────

class AutoModCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="badword_configuration",
        description="View and configure Lumi's bad-word filter and exempt roles 🚫",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_configuration(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)

        embed = _build_badword_embed(interaction.guild, gs)
        view = BadWordConfigView(interaction.guild, gs, interaction)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @badword_configuration.error
    async def _config_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need the **Manage Server** permission to use this command.",
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(AutoModCmds(bot))
