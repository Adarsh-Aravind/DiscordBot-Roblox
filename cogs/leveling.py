import time
import random
import math

import discord
from discord.ext import commands

import config

# Seconds a user must wait between XP-earning messages (anti-spam).
XP_COOLDOWN = 60


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldowns: dict[int, float] = {}  # user_id -> last XP timestamp

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # Ignore commands so prefixed messages don't grant XP.
        if message.content.startswith(config.COMMAND_PREFIX):
            return

        # Rate-limit XP gain per user.
        now = time.monotonic()
        last = self._cooldowns.get(message.author.id, 0)
        if now - last < XP_COOLDOWN:
            return
        self._cooldowns[message.author.id] = now

        xp_gain = random.randint(5, 10)

        async with self.bot.db.execute(
            "SELECT xp, level FROM levels WHERE user_id = ?",
            (message.author.id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            xp, level = xp_gain, 0
            await self.bot.db.execute(
                "INSERT INTO levels (user_id, xp, level) VALUES (?, ?, ?)",
                (message.author.id, xp, level),
            )
        else:
            xp, level = row
            xp += xp_gain

        new_level = int(math.sqrt(xp) // 10)

        # 🔥 Level Up Notification
        if new_level > level:
            level = new_level
            await message.channel.send(
                f"🎉 **{message.author.name}** has reached level **{level}**!"
            )

        await self.bot.db.execute(
            "UPDATE levels SET xp = ?, level = ? WHERE user_id = ?",
            (xp, level, message.author.id),
        )
        await self.bot.db.commit()

    @commands.command()
    async def rank(self, ctx):
        async with self.bot.db.execute(
            "SELECT xp, level FROM levels WHERE user_id = ?",
            (ctx.author.id,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            await ctx.send("No data yet.")
            return

        xp, level = row
        await ctx.send(f"Level: {level} | XP: {xp}")

    @commands.command(name="leaderboard", aliases=["top", "lb"])
    async def leaderboard(self, ctx):
        """Show the top 10 members by level and XP."""
        async with self.bot.db.execute(
            "SELECT user_id, xp, level FROM levels ORDER BY xp DESC LIMIT 10"
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send("No one has earned XP yet!")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (user_id, xp, level) in enumerate(rows):
            member = ctx.guild.get_member(user_id) if ctx.guild else None
            name = member.display_name if member else f"User {user_id}"
            rank = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{rank} **{name}** — Level {level} ({xp} XP)")

        embed = discord.Embed(
            title="🏆 XP Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def levelreset(self, ctx, user: discord.Member = None):
        if user:
            await self.bot.db.execute(
                "DELETE FROM levels WHERE user_id = ?",
                (user.id,),
            )
            self._cooldowns.pop(user.id, None)
        else:
            await self.bot.db.execute("DELETE FROM levels")
            self._cooldowns.clear()

        await self.bot.db.commit()
        await ctx.send("Levels reset.")


async def setup(bot):
    await bot.add_cog(Leveling(bot))
