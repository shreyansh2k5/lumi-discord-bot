# mention_commands.py

import discord
import datetime
import re

# Import necessary functions from other modules
from groq_api import query_groq as query_model
from personality import apply_personality
from memory_store import get_memory, add_to_memory
from automod import check_bad_words, is_role_exempt

def setup_mention_commands(bot: discord.ext.commands.Bot):
    """
    Sets up event listeners for mention-based commands and moderation confirmations.
    """

    # --- Event Listener for Button Interactions (for moderation confirmation) ---
    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        """
        Handles interactions, specifically for moderation confirmation buttons.
        """
        if interaction.type == discord.InteractionType.component:
            custom_id_parts = interaction.data.get("custom_id", "").split('_')
            # Check if it's a moderation confirmation button interaction
            if len(custom_id_parts) >= 5 and custom_id_parts[0] == "mod":
                action_type = custom_id_parts[1] # e.g., "timeout", "kick", "ban"
                status = custom_id_parts[2]       # "confirm" or "cancel"
                target_id = int(custom_id_parts[3])
                invoker_id = int(custom_id_parts[4])

                guild = interaction.guild
                if not guild:
                    await interaction.response.send_message("This action can only be performed in a server.", ephemeral=True)
                    return

                # Ensure only the original invoker or an administrator can confirm/cancel
                if interaction.user.id != invoker_id and not interaction.user.guild_permissions.moderate_members:
                    await interaction.response.send_message("❌ Only the original moderator or an administrator can confirm/cancel this action.", ephemeral=True)
                    return

                target_member = guild.get_member(target_id)
                invoker_member = guild.get_member(invoker_id)

                # Prevent re-use of old buttons
                # Edit the original message to remove the buttons after a choice is made
                await interaction.message.edit(view=None)

                if status == "confirm":
                    if not target_member:
                        await interaction.response.send_message(f"❌ User not found or left the server. Cannot complete action.", ephemeral=True)
                        return
                    
                    # Re-check permissions and hierarchy just in case roles changed between initial command and confirmation
                    bot_member = guild.me
                    if bot_member.top_role <= target_member.top_role:
                        await interaction.response.send_message(f"❌ Lumi cannot {action_type} {target_member.mention} because their role is higher than or equal to Lumi's highest role.", ephemeral=True)
                        return
                    if invoker_member and invoker_member.top_role <= target_member.top_role:
                        await interaction.response.send_message(f"❌ {invoker_member.mention}, you cannot {action_type} {target_member.mention} because their role is higher than or equal to your highest role.", ephemeral=True)
                        return
                    if target_member == guild.owner:
                        await interaction.response.send_message(f"❌ Lumi cannot {action_type} the server owner.", ephemeral=True)
                        return

                    reason = "Moderation action confirmed by staff via Lumi bot."
                    
                    try:
                        if action_type == "timeout":
                            duration_str = "5 minutes" # Default if not found in embed
                            # Attempt to parse duration from the embed's field
                            for field in interaction.message.embeds[0].fields:
                                if field.name == "Duration":
                                    duration_str = field.value
                                    break
                            
                            duration = datetime.timedelta(minutes=5) # Default
                            match = re.match(r'(\d+)\s*(minute|hour|day|week)s?', duration_str, re.IGNORECASE)
                            if match:
                                value = int(match.group(1))
                                unit = match.group(2).lower()
                                if 'minute' in unit: duration = datetime.timedelta(minutes=value)
                                elif 'hour' in unit: duration = datetime.timedelta(hours=value)
                                elif 'day' in unit: duration = datetime.timedelta(days=value)
                                elif 'week' in unit: duration = datetime.timedelta(weeks=value)

                            await target_member.timeout(duration, reason=reason)
                            await interaction.response.send_message(f"✅ {target_member.display_name} has been **{action_type}ed** for {duration_str} by {invoker_member.display_name}.", ephemeral=False)
                        elif action_type == "kick":
                            await target_member.kick(reason=reason)
                            await interaction.response.send_message(f"✅ {target_member.display_name} has been **{action_type}ed** by {invoker_member.display_name}.", ephemeral=False)
                        elif action_type == "ban":
                            await target_member.ban(reason=reason)
                            await interaction.response.send_message(f"✅ {target_member.display_name} has been **{action_type}ed** by {invoker_member.display_name}.", ephemeral=False)

                    except discord.Forbidden:
                        await interaction.response.send_message(f"❌ Lumi does not have permission to {action_type} {target_member.display_name}. Check Lumi's role hierarchy and permissions.", ephemeral=True)
                    except Exception as e:
                        print(f"[Moderation Error] {e}")
                        await interaction.response.send_message(f"An unexpected error occurred during moderation: {e}", ephemeral=True)

                elif status == "cancel":
                    await interaction.response.send_message(f"✅ Moderation action cancelled.", ephemeral=False)
        
        # IMPORTANT: Ensure this line is present to allow other interactions (like slash commands) to process
        # This calls the original process_commands from the bot, which handles slash commands and other commands.
        await bot.process_commands(interaction)


    # --- Event Listener for Messages ---
    @bot.event
    async def on_message(message):
        """
        Handles incoming messages for auto-moderation, mention-based chat,
        and moderation commands via replies.
        """
        # Always process traditional commands first (if any are defined)
        await bot.process_commands(message)

        if message.author == bot.user:
            return

        # 🚨 Auto-moderation check (MUST come early)
        if message.guild:  # only moderate in servers
            guild_id = message.guild.id
            
            user_roles = [role.name for role in message.author.roles]
            if not any(is_role_exempt(guild_id, role_name) for role_name in user_roles):
                if check_bad_words(message.content):
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, please avoid using inappropriate language.",
                        delete_after=5
                    )
                    return # Stop processing if a bad word is detected
                    
        # ✅ Only extract user info if safe
        user_input = message.content.strip()
        user_id = str(message.author.id)

        # ✅ If Lumi is mentioned directly (and not a reply with moderation intent)
        if bot.user in message.mentions and not message.reference:
            user_prompt = message.clean_content.replace(f"@{bot.user.name}", "").strip()
            if not user_prompt:
                user_prompt = "Say something cute!"

            memory = get_memory(user_id)
            final_prompt = f"{memory}\nUser: {user_prompt}"
            prompt = apply_personality(final_prompt)

            response = await query_model(prompt)
            add_to_memory(user_id, f"User: {user_prompt}")
            add_to_memory(user_id, f"Lumi: {response}")

            await message.channel.send(response)

        # ✅ If it's a reply to any message (check for moderation intent or reply to Lumi)
        elif message.reference:
            replied_msg = await message.channel.fetch_message(message.reference.message_id)
            
            # --- New Moderation Logic (if Lumi is mentioned in a reply to another user's message) ---
            if bot.user in message.mentions and replied_msg.author != bot.user:
                content = message.clean_content.replace(f"@{bot.user.name}", "").strip().lower()
                target_member = replied_msg.author # The user who was replied to
                invoker = message.author # The user who invoked the moderation command
                guild = message.guild

                if not guild: # Moderation commands are guild-specific
                    return

                action_type = None
                duration = None # For timeout
                reason = "Moderation action requested via Lumi bot." # Default reason

                # Command parsing for mute/timeout, kick, ban
                if "mute" in content or "timeout" in content:
                    action_type = "timeout"
                    # Check for duration (e.g., "mute for 5m", "timeout for 1h")
                    match = re.search(r'(?:for\s+)(\d+)\s*(m|h|d|w)', content)
                    if match:
                        value = int(match.group(1))
                        unit = match.group(2)
                        if unit == 'm': duration = datetime.timedelta(minutes=value)
                        elif unit == 'h': duration = datetime.timedelta(hours=value)
                        elif unit == 'd': duration = datetime.timedelta(days=value)
                        elif unit == 'w': duration = datetime.timedelta(weeks=value)
                    else:
                        duration = datetime.timedelta(minutes=5) # Default to 5 minutes if no duration specified
                    reason = f"Timeout requested by {invoker.display_name}."
                elif "kick" in content:
                    action_type = "kick"
                    reason = f"Kick requested by {invoker.display_name}."
                elif "ban" in content:
                    action_type = "ban"
                    reason = f"Ban requested by {invoker.display_name}."
                
                # Additional logic to parse custom reasons
                reason_match = re.search(r'(?:reason|for)\s+(.+)', content)
                if reason_match:
                    parsed_reason = reason_match.group(1).strip()
                    if parsed_reason:
                        reason = parsed_reason

                if action_type:
                    # --- Permission and Hierarchy Checks ---
                    bot_member = guild.me # Lumi's member object in this guild
                    
                    # Check if Lumi has the necessary permissions
                    if action_type == "timeout" and not bot_member.guild_permissions.moderate_members:
                        await message.channel.send("❌ Lumi doesn't have 'Moderate Members' permission to timeout users!")
                        return
                    if action_type == "kick" and not bot_member.guild_permissions.kick_members:
                        await message.channel.send("❌ Lumi doesn't have 'Kick Members' permission to kick users!")
                        return
                    if action_type == "ban" and not bot_member.guild_permissions.ban_members:
                        await message.channel.send("❌ Lumi doesn't have 'Ban Members' permission to ban users!")
                        return

                    # Check if the invoking user has the necessary permissions
                    if action_type == "timeout" and not invoker.guild_permissions.moderate_members:
                        await message.channel.send(f"❌ {invoker.mention}, you don't have 'Moderate Members' permission to timeout users!")
                        return
                    if action_type == "kick" and not invoker.guild_permissions.kick_members:
                        await message.channel.send(f"❌ {invoker.mention}, you don't have 'Kick Members' permission to kick users!")
                        return
                    if action_type == "ban" and not invoker.guild_permissions.ban_members:
                        await message.channel.send(f"❌ {invoker.mention}, you don't have 'Ban Members' permission to ban users!")
                        return

                    # Check Role Hierarchy: Lumi cannot moderate someone with a higher or equal role.
                    # The invoker also cannot moderate someone with a higher or equal role.
                    if bot_member.top_role <= target_member.top_role:
                        await message.channel.send(f"❌ Lumi cannot {action_type} {target_member.mention} because their role is higher than or equal to Lumi's highest role. Move Lumi's role higher!")
                        return
                    if invoker.top_role <= target_member.top_role:
                        await message.channel.send(f"❌ {invoker.mention}, you cannot {action_type} {target_member.mention} because their role is higher than or equal to your highest role. Their power level is too high!")
                        return
                    if target_member == guild.owner:
                        await message.channel.send(f"❌ Lumi cannot {action_type} the server owner.")
                        return


                    # --- Confirmation Message with Buttons ---
                    embed = discord.Embed(
                        title=f"Confirm {action_type.capitalize()}?",
                        description=f"Are you sure you want to **{action_type}** {target_member.mention} ({target_member.display_name})?",
                        color=discord.Color.orange()
                    )
                    if action_type == "timeout" and duration:
                        embed.add_field(name="Duration", value=str(duration), inline=False)
                    embed.add_field(name="Target User ID", value=target_member.id, inline=True)
                    embed.add_field(name="Invoked By", value=invoker.display_name, inline=True)
                    embed.set_footer(text=f"Reason: {reason}")

                    # Custom IDs for buttons will carry action, status, target_id, invoker_id
                    # This allows the on_interaction event to know all details.
                    confirm_button = discord.ui.Button(
                        label="Confirm", style=discord.ButtonStyle.red,
                        custom_id=f"mod_{action_type}_confirm_{target_member.id}_{invoker.id}"
                    )
                    cancel_button = discord.ui.Button(
                        label="Cancel", style=discord.ButtonStyle.grey,
                        custom_id=f"mod_{action_type}_cancel_{target_member.id}_{invoker.id}"
                    )

                    view = discord.ui.View()
                    view.add_item(confirm_button)
                    view.add_item(cancel_button)

                    await message.channel.send(embed=embed, view=view)
                    return # Stop further processing of this message to avoid AI chat


            # --- Original AI chat logic (if it's a reply to Lumi for chat) ---
            elif replied_msg.author == bot.user:
                memory = get_memory(user_id)
                final_prompt = f"{memory}\nUser: {user_input}"
                prompt = apply_personality(final_prompt)

                response = await query_model(prompt)
                add_to_memory(user_id, f"User: {user_input}")
                add_to_memory(user_id, f"Lumi: {response}")

                await message.channel.send(response)


