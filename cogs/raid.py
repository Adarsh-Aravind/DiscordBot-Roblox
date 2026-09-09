"""Raid protection.

A burst of joins in a short window is the signature of a raid, which is what
tends to follow a video doing well. When one is detected the server's
verification level is raised for a while, which forces new accounts to clear
Discord's own checks before they can post. The previous level is restored
automatically so a raid can't leave the server permanently locked down.
"""

import logging
import time
from collections import defaultdict, deque

import discord
from discord.ext import commands, tasks

import config
import modlog

log = logging.getLogger("runejerry.raid")

# Level applied while locked down. "highest" requires a verified phone number,
# which essentially all throwaway raid accounts lack.
LOCKDOWN_LEVEL = discord.VerificationLevel.highest


class RaidProtection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # guild_id -> timestamps of recent joins
        self._joins: dict[int, deque[float]] = defaultdict(deque)
        # guild_id -> (expires_at, level to restore)
        self._lockdowns: dict[int, tuple[float, discord.VerificationLevel]] = {}
        # guild_id -> time until which a failed lock attempt won't be retried.
        # Without this, a raid on a server where the bot lacks Manage Server
        # retries on every single join, hammering the API and the mod log.
        self._lock_cooldowns: dict[int, float] = {}
        self.expire_lockdowns.start()

    async def cog_unload(self):
        self.expire_lockdowns.cancel()

    def is_locked(self, guild: discord.Guild) -> bool:
        return guild.id in self._lockdowns

    def _in_cooldown(self, guild: discord.Guild) -> bool:
        until = self._lock_cooldowns.get(guild.id)
        if until is None:
            return False
        if time.monotonic() >= until:
            del self._lock_cooldowns[guild.id]
            return False
        return True

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        now = time.monotonic()

        joins = self._joins[guild.id]
        joins.append(now)
        # Drop anything that fell outside the detection window.
        while joins and now - joins[0] > config.RAID_WINDOW_SECONDS:
            joins.popleft()

        if (len(joins) < config.RAID_JOIN_THRESHOLD
                or self.is_locked(guild)
                or self._in_cooldown(guild)):
            return

        # Consume the window so the post-trigger state doesn't immediately
        # re-fire once the lockdown lifts. Count first -- it's needed below.
        count = len(joins)
        joins.clear()

        await self._lock(
            guild,
            f"{count} joins in {config.RAID_WINDOW_SECONDS}s "
            f"(threshold {config.RAID_JOIN_THRESHOLD}).",
        )

    async def _lock(self, guild: discord.Guild, reason: str, minutes: int | None = None):
        """Raise the verification level and remember what to restore."""
        minutes = minutes or config.RAID_LOCKDOWN_MINUTES
        previous = guild.verification_level

        try:
            await guild.edit(verification_level=LOCKDOWN_LEVEL, reason=f"Raid protection: {reason}")
        except discord.Forbidden:
            # Back off before retrying, or an ongoing raid re-triggers this on
            # every join and floods both the API and the mod log.
            self._lock_cooldowns[guild.id] = time.monotonic() + minutes * 60
            log.warning("Missing Manage Server permission; cannot lock down %s", guild.name)
            await self._report(
                guild,
                "⚠️ Raid detected but lockdown FAILED",
                f"{reason}\nThe bot needs the Manage Server permission.\n"
                f"Suppressing further attempts for {minutes} minutes.",
                discord.Color.orange(),
            )
            return
        except discord.HTTPException as e:
            self._lock_cooldowns[guild.id] = time.monotonic() + minutes * 60
            log.warning("Lockdown failed for %s: %s", guild.name, e)
            return

        self._lockdowns[guild.id] = (time.monotonic() + minutes * 60, previous)
        log.warning("Raid lockdown engaged on %s: %s", guild.name, reason)

        await self._report(
            guild,
            "🚨 Raid lockdown engaged",
            f"{reason}\nVerification raised to **{LOCKDOWN_LEVEL.name}** "
            f"for {minutes} minutes (was **{previous.name}**).",
            discord.Color.red(),
        )

    async def _unlock(self, guild: discord.Guild, automatic: bool = True):
        """Put the verification level back to whatever it was before."""
        entry = self._lockdowns.get(guild.id)
        if entry is None:
            return False

        expires_at, previous = entry
        try:
            await guild.edit(verification_level=previous, reason="Raid protection: lockdown expired")
        except discord.HTTPException as e:
            # Keep the entry so the next tick retries. Dropping it here would
            # strand the server at the raised verification level for good.
            self._lockdowns[guild.id] = (expires_at + 60, previous)
            log.warning("Could not restore verification level on %s: %s", guild.name, e)
            return False

        # Only forget the lockdown once the level is actually restored.
        self._lockdowns.pop(guild.id, None)

        await self._report(
            guild,
            "✅ Lockdown lifted",
            f"Verification level restored to **{previous.name}** "
            f"({'automatically' if automatic else 'manually'}).",
            discord.Color.green(),
        )
        return True

    async def _report(self, guild, title: str, description: str, colour: discord.Color):
        embed = discord.Embed(title=title, description=description, color=colour)
        embed.set_footer(text=guild.name)
        embed.timestamp = discord.utils.utcnow()
        await modlog.send(self.bot, embed)

    @tasks.loop(seconds=30)
    async def expire_lockdowns(self):
        now = time.monotonic()
        for guild_id, (expires_at, _) in list(self._lockdowns.items()):
            if now < expires_at:
                continue
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                self._lockdowns.pop(guild_id, None)
                continue
            await self._unlock(guild)

    @expire_lockdowns.before_loop
    async def before_expire(self):
        await self.bot.wait_until_ready()

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def lockdown(self, ctx, minutes: int = None):
        """Manually lock the server down for a number of minutes."""
        if self.is_locked(ctx.guild):
            return await ctx.send("The server is already locked down.")
        await self._lock(ctx.guild, f"Manual lockdown by {ctx.author}.", minutes)
        await ctx.send("🔒 Lockdown engaged.")

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def unlock(self, ctx):
        """Lift an active lockdown early."""
        if await self._unlock(ctx.guild, automatic=False):
            await ctx.send("🔓 Lockdown lifted.")
        else:
            await ctx.send("The server isn't locked down.")


async def setup(bot):
    await bot.add_cog(RaidProtection(bot))
