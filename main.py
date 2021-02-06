import discord

from discord.ext import commands
from utils.auth import Auth
from utils.logger import setup_logger


bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
bot.logger = setup_logger(__name__, False)


@bot.event
async def on_ready():
    bot.load_extension("cogs.handler")
    bot.load_extension("cogs.game")
    bot.logger.info("Loaded all cogs")


if __name__ == "__main__":
    bot.run(Auth.TOKEN)

