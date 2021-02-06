import discord
import asyncio
import json
import copy

from discord.ext import commands, tasks
from utils.game import Games, GameError


class GameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.valid_messages = list()
        self.games = Games()

        with open("config/levels.json", "r") as fp:
            self.levels = json.load(fp)

        self.save_levels.start()

    @commands.command()
    async def play(self, ctx, emoji: str = None, level: str = "1"):
        if self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot start game: game is already active in this channel")
        self.games.new(ctx.author, ctx.channel, level_id=level, emoji_player=emoji)
        game = self.games.get_game(ctx.author.id)
        await self.finish_setup(ctx, title=f"Level {game.level_id}")

    @commands.command(aliases=["quit"])
    async def end(self, ctx):
        if not self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot end game: no game to end")
        self.games.delete(ctx.author.id)
        await ctx.send("Ended game!")

    @commands.group()
    async def custom(self, ctx):
        pass

    @custom.command(name="file")
    async def file(self, ctx, emoji: str = None):
        if self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot start game: game is already active in this channel")
        if not ctx.message.attachments:
            await ctx.send("You must provide a text file for me to parse!")
            return
        file = await ctx.message.attachments[0].read()
        try:
            self.games.new(ctx.author, ctx.channel, emoji_player=emoji, file=file)
        except GameError as e:
            await ctx.send(e.message)
            return
        await self.finish_setup(ctx, title="Custom Level")

    @custom.command(name="load")
    async def load(self, ctx, member: discord.Member = None, emoji: str = None):
        if self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot start game: game is already active in this channel")
        member = member or ctx.author
        level = self.levels.get(str(member.id))
        if not level:
            await ctx.send("Cannot find level")
            return
        self.games.new(ctx.author, ctx.channel, emoji_player=emoji, content=level)
        await self.finish_setup(ctx, title="Custom Level")

    async def finish_setup(self, ctx, title):
        board = self.games.format_board(ctx.author.id)
        embed = discord.Embed(title=title, description=board, color=discord.Color.red())
        msg = await ctx.send(embed=embed)
        await self.games.react_to(msg)
        self.valid_messages.append(msg.id)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not reaction.message.id in self.valid_messages or user.id == self.bot.user.id:
            return
        game = self.games.get_game(user.id)
        if reaction.emoji == "🔁":
            game.reset()
            await self.games.update_board(user.id, reaction.message)
        else:
            win = await game.move(reaction.emoji)
            await self.games.update_board(user.id, reaction.message)
            if win:
                self.games.delete(user.id)
                idx = self.valid_messages.index(reaction.message.id)
                del self.valid_messages[idx]
                if game.random_levels:
                    await self.random_level_win(game, user, reaction.message)
                else:
                    await self.custom_level_win(game, user, reaction.message)

    async def random_level_win(self, game, user, message):
        embed = discord.Embed(title="You win!", description="Wow! Good job!", color=discord.Color.red())
        embed.set_footer(text=f"Next level: {game.next_level}")
        await message.channel.send(embed=embed)
        self.games.new(user, message.channel, emoji_player=game.emoji_player,
                       level_id=game.next_level)
        board = self.games.format_board(user.id)
        game = self.games.get_game(user.id)
        embed = discord.Embed(title=f"Level {game.level_id}", description=board, color=discord.Color.red())
        msg = await message.channel.send(embed=embed)
        await self.games.react_to(msg)
        self.valid_messages.append(msg.id)

    async def custom_level_win(self, game, user, message):
        if not game.saved:
            embed = discord.Embed(title="Level completed!", description="Would you like to save your level?",
                                  color=discord.Color.red())
            embed.set_footer(text="You can only save one custom level as a time, this will overwrite any previous level you have saved")
            msg = await message.channel.send(embed=embed)
            for emoji in ("✅", "❌"):
                await msg.add_reaction(emoji)
            try:
                r, u = await self.bot.wait_for("reaction_add", check=lambda r, u: r.message.id == msg.id and r.emoji in ("✅", "❌") and u.id == user.id, timeout=60)
            except asyncio.TimeoutError:
                await msg.clear_reactions()
                return
            if r.emoji == "✅":
                self.levels[str(user.id)] = copy.deepcopy(game.initial_board)
                embed = discord.Embed(title="Level saved!", color=discord.Color.red())
                await msg.edit(embed=embed)
            await msg.clear_reactions()
        else:
            embed = discord.Embed(title="Level completed!", color=discord.Color.red())
            await message.channel.send(embed=embed)

    @tasks.loop(minutes=1)
    async def save_levels(self):
        with open("config/levels.json", "w") as fp:
            json.dump(self.levels, fp)


def setup(bot):
    bot.add_cog(GameCog(bot))
