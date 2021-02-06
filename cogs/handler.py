import discord

from discord.ext import commands


class Handler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(self, ctx):
        args = list()
        for arg in ctx.args:
            if not (isinstance(arg, commands.Cog) or isinstance(arg, commands.Context)):
                args.append(arg)
        self.bot.logger.info(f"[{ctx.author.id}] invoked command {ctx.command.name} [args: {args} kwargs: {ctx.kwargs}]")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        self.bot.logger.error(f"Command {ctx.command.name} errored out: {error.__class__.__name__}: {str(error)}")


def setup(bot):
    bot.add_cog(Handler(bot))
