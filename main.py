import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")
OWNER_IDS_STR = os.getenv("OWNER_IDS")

owner_ids = set()
if OWNER_ID and OWNER_ID.strip().isdigit():
    owner_ids.add(int(OWNER_ID.strip()))
if OWNER_IDS_STR:
    for oid in OWNER_IDS_STR.split(","):
        oid = oid.strip()
        if oid.isdigit():
            owner_ids.add(int(oid))

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True

kwargs = {
    "command_prefix": "#",
    "intents": intents,
    "help_command": None
}
if owner_ids:
    kwargs["owner_ids"] = owner_ids

bot = commands.Bot(**kwargs)

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
        "cogs.roblox",
        "cogs.giveaway"
    ]:
        await bot.load_extension(ext)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# 🔥 ONLY ONE PLACE PROCESSING COMMANDS
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

def run():
    bot.run(TOKEN, reconnect=True)