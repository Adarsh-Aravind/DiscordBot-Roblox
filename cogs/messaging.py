import logging

import discord
from discord.ext import commands

import config

log = logging.getLogger("runejerry.messaging")


class Messaging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._owner = None  # cached owner User for DM relaying

    async def _get_owner(self):
        if self._owner is None:
            self._owner = await self.bot.fetch_user(config.PRIMARY_OWNER_ID)
        return self._owner

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.DMChannel):
            return

        # Don't relay the owner's own DMs back to themselves.
        if config.is_owner(message.author.id):
            return

        embed = discord.Embed(
            title=f"📩 DM from {message.author}",
            description=message.content or "*No text*",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"User ID: {message.author.id}")

        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join(a.url for a in message.attachments),
                inline=False,
            )

        try:
            owner = await self._get_owner()
            await owner.send(embed=embed)
        except discord.HTTPException as e:
            log.warning("Failed to relay DM from %s: %s", message.author.id, e)

    @commands.command()
    @commands.is_owner()
    async def reply(self, ctx, user_id: int, *, content):
        """DM a user by ID (used to answer relayed DMs)."""
        try:
            user = await self.bot.fetch_user(user_id)
            await user.send(content)
            await ctx.send("Sent.")
        except discord.NotFound:
            await ctx.send("❌ No user found with that ID.")
        except discord.Forbidden:
            await ctx.send("❌ Can't DM that user (they may share no server or have DMs closed).")

    @commands.command()
    @commands.is_owner()
    async def say(self, ctx, channel_id: int, *, content):
        """Send a message to a channel by ID as the bot."""
        try:
            channel = await self.bot.fetch_channel(channel_id)
            await channel.send(content)
            await ctx.send("Message sent.")
        except discord.NotFound:
            await ctx.send("❌ No channel found with that ID.")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages there.")


async def setup(bot):
    await bot.add_cog(Messaging(bot))
