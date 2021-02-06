import discord

from discord.ext import commands
from utils.auth import Auth


bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


@bot.event
async def on_ready():
    bot.load_extension("cogs.game")


if __name__ == "__main__":
    bot.run(Auth.TOKEN)

