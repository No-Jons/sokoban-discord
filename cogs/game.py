import discord
import asyncio
import json

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

    @commands.is_owner()
    @commands.command()
    async def force_save(self, ctx):
        with open("config/levels.json", "w") as fp:
            json.dump(self.levels, fp)
        self.bot.logger.info("[ADMIN] Saving custom levels json")
        await ctx.send("Saved custom levels json")

    @commands.group()
    async def play(self, ctx):
        pass

    @play.command(name="infinite", aliases=["inf", "i"])
    async def infinite(self, ctx, emoji=None, level="1"):
        if self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot start game: game is already active in this channel")
        self.bot.logger.info(f"[{ctx.author.id}] Started new infinite game")
        self.games.new(ctx.author, ctx.channel, level_id=level, emoji_player=emoji)
        game = self.games.get_game(ctx.author.id)
        await self.finish_setup(ctx, title=f"Level {game.level_id}")

    @play.command(name="challenge", aliases=["moves", "c"])
    async def challenge(self, ctx, emoji=None, level="1"):
        if self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot start game: game is already active in this channel")
        self.bot.logger.info(f"[{ctx.author.id}] Started new infinite game")
        moves = 5 + (10 * round(.51 * int(level)))
        self.games.new(ctx.author, ctx.channel, level_id=level, emoji_player=emoji, moves=moves)
        game = self.games.get_game(ctx.author.id)
        await self.finish_setup(ctx, title=f"Level {game.level_id}")

    @commands.command(aliases=["quit"])
    async def end(self, ctx):
        if not self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot end game: no game to end")
        self.bot.logger.info(f"[{ctx.author.id}] Ended game")
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
        self.bot.logger.info(f"[{ctx.author.id}] Submitted new custom level file")
        file = await ctx.message.attachments[0].read()
        try:
            self.games.new(ctx.author, ctx.channel, emoji_player=emoji, file=file)
        except GameError as e:
            self.bot.logger.info(f"[{ctx.author.id}] File was deemed invalid")
            await ctx.send(e.message)
            return
        await self.finish_setup(ctx, title="Custom Level")

    @custom.command(name="text")
    async def text(self, ctx, *, text):
        if self.games.check_active(ctx.author.id, ctx.channel.id):
            return await ctx.send("Cannot start game: game is already active in this channel")
        self.bot.logger.info(f"[{ctx.author.id}] Submitted new custom level string")
        try:
            self.games.new(ctx.author, ctx.channel, emoji_player=None, text=text)
        except GameError as e:
            self.bot.logger.info(f"[{ctx.author.id}] String was deemed invalid")
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
        self.bot.logger.info(f"[{ctx.author.id}] Started playing {member.id}'s level")
        self.games.new(ctx.author, ctx.channel, emoji_player=emoji, content=level)
        await self.finish_setup(ctx, title="Custom Level")

    async def finish_setup(self, ctx, title):
        board = self.games.format_board(ctx.author.id)
        game = self.games.get_game(ctx.author.id)
        embed = discord.Embed(title=title, description=board, color=discord.Color.red())
        if game.moves:
            embed.add_field(name="Moves left:", value=game.moves)
        msg = await ctx.send(embed=embed)
        await self.games.react_to(msg)
        self.valid_messages.append(msg.id)
        self.bot.logger.debug(f"[{ctx.author.id}] Finished game setup")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not reaction.message.id in self.valid_messages or user.id == self.bot.user.id:
            return
        game = self.games.get_game(user.id)
        if reaction.emoji == "🔁":
            game.reset()
            game.moves_made = 0
            await self.games.update_board(user, reaction.message)
            self.bot.logger.debug(f"[{user.id}] Reset board")
        else:
            results = await game.move(reaction.emoji)
            await self.games.update_board(user, reaction.message)
            self.bot.logger.debug(f"[{user.id}] Moved player piece")
            if results["win"]:
                self.games.delete(user.id)
                idx = self.valid_messages.index(reaction.message.id)
                del self.valid_messages[idx]
                if game.random_levels:
                    await self.random_level_win(game, user, reaction.message)
                else:
                    await self.custom_level_win(game, user, reaction.message)
            elif results["loss"]:
                self.games.delete(user.id)
                idx = self.valid_messages.index(reaction.message.id)
                del self.valid_messages[idx]
                await self.game_loss(game, user, reaction.message)

    async def random_level_win(self, game, user, message):
        self.bot.logger.info(f"[{user.id}] Won level")
        embed = discord.Embed(title="You win!", description="Wow! Good job!", color=discord.Color.red())
        embed.set_footer(text=f"Next level: {game.next_level}")
        moves = None
        if game.moves:
            moves = 7 + (8 * round(.51 * int(game.level_id) + 1))
        await message.channel.send(embed=embed)
        self.games.new(user, message.channel, emoji_player=game.emoji_player,
                       level_id=game.next_level, moves=moves)
        board = self.games.format_board(user.id)
        game = self.games.get_game(user.id)
        embed = discord.Embed(title=f"Level {game.level_id}", description=board, color=discord.Color.red())
        if game.moves:
            embed.add_field(name="Moves left:", value=game.moves)
        msg = await message.channel.send(embed=embed)
        await self.games.react_to(msg)
        self.valid_messages.append(msg.id)

    async def custom_level_win(self, game, user, message):
        self.bot.logger.info(f"[{user.id}] Won custom level")
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
                self.bot.logger.info(f"[{user.id}] Saved custom level")
                self.levels[str(user.id)] = game.board_string
                embed = discord.Embed(title="Level saved!", color=discord.Color.red())
                await msg.edit(embed=embed)
            else:
                self.bot.logger.info(f"[{user.id}] Not saving custom level")
            await msg.clear_reactions()
        else:
            embed = discord.Embed(title="Level completed!", color=discord.Color.red())
            await message.channel.send(embed=embed)

    async def game_loss(self, game, user, message):
        self.bot.logger.info(f"[{user.id}] Lost level, ran out of moves")
        embed = discord.Embed(title="You lost...", description="Better luck next time", color=discord.Color.red())
        if game.random_levels:
            embed.add_field(name="Levels completed:", value=str(int(game.level_id) - 1))
        await message.channel.send(embed=embed)

    @tasks.loop(minutes=20)
    async def save_levels(self):
        with open("config/levels.json", "w") as fp:
            json.dump(self.levels, fp)
        self.bot.logger.info("Saving custom levels json")


def setup(bot):
    bot.add_cog(GameCog(bot))
