import discord
from discord.ext import commands

import config

# Pretty labels for cog names. Cogs without an entry fall back to their class
# name, so a newly added cog still shows up in #help without touching this map.
COG_LABELS = {
    "General": "⚙️ General",
    "Leveling": "⭐ Leveling",
    "RobloxSearch": "🔍 Roblox",
    "Giveaway": "🎉 Giveaways",
    "Messaging": "💬 Messaging",
    "RaidProtection": "🛡️ Moderation",
    "PingRoles": "🔔 Notifications",
}
# Cogs are listed in this order first; anything else follows alphabetically.
COG_ORDER = ["General", "Leveling", "RobloxSearch", "Giveaway", "Messaging",
             "PingRoles", "RaidProtection"]

OWNER_BADGE = "👑"
FIELD_LIMIT = 1024  # Discord's per-field character cap


def _owner_check_qualname() -> str:
    """Ask discord.py itself what its is_owner check is called.

    Deriving the name from the library beats hardcoding "is_owner": there's no
    public API for reading a command's checks, so if the internal name ever
    changes this follows it instead of silently dropping the owner badge.
    """
    @commands.is_owner()
    async def _probe(ctx):
        ...

    checks = getattr(_probe, "__commands_checks__", [])
    return getattr(checks[0], "__qualname__", "is_owner") if checks else "is_owner"


OWNER_CHECK_QUALNAME = _owner_check_qualname()


def is_owner_only(command: commands.Command) -> bool:
    """True if a command is restricted to bot owners.

    Detects the @commands.is_owner() check, and honours an explicit
    extras={"owner_only": True} for commands that check ownership by hand.
    """
    if command.extras.get("owner_only"):
        return True
    if any(getattr(c, "__qualname__", "") == OWNER_CHECK_QUALNAME for c in command.checks):
        return True
    return command.parent is not None and is_owner_only(command.parent)


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Show the bot's latency."""
        await ctx.send(f"Pong! {round(self.bot.latency * 1000)}ms")

    def _describe(self, command: commands.Command) -> str:
        """Render one command as a single help line."""
        prefix = config.COMMAND_PREFIX
        signature = f" {command.signature}" if command.signature else ""
        line = f"`{prefix}{command.qualified_name}{signature}`"

        if command.aliases:
            alias_list = ", ".join(f"{prefix}{a}" for a in command.aliases)
            line += f" *(also: {alias_list})*"

        line += f" — {command.short_doc or 'No description.'}"
        if is_owner_only(command):
            line += f" {OWNER_BADGE}"
        return line

    def _collect(self) -> dict[str, list[str]]:
        """Group every visible command (and subcommand) by cog."""
        groups: dict[str, list[str]] = {}
        for command in sorted(self.bot.walk_commands(), key=lambda c: c.qualified_name):
            if command.hidden:
                continue
            cog_name = command.cog_name or "Other"
            groups.setdefault(cog_name, []).append(self._describe(command))
        return groups

    @commands.command()
    async def help(self, ctx):
        """List every available command."""
        groups = self._collect()
        ordered = [name for name in COG_ORDER if name in groups]
        ordered += sorted(name for name in groups if name not in COG_ORDER)

        embed = discord.Embed(
            title="🤖 RuneJerry Commands",
            description=f"{OWNER_BADGE} = owner only",
            color=discord.Color.blue(),
        )

        total = 0
        for cog_name in ordered:
            lines = groups[cog_name]
            total += len(lines)
            label = COG_LABELS.get(cog_name, cog_name)

            # Split across extra fields if a cog ever outgrows the 1024 cap.
            chunk: list[str] = []
            length = 0
            part = 0
            for line in lines:
                if length + len(line) + 1 > FIELD_LIMIT and chunk:
                    part += 1
                    embed.add_field(
                        name=label if part == 1 else f"{label} (cont.)",
                        value="\n".join(chunk),
                        inline=False,
                    )
                    chunk, length = [], 0
                chunk.append(line)
                length += len(line) + 1
            if chunk:
                part += 1
                embed.add_field(
                    name=label if part == 1 else f"{label} (cont.)",
                    value="\n".join(chunk),
                    inline=False,
                )

        embed.set_footer(text=f"{total} commands")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))
