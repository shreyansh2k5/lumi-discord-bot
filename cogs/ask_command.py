import discord
from discord import app_commands
from discord.ext import commands
import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def ask_openrouter(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistralai/mistral-small-3.2-24b-instruct:free",
        "messages": [
            {"role": "system", "content": "You are Lumi, a flirty anime girl."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Error: {e}"

class AskCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Chat with Lumi 💬")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        response = ask_openrouter(question)
        await interaction.followup.send(response)

async def setup(bot):
    await bot.add_cog(AskCommand(bot))

