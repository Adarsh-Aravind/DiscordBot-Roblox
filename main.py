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
# Raid protection counts joins, which needs the privileged Server Members
# Intent. It must ALSO be enabled in the Discord Developer Portal
# (Bot -> Privileged Gateway Intents) or login fails outright.
intents.members = True

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
        "cogs.raid",
        "cogs.pingroles",
        "cogs.youtube",
        "cogs.kick",
        "cogs.roblox",
        "cogs.giveaway",
        "cogs.heartbeat"
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

@bot.event
async def on_command_error(ctx, error):
    # The "." prefix means plenty of ordinary chat ("...", ".", ".gg") parses as
    # a command. discord.py's default handler logs an ERROR + traceback for each
    # one, so unknown commands are swallowed here instead of flooding the log.
    if isinstance(error, commands.CommandNotFound):
        return

    # Owner-only commands stay invisible to everyone else.
    if isinstance(error, commands.NotOwner):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        usage = f"{config.COMMAND_PREFIX}{ctx.command.qualified_name} {ctx.command.signature}"
        await ctx.send(f"❌ Missing `{error.param.name}`. Usage: `{usage.strip()}`")
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ I couldn't understand one of those arguments.")
        return

    log.error("Error in command %s", ctx.command, exc_info=error)

def run():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Add it to your .env file.")
    try:
        bot.run(TOKEN, reconnect=True)
    except discord.PrivilegedIntentsRequired:
        # Raid protection needs the members intent, which Discord gates behind
        # a portal toggle. The library's own error doesn't say which switch.
        raise RuntimeError(
            "Discord rejected the privileged intents this bot requires.\n"
            "Enable the SERVER MEMBERS INTENT at "
            "https://discord.com/developers/applications -> your app -> Bot -> "
            "Privileged Gateway Intents, then start the bot again."
        ) from None


if __name__ == "__main__":
    run()
