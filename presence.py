# presence.py

import discord

# Sets Lumi's rich presence (status)
async def set_rich_presence(client: discord.Client):
    # Replace with your actual Discord Application ID and Server Invite Link
    YOUR_APPLICATION_ID = 123456789012345678 # Example ID
    YOUR_SERVER_INVITE_URL = "https://discord.gg/UjzpCSHRgb" # Example Invite

    # Define buttons for the rich presence
    buttons = [
         discord.ui.Button(label="Join Our Server", style=discord.ButtonStyle.link, url=YOUR_SERVER_INVITE_URL)
    ]

    # Create the activity with more details and buttons
    activity = discord.Activity(
        type=discord.ActivityType.watching, # Or PLAYING, STREAMING, etc.
        name="💖 you ping me",
        details="Chatting with homies!", # More descriptive text
        state="Feeling cute today!",     # Even more personalized text
        application_id=YOUR_APPLICATION_ID,
        "wlppr7", # Asset key from Discord Dev Portal
        "sanchita_pfp", # Asset key from Discord Dev Portal
        buttons=buttons # Attach the buttons here
    )
    await client.change_presence(status=discord.Status.idle, activity=activity)
