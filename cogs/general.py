import discord
from discord.ext import commands

import config

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.command()
    async def help(self, ctx):
        embed = discord.Embed(
            title="🤖 RuneJerry Commands",
            color=discord.Color.blue()
        )

        embed.add_field(name="⭐ Leveling", value="`#rank` - See your current level and XP\n`#leaderboard` - See the top 10 members by XP\n`#levelreset [user]` - Reset a user's level or all levels (Owner Only)", inline=False)
        embed.add_field(name="💬 Messaging (Owner Only)", value="`#reply <user_id> <message>` - Reply to a user via DM\n`#say <channel_id> <message>` - Send a message to a specific channel", inline=False)
        embed.add_field(name="🔍 Roblox Search", value="`#roblox <username>` - Search for public Roblox account details", inline=False)
        embed.add_field(name="🎉 Giveaways (Owner Only)", value="`#giveaway start <duration> <winners> <prize>` - Start a giveaway\n`#giveaway reroll <message_id>` - Reroll a giveaway", inline=False)
        embed.add_field(name="⚙️ General", value="`#status` - Shows the status of the server\n`#ping` - Shows the bot's latency\n`#setpresence <type> <text>` - Change the bot's status (Owner Only)", inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def status(self, ctx):
        # Shows status of the server
        guild = ctx.guild
        if not guild:
            await ctx.send("This command can only be used in a server.")
            return
            
        embed = discord.Embed(title=f"Server Status: {guild.name}", color=discord.Color.green())
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Created At", value=guild.created_at.strftime("%d %b %Y"), inline=False)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        await ctx.send(embed=embed)

    @commands.command(name="setpresence")
    async def set_presence(self, ctx, activity_type: str, *, text: str):
        if not config.is_owner(ctx.author.id):
            return

        activity_type = activity_type.lower()

        if activity_type == "playing":
            activity = discord.Game(name=text)
        elif activity_type == "watching":
            activity = discord.Activity(type=discord.ActivityType.watching, name=text)
        elif activity_type == "listening":
            activity = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif activity_type == "competing":
            activity = discord.Activity(type=discord.ActivityType.competing, name=text)
        else:
            await ctx.send("Invalid type.")
            return

        await self.bot.change_presence(activity=activity)
        await ctx.send("Status updated.")

async def setup(bot):
    await bot.add_cog(General(bot))