import os
import logging

import discord
from discord.ext import commands, tasks
import feedparser
import aiohttp

import config

log = logging.getLogger("runejerry.youtube")

CHANNELS = {
    "UCWOMTp0BLi41FTn6ouh_mdg": config.env_int("YT_CHANNEL_1"),
    "UCCYq8CHiJR3Y8IEME0SgNUQ": config.env_int("YT_CHANNEL_2"),
    "UCKK4jwSOaKBSTqQjNRbndng": config.env_int("YT_CHANNEL_3"),
}

# Set YT_PING=0 in the environment to announce uploads without any ping.
PING_ENABLED = os.getenv("YT_PING", "1") != "0"
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

# Discord caps thread names at 100 characters.
THREAD_NAME_LIMIT = 100
# Threads auto-archive after 24h of silence.
THREAD_ARCHIVE_MINUTES = 1440

# Permit role pings while making an accidental @everyone impossible.
PING_MENTIONS = discord.AllowedMentions(everyone=False, users=False, roles=True)


class YouTube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self.check.start()

    async def cog_load(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )

    async def cog_unload(self):
        self.check.cancel()
        if self.session:
            await self.session.close()

    async def _open_thread(self, message, title: str):
        """Start a discussion thread on an announcement.

        Keeps chatter about each upload in one place instead of flooding the
        channel. Failing to create it must never stop the notification loop.
        """
        name = f"💬 {title}"[:THREAD_NAME_LIMIT]
        try:
            await message.create_thread(
                name=name, auto_archive_duration=THREAD_ARCHIVE_MINUTES
            )
        except (discord.HTTPException, AttributeError) as e:
            # AttributeError covers channel types that can't hold threads.
            log.warning("Could not create thread for %s: %s", title, e)

    @tasks.loop(minutes=5)
    async def check(self):
        for yt_id, discord_channel_id in CHANNELS.items():
            channel = self.bot.get_channel(discord_channel_id)
            if not channel:
                continue

            try:
                async with self.session.get(FEED_URL.format(yt_id)) as response:
                    if response.status != 200:
                        continue
                    content = await response.read()
            except Exception as e:
                log.warning("Error fetching YouTube feed for %s: %s", yt_id, e)
                continue

            feed = feedparser.parse(content)
            if not feed.entries:
                continue

            latest_entry = feed.entries[0]
            video_id = latest_entry.get("yt_videoid")
            if not video_id:
                continue

            async with self.bot.db.execute(
                "SELECT 1 FROM youtube_history WHERE channel_id = ? LIMIT 1",
                (yt_id,),
            ) as cursor:
                has_history = await cursor.fetchone()

            async with self.bot.db.execute(
                "SELECT 1 FROM youtube_history WHERE channel_id = ? AND video_id = ?",
                (yt_id, video_id),
            ) as cursor:
                already_seen = await cursor.fetchone()

            if already_seen is not None:
                continue

            await self.bot.db.execute(
                "INSERT INTO youtube_history (channel_id, video_id) VALUES (?, ?)",
                (yt_id, video_id),
            )
            await self.bot.db.execute(
                "INSERT OR REPLACE INTO youtube (channel_id, last_video) VALUES (?, ?)",
                (yt_id, video_id),
            )
            await self.bot.db.commit()

            # First time we see this channel: seed history without announcing,
            # so we don't spam-notify old videos on first run.
            if has_history is None:
                continue

            title = latest_entry.title
            role_id = config.VIDEO_PING_ROLE_ID

            embed = discord.Embed(
                title=f"🎥 {latest_entry.author} just posted a video! Go check it out!",
                description=f"**[{title}](https://www.youtube.com/watch?v={video_id})**",
                color=discord.Color.red(),
            )
            embed.set_image(url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg")

            content = f"<@&{role_id}>" if (PING_ENABLED and role_id) else None
            # tasks.Loop stops for good on an unhandled HTTPException, so a
            # single bad send (missing perms, over-long title) would silently
            # end all future checks. Log and move on to the next channel.
            try:
                message = await channel.send(
                    content=content, embed=embed, allowed_mentions=PING_MENTIONS
                )
            except discord.HTTPException as e:
                log.warning("Failed to send YouTube notification for %s: %s", yt_id, e)
                continue

            await self._open_thread(message, title)

    @check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(YouTube(bot))
