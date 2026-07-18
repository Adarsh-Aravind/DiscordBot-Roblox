import logging

import discord
from discord.ext import commands, tasks
from curl_cffi.requests import AsyncSession

log = logging.getLogger("runejerry.kick")

# Kick channel to watch: https://kick.com/runejerry
KICK_SLUG = "runejerry"
# Discord channel that go-live announcements are posted to.
KICK_CHANNEL_ID = 1527727884264018072
# Set to False to announce streams without pinging @everyone.
KICK_PING = True
# How often (in minutes) to poll Kick for the live status.
KICK_POLL_MINUTES = 2

API_URL = "https://kick.com/api/v2/channels/{}"
STREAM_URL = "https://kick.com/{}"

# Kick's API sits behind Cloudflare, which rejects plain aiohttp on its TLS
# fingerprint (403) no matter what headers are sent. curl_cffi impersonates a
# real Chrome handshake, which gets through.
IMPERSONATE = "chrome"


class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: AsyncSession | None = None
        self.check.start()

    async def cog_load(self):
        self.session = AsyncSession(impersonate=IMPERSONATE, timeout=15)

    async def cog_unload(self):
        self.check.cancel()
        if self.session:
            await self.session.close()

    async def _fetch_channel(self, slug: str) -> dict | None:
        try:
            response = await self.session.get(API_URL.format(slug))
            if response.status_code != 200:
                log.warning("Kick API returned %s for %s", response.status_code, slug)
                return None
            return response.json()
        except Exception as e:
            log.warning("Error fetching Kick channel %s: %s", slug, e)
            return None

    def _build_embed(self, data: dict, livestream: dict) -> discord.Embed:
        slug = data.get("slug") or KICK_SLUG
        user = data.get("user") or {}
        name = user.get("username") or slug
        url = STREAM_URL.format(slug)

        embed = discord.Embed(
            title=f"🟢 {name} is now LIVE on Kick!",
            description=f"**[{livestream.get('session_title') or 'Untitled stream'}]({url})**",
            color=discord.Color.from_str("#53fc18"),  # Kick green
        )

        categories = livestream.get("categories") or []
        if categories and categories[0].get("name"):
            embed.add_field(name="Category", value=categories[0]["name"], inline=True)

        viewers = livestream.get("viewer_count")
        if viewers is not None:
            embed.add_field(name="Viewers", value=f"{viewers:,}", inline=True)

        # thumbnail can be null (or a bare string) even while live, so fall back
        # to the offline banner and then the profile picture.
        thumbnail = livestream.get("thumbnail")
        if isinstance(thumbnail, dict):
            image = thumbnail.get("url")
        elif isinstance(thumbnail, str):
            image = thumbnail
        else:
            image = None

        banner = data.get("offline_banner_image")
        if not image and isinstance(banner, dict):
            image = banner.get("src") or banner.get("url")
        if image:
            embed.set_image(url=image)

        if user.get("profile_pic"):
            embed.set_thumbnail(url=user["profile_pic"])

        embed.set_footer(text="Kick")
        return embed

    @tasks.loop(minutes=KICK_POLL_MINUTES)
    async def check(self):
        slug = KICK_SLUG
        channel = self.bot.get_channel(KICK_CHANNEL_ID)
        if not channel:
            return

        data = await self._fetch_channel(slug)
        if data is None:
            # Network/Cloudflare hiccup: leave the stored state alone so a
            # transient failure isn't treated as the stream going offline.
            return

        livestream = data.get("livestream")
        is_live = bool(livestream) and livestream.get("is_live", True)
        stream_id = str(livestream.get("id")) if is_live else None

        async with self.bot.db.execute(
            "SELECT is_live, last_stream_id FROM kick WHERE slug = ?", (slug,)
        ) as cursor:
            row = await cursor.fetchone()

        await self.bot.db.execute(
            "INSERT OR REPLACE INTO kick (slug, is_live, last_stream_id) VALUES (?, ?, ?)",
            (slug, int(is_live), stream_id if is_live else (row[1] if row else None)),
        )
        await self.bot.db.commit()

        # First run for this channel: record the state without announcing so we
        # don't post an alert for a stream that was already running.
        if row is None:
            return

        if not is_live:
            return

        was_live, last_stream_id = bool(row[0]), row[1]
        # Announce only on an offline -> live transition, and never twice for
        # the same stream (guards against a brief drop mid-stream).
        if was_live or last_stream_id == stream_id:
            return

        content = "@everyone" if KICK_PING else None
        try:
            await channel.send(content=content, embed=self._build_embed(data, livestream))
        except discord.HTTPException as e:
            log.warning("Failed to send Kick notification: %s", e)

    @check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Kick(bot))
