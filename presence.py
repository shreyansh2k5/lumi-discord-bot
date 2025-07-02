# presence.py

import discord
import datetime # Import datetime for handling timestamps

# Sets Lumi's rich presence (status)
async def set_rich_presence(client: discord.Client):
    # Your actual Discord Application ID
    YOUR_APPLICATION_ID = 1387357109842350120

    # --- Map fields from the C code to discord.py Activity parameters ---

    # Timestamps (Unix timestamps to datetime objects)
    # The timestamps in your C code seem to be the same, so the duration will be 0.
    start_timestamp_unix = 1507665886
    end_timestamp_unix = 1507665886 # If your actual end timestamp is different, adjust this

    start_time = datetime.datetime.fromtimestamp(start_timestamp_unix)
    end_time = datetime.datetime.fromtimestamp(end_timestamp_unix)

    # Image Keys and Text (These are asset keys uploaded to Discord Developer Portal)
    large_image_key = "wlppr7"       # Asset name from Discord Developer Portal -> Rich Presence -> Art Assets
    large_image_text = "clinnin"     # Text shown when hovering over the large image
    small_image_key = "sanchita_pfp" # Asset name from Discord Developer Portal -> Rich Presence -> Art Assets
    small_image_text = "join"        # Text shown when hovering over the small image

    # Create the Activity object with the mapped parameters
    activity = discord.Activity(
        application_id=YOUR_APPLICATION_ID,
        type=discord.ActivityType.playing, # Setting type to 'playing' is common for rich presence with images
        name="Custom Status", # This is the main line under "Playing a game" or "Watching a show"
        details= "listening", # Corresponds to `discordPresence.details` ("listening")
        state="chillin'",     # Corresponds to `discordPresence.state` ("chillin'")
        timestamps={'start': start_time, 'end': end_time}, # Dictionary for start/end times
        assets={
            'large_image': large_image_key,
            'large_text': large_image_text,
            'small_image': small_image_key,
            'small_text': small_image_text
        }
        # Removed 'party' and 'secrets' dictionaries as requested.
        # If you want "Join Server" buttons in the future, you'll set them up
        # directly in the Discord Developer Portal for your application,
        # under Rich Presence -> Art Assets -> Rich Presence Display / External Links.
    )

    await client.change_presence(status=discord.Status.idle, activity=activity)
