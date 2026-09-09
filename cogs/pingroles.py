"""Self-assignable notification roles.

Posts a panel with two buttons so members opt into upload and go-live pings
themselves. This is what lets the notification cogs ping a role instead of
@everyone -- people who want the alert still get it, and everyone else stops
being nagged on every upload.
"""

import logging

import discord
from discord.ext import commands

import config

log = logging.getLogger("runejerry.pingroles")


class PingRoleView(discord.ui.View):
    """Persistent view: custom_ids let the buttons keep working after a restart."""

    def __init__(self):
        super().__init__(timeout=None)

    async def _toggle(self, interaction: discord.Interaction, role_id: int, label: str):
        if not role_id:
            return await interaction.response.send_message(
                f"❌ The {label} role isn't configured yet.", ephemeral=True
            )

        role = interaction.guild.get_role(role_id)
        if role is None:
            log.warning("Ping role %s (%s) not found in %s", label, role_id, interaction.guild)
            return await interaction.response.send_message(
                f"❌ The {label} role no longer exists. Let a mod know.", ephemeral=True
            )

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Opted out of pings")
                await interaction.response.send_message(
                    f"🔕 Removed **{role.name}** — you won't be pinged.", ephemeral=True
                )
            else:
                await interaction.user.add_roles(role, reason="Opted into pings")
                await interaction.response.send_message(
                    f"🔔 Added **{role.name}** — you'll be pinged.", ephemeral=True
                )
        except discord.Forbidden:
            # Almost always the bot's own role sitting below the ping role.
            log.warning("Missing permission to manage role %s", role_id)
            await interaction.response.send_message(
                "❌ I can't manage that role. My role needs to sit above it.", ephemeral=True
            )
        except discord.HTTPException as e:
            # Any other API failure still has to answer the interaction, or the
            # member is left staring at "This interaction failed".
            log.warning("Failed to toggle role %s: %s", role_id, e)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Something went wrong. Try again in a moment.", ephemeral=True
                )

    @discord.ui.button(label="Video Ping", style=discord.ButtonStyle.primary,
                       emoji="🎥", custom_id="pingroles:video")
    async def video(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, config.VIDEO_PING_ROLE_ID, "Video Ping")

    @discord.ui.button(label="Live Ping", style=discord.ButtonStyle.danger,
                       emoji="🔴", custom_id="pingroles:live")
    async def live(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, config.LIVE_PING_ROLE_ID, "Live Ping")


class PingRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Re-register so the buttons survive restarts.
        self.bot.add_view(PingRoleView())

    @commands.command(name="pingroles")
    @commands.guild_only()
    @commands.is_owner()
    async def pingroles(self, ctx):
        """Post the notification role opt-in panel."""
        embed = discord.Embed(
            title="🔔 Notification Roles",
            description=(
                "Pick what you want to be pinged for. Click again to turn it off.\n\n"
                "🎥 **Video Ping** — new YouTube uploads\n"
                "🔴 **Live Ping** — streams on Kick and YouTube"
            ),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed, view=PingRoleView())


async def setup(bot):
    await bot.add_cog(PingRoles(bot))
