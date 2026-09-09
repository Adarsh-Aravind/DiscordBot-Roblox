import logging
import re
import datetime

import discord
from discord.ext import commands

import config
import modlog

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

# Any hostname in a message, with or without a scheme -- scam posts are just as
# often bare domains ("free-robux.xyz") as full links.
# Each label is one greedy class that cannot span the "." separator, so the
# decomposition is unambiguous. The lookbehind stops the engine from retrying
# the whole match at every character inside a hyphen run -- without it a
# 4000-char message of "a-a-a-..." costs ~32ms of backtracking on the event
# loop; with it, ~0.08ms.
URL_PATTERN = re.compile(
    r"(?<![-\w.])((?:[a-z0-9][a-z0-9-]*\.)+[a-z]{2,})\b",
    re.IGNORECASE,
)

# Two-part public suffixes, so "robux.co.uk" reduces to itself rather than to
# the meaningless "co.uk" (which would slip past the lookalike check).
MULTI_PART_TLDS = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk",
    "com.au", "net.au", "org.au", "co.nz", "co.za",
    "com.br", "com.mx", "com.ar", "co.in", "com.sg",
    "co.jp", "co.kr", "com.cn", "com.tr", "com.tw",
}

# Real domains for the brands these scams impersonate. Anything else carrying a
# brand name in its domain is treated as a lookalike -- this catches new scam
# domains without needing a blocklist that goes stale every week.
OFFICIAL_DOMAINS = {
    "discord.com", "discord.gg", "discordapp.com", "discordapp.net", "discord.media",
    "roblox.com", "rbxcdn.com",
    "youtube.com", "youtu.be", "ytimg.com",
    "kick.com", "twitch.tv",
    "twitter.com", "x.com", "tiktok.com", "instagram.com",
    "steampowered.com", "steamcommunity.com",
}
IMPERSONATED_BRANDS = ("discord", "roblox", "robux", "nitro", "steamcommunity", "bloxflip")

# Classic bait wording. Only acted on when paired with a link.
SCAM_KEYWORD_PATTERN = re.compile(
    r"free\s*(?:robux|nitro|v-?bucks|gift)"
    r"|robux\s*(?:gen|generator|hack)"
    r"|nitro\s*(?:gen|generator)"
    r"|steam\s*gift"
    r"|claim\s*(?:your|free)"
    r"|\bairdrop\b"
    r"|gift\s*card\s*code",
    re.IGNORECASE,
)

ALLOWED_YT_CHANNEL = config.env_int("ALLOWED_YT_CHANNEL")
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
        # Block scam / phishing links
        # -------------------------
        # Extract hostnames once and share them across both link rules.
        domains = self._domains(message.content)

        scam_reason = self._scam_reason(message, domains)
        if scam_reason:
            await self.punish(message, scam_reason, minutes=config.SCAM_TIMEOUT_MINUTES)
            return

        # Brand-new accounts posting links are the usual raid payload. Remove
        # the link but don't time them out -- this one has real false positives.
        if self._new_account_with_link(message, domains):
            await self._delete_and_warn(
                message,
                f"{message.author.mention} New accounts can't post links here yet.",
            )
            await modlog.send(self.bot, modlog.action_embed(
                "🔗 Link removed (new account)",
                discord.Color.orange(),
                message.author,
                f"Account is under {config.NEW_ACCOUNT_LINK_DAYS} days old.",
            ))
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

    @staticmethod
    def _registrable(host: str) -> str:
        """Reduce a hostname to its registrable domain ("a.b.roblox.com" -> "roblox.com").

        Two-part public suffixes are kept whole, so "robux.co.uk" stays
        "robux.co.uk" instead of collapsing to "co.uk".
        """
        parts = host.lower().strip(".").split(".")
        if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_PART_TLDS:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()

    def _domains(self, content: str) -> list[str]:
        return [self._registrable(host) for host in URL_PATTERN.findall(content)]

    def _scam_reason(self, message: discord.Message, domains: list[str]) -> str | None:
        """Return why a message looks like a scam, or None if it looks fine.

        `domains` is passed in so the URL regex runs once per message rather
        than once per rule -- this is on the path of every message sent.
        """
        # Links to the real sites are not evidence of anything.
        unofficial = [d for d in domains if d not in OFFICIAL_DOMAINS]
        if not unofficial:
            return None

        for domain in unofficial:
            for brand in IMPERSONATED_BRANDS:
                if brand in domain:
                    return f"Link imitating {brand} (`{domain}`)"

        # Bait wording only counts alongside an unrecognised link. Requiring
        # that keeps members who are warning each other about scams -- "the
        # free nitro thing on discord.com is fake" -- out of the filter.
        if SCAM_KEYWORD_PATTERN.search(message.content):
            return f"Scam bait wording paired with an unrecognised link (`{unofficial[0]}`)"

        return None

    def _new_account_with_link(self, message: discord.Message, domains: list[str]) -> bool:
        """True for a link posted by an account younger than the configured age."""
        if not config.NEW_ACCOUNT_LINK_DAYS or not domains:
            return False
        age = discord.utils.utcnow() - message.author.created_at
        return age < datetime.timedelta(days=config.NEW_ACCOUNT_LINK_DAYS)

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

    async def punish(self, message, reason, minutes: int = TIMEOUT_DURATION):
        # Delete violation message
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        # Timeout user
        try:
            await message.author.timeout(
                datetime.timedelta(minutes=minutes),
                reason=reason,
            )
        except discord.HTTPException:
            pass

        # Send warning message (auto delete)
        try:
            await message.channel.send(
                f"{message.author.mention} ⚠ {reason}. "
                f"You have been timed out for {minutes} minutes.",
                delete_after=WARNING_DELETE_AFTER,
            )
        except discord.HTTPException:
            pass

        await modlog.send(self.bot, modlog.action_embed(
            "⛔ Member timed out",
            discord.Color.red(),
            message.author,
            f"{reason}\nTimeout: {minutes} minutes | Channel: {message.channel.mention}",
        ))


async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
