# presence.py

import discord

# Sets Lumi's rich presence (status)
async def set_rich_presence(client: discord.Client):
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="💖 you ping me"
    )
    await client.change_presence(status=discord.Status.idle, activity=activity)
