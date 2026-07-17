import discord
from discord.ext import commands
import aiohttp
import asyncio
import datetime
import logging

log = logging.getLogger("runejerry.roblox")

class RobloxSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def cog_load(self):
        """Called when the cog is loaded."""
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        if self.session:
            await self.session.close()

    async def get_roblox_user_id(self, username: str):
        """Fetch basic user data from Roblox API by username."""
        url = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username], "excludeBannedUsers": False}
        
        try:
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data"):
                        return data["data"][0]  # Keys: id, name, displayName
                return None
        except Exception:
            return None

    async def get_user_details(self, user_id: int):
        """Fetch advanced user details from Roblox API by ID."""
        url = f"https://users.roblox.com/v1/users/{user_id}"
        
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception:
            return None

    async def get_roblox_avatar(self, user_id: int):
        """Fetch user avatar from Roblox API."""
        url = f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png&isCircular=false"
        
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data") and len(data["data"]) > 0:
                        return data["data"][0].get("imageUrl")
                return None
        except Exception:
            return None

    @commands.hybrid_command(name="roblox", aliases=["rbx", "rblx"], help="Search for a Roblox player's public profile.")
    async def roblox(self, ctx: commands.Context, *, username: str):
        """Search and display public Roblox account details."""
        async with ctx.typing():
            try:
                # 1. Get ID from Username
                basic_user = await self.get_roblox_user_id(username)
                
                if not basic_user:
                    embed = discord.Embed(
                        title="❌ User Not Found",
                        description=f"Could not find a valid public Roblox user named `{username}`.",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
                    
                user_id = basic_user["id"]
                display_name = basic_user.get("displayName", basic_user.get("name"))
                actual_name = basic_user.get("name")
                
                # 2. Get Advanced Details
                details = await self.get_user_details(user_id)
                # Fallback if details endpoint fails but basic lookup succeeded
                if not details:
                    details = {"description": "", "created": None, "isBanned": False}
                    
                # 3. Get Avatar
                avatar_url = await self.get_roblox_avatar(user_id)
                if not avatar_url:
                    avatar_url = "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/420/420/Avatar/Png"
                    
                # Prepare description snippet
                desc = details.get("description") or ""
                if len(desc) > 300:
                    desc = desc[:297] + "..."
                if not desc.strip():
                    desc = "*No description provided.*"
                    
                embed = discord.Embed(
                    title=f"Roblox Profile: {display_name}",
                    url=f"https://www.roblox.com/users/{user_id}/profile",
                    description=f"**Bio**\n{desc}",
                    color=discord.Color.blue()
                )
                
                embed.set_thumbnail(url=avatar_url)
                embed.add_field(name="Username", value=actual_name, inline=True)
                embed.add_field(name="User ID", value=str(user_id), inline=True)
                
                if details.get("isBanned"):
                    embed.add_field(name="Status", value="🚫 **Banned**", inline=True)
                else:
                    embed.add_field(name="Status", value="✅ **Active**", inline=True)
                    
                if details.get("created"):
                    try:
                        # Roblox returns datetime like "2013-08-20T19:27:03.493Z"
                        created_dt = datetime.datetime.fromisoformat(details["created"].replace("Z", "+00:00"))
                        embed.add_field(name="Join Date", value=f"<t:{int(created_dt.timestamp())}:D>", inline=True)
                    except Exception:
                        pass
                        
                await ctx.send(embed=embed)
                
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="⏳ Request Timed Out",
                    description="The Roblox API is taking too long to respond. Please try again later.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="⚠️ Error",
                    description="An unexpected error occurred while searching for this user.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                log.warning("Roblox search error: %s", e)

async def setup(bot):
    await bot.add_cog(RobloxSearch(bot))
