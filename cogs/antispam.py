import logging
import re
import datetime

import discord
from discord.ext import commands

import config

log = logging.getLogger("runejerry.antispam")

INVITE_PATTERN = re.compile(r"(discord\.gg/|discord\.com/invite/)", re.IGNORECASE)
YOUTUBE_PATTERN = re.compile(r"(youtube\.com|youtu\.be)", re.IGNORECASE)
CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:\w+:\d+>")
UNICODE_EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF]+",  # flags
    flags=re.UNICODE,
)

import os

ALLOWED_YT_CHANNEL = int(os.getenv("ALLOWED_YT_CHANNEL", 0))
MAX_USER_MENTIONS = 4
MAX_EMOJIS = 8
TIMEOUT_DURATION = 5  # minutes
WARNING_DELETE_AFTER = 30  # seconds


class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_exempt(self, message: discord.Message) -> bool:
        """Owners, admins and anyone who can manage messages skip moderation."""
        author = message.author
        if config.is_owner(author.id):
            return True
        perms = getattr(author, "guild_permissions", None)
        if perms and (perms.administrator or perms.manage_messages):
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots and DMs (no moderation outside guilds).
        if message.author.bot or not message.guild:
            return

        # -------------------------
        # Protect the creator / staff from being pinged
        # -------------------------
        if self._mentions_protected_user(message):
            await self._delete_and_warn(
                message,
                f"{message.author.mention} ⚠ Please don't ping the creator or staff directly.",
            )
            return

        # Trusted members bypass the remaining spam filters.
        if self._is_exempt(message):
            return

        # -------------------------
        # Block @everyone / @here
        # -------------------------
        if message.mention_everyone:
            await self.punish(message, "Mass mention (@everyone / @here) is not allowed")
            return

        # -------------------------
        # Block mass user mentions
        # -------------------------
        if len(message.mentions) > MAX_USER_MENTIONS:
            await self.punish(message, "Mass user mentions are not allowed")
            return

        # -------------------------
        # Block invite links
        # -------------------------
        if INVITE_PATTERN.search(message.content):
            await self.punish(message, "Discord invite links are not allowed")
            return

        # -------------------------
        # Restrict YouTube links
        # -------------------------
        if YOUTUBE_PATTERN.search(message.content) and message.channel.id != ALLOWED_YT_CHANNEL:
            await self._delete_and_warn(
                message,
                f"{message.author.mention} YouTube links are only allowed in the designated channel.",
            )
            return

        # -------------------------
        # Block mass emoji spam
        # -------------------------
        emoji_count = len(CUSTOM_EMOJI_PATTERN.findall(message.content))
        emoji_count += len(UNICODE_EMOJI_PATTERN.findall(message.content))

        if emoji_count > MAX_EMOJIS:
            await self.punish(message, "Mass emoji spam is not allowed")
            return

    def _mentions_protected_user(self, message: discord.Message) -> bool:
        """True if the message pings a protected user (and the author isn't one)."""
        if config.is_owner(message.author.id) or message.author.id in config.PROTECTED_USER_IDS:
            return False
        return any(user.id in config.PROTECTED_USER_IDS for user in message.mentions)

    async def _delete_and_warn(self, message: discord.Message, warning: str):
        """Delete a message and post a self-deleting warning (no timeout)."""
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        try:
            await message.channel.send(warning, delete_after=WARNING_DELETE_AFTER)
        except discord.HTTPException:
            pass

    async def punish(self, message, reason):
        # Delete violation message
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        # Timeout user
        try:
            await message.author.timeout(
                datetime.timedelta(minutes=TIMEOUT_DURATION),
                reason=reason,
            )
        except discord.HTTPException:
            pass

        # Send warning message (auto delete)
        try:
            await message.channel.send(
                f"{message.author.mention} ⚠ {reason}. "
                f"You have been timed out for {TIMEOUT_DURATION} minutes.",
                delete_after=WARNING_DELETE_AFTER,
            )
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
