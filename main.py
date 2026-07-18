import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite

import config

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("runejerry")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=config.COMMAND_PREFIX,
    intents=intents,
    help_command=None,
    owner_ids=config.OWNER_IDS,
)

@bot.event
async def setup_hook():
    bot.db = await aiosqlite.connect("runejerry.db")

    await bot.db.execute("""
    CREATE TABLE IF NOT EXISTS levels (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 0
    )
    """)

    await bot.db.execute("""
    CREATE TABLE IF NOT EXISTS youtube (
        channel_id TEXT PRIMARY KEY,
        last_video TEXT
    )
    """)

    await bot.db.execute("""
    CREATE TABLE IF NOT EXISTS youtube_history (
        channel_id TEXT,
        video_id TEXT,
        PRIMARY KEY (channel_id, video_id)
    )
    """)

    await bot.db.execute("""
    CREATE TABLE IF NOT EXISTS kick (
        slug TEXT PRIMARY KEY,
        is_live INTEGER DEFAULT 0,
        last_stream_id TEXT
    )
    """)

    # Migrate existing last_video to history to avoid re-notifying
    await bot.db.execute("""
    INSERT OR IGNORE INTO youtube_history (channel_id, video_id)
    SELECT channel_id, last_video FROM youtube WHERE last_video IS NOT NULL
    """)

    await bot.db.commit()

    for ext in [
        "cogs.general",
        "cogs.messaging",
        "cogs.leveling",
        "cogs.antispam",
        "cogs.youtube",
        "cogs.kick",
        "cogs.roblox",
        "cogs.giveaway"
    ]:
        await bot.load_extension(ext)

@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)

# 🔥 ONLY ONE PLACE PROCESSING COMMANDS
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

def run():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Add it to your .env file.")
    bot.run(TOKEN, reconnect=True)