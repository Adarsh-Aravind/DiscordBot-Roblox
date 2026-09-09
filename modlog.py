"""Shared helper for reporting automated moderation actions to a log channel.

Keeps an audit trail of what the bot did on its own -- without one there's no
way to tell a working filter apart from one that's quietly misfiring.
"""

import logging

import discord

import config

log = logging.getLogger("runejerry.modlog")


async def send(bot, embed: discord.Embed) -> None:
    """Post an embed to the configured mod-log channel, if there is one."""
    if not config.MOD_LOG_CHANNEL_ID:
        return

    channel = bot.get_channel(config.MOD_LOG_CHANNEL_ID)
    if channel is None:
        # Not in the cache (e.g. the bot just started): ask the API once.
        try:
            channel = await bot.fetch_channel(config.MOD_LOG_CHANNEL_ID)
        except (discord.HTTPException, discord.InvalidData) as e:
            log.warning("Mod log channel %s unavailable: %s", config.MOD_LOG_CHANNEL_ID, e)
            return

    try:
        await channel.send(embed=embed)
    except discord.HTTPException as e:
        log.warning("Failed to write to mod log: %s", e)


def action_embed(title: str, colour: discord.Color, member, reason: str) -> discord.Embed:
    """Build a consistent embed for a moderation action taken against a member."""
    embed = discord.Embed(title=title, description=reason, color=colour)
    embed.add_field(name="Member", value=f"{member} ({member.mention})", inline=False)
    embed.set_footer(text=f"User ID: {member.id}")
    embed.timestamp = discord.utils.utcnow()
    return embed
