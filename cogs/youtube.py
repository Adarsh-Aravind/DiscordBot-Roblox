import os
import logging

import discord
from discord.ext import commands, tasks
import feedparser
import aiohttp

log = logging.getLogger("runejerry.youtube")

CHANNELS = {
    "UCWOMTp0BLi41FTn6ouh_mdg": int(os.getenv("YT_CHANNEL_1", 0)),
    "UCCYq8CHiJR3Y8IEME0SgNUQ": int(os.getenv("YT_CHANNEL_2", 0)),
    "UCKK4jwSOaKBSTqQjNRbndng": int(os.getenv("YT_CHANNEL_3", 0)),
}

# Set YT_PING=0 in the environment to announce videos without pinging @everyone.
PING_EVERYONE = os.getenv("YT_PING", "1") != "0"
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"


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

            embed = discord.Embed(
                title=f"🎥 {latest_entry.author} just posted a video! Go check it out!",
                description=f"**[{latest_entry.title}](https://www.youtube.com/watch?v={video_id})**",
                color=discord.Color.red(),
            )
            embed.set_image(url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg")

            content = "Hey! @everyone" if PING_EVERYONE else None
            await channel.send(content=content, embed=embed)

    @check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(YouTube(bot))
