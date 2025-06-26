import discord

async def set_rich_presence(client):
    await client.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening,
        name="your secrets ❤️"
    ))
