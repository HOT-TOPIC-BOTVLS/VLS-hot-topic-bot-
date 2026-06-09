"""Utility commands cog for Hot Helper bot."""

import discord
from discord.ext import commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()

class Utility(commands.Cog):
    """Utility commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="poll")
    async def poll(self, ctx, question: str, *options):
        """Create a reaction-based poll."""
        try:
            if len(options) < 2:
                await ctx.send("❌ At least 2 options required.")
                return
            
            if len(options) > 4:
                await ctx.send("❌ Maximum 4 options allowed.")
                return
            
            reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
            
            embed = discord.Embed(
                title="📊 Poll",
                description=question,
                color=EMBED_COLOR_BLACK
            )
            
            for i, option in enumerate(options):
                embed.add_field(name=f"{reactions[i]} {option}", value="", inline=False)
            
            message = await ctx.send(embed=embed)
            
            for i in range(len(options)):
                await message.add_reaction(reactions[i])
            
            logger.info(f"Poll created in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in poll command: {e}", exc_info=True)
            await ctx.send("❌ Error creating poll.")
    
    @commands.command(name="rules")
    async def rules(self, ctx):
        """Post server rules."""
        try:
            embed = discord.Embed(
                title="📋 Server Rules",
                description="Please follow these rules to maintain a healthy community.",
                color=EMBED_COLOR_BLACK
            )
            
            embed.add_field(
                name="1. Be Respectful",
                value="Treat all members with respect. No harassment, hate speech, or discrimination.",
                inline=False
            )
            embed.add_field(
                name="2. No Spam",
                value="Don't spam messages, links, or ads. Keep conversations on-topic.",
                inline=False
            )
            embed.add_field(
                name="3. No NSFW Content",
                value="Keep the server family-friendly. No explicit images or language.",
                inline=False
            )
            embed.add_field(
                name="4. Follow Discord ToS",
                value="Comply with Discord's Terms of Service at all times.",
                inline=False
            )
            embed.add_field(
                name="5. Listen to Moderators",
                value="Moderators enforce the rules. Follow their instructions.",
                inline=False
            )
            
            embed.set_footer(text="Violations may result in warnings, mutes, or bans.")
            
            await ctx.send(embed=embed)
            logger.info(f"Rules posted in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in rules command: {e}", exc_info=True)
            await ctx.send("❌ Error posting rules.")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send welcome DM to new members."""
        try:
            guild_config = db.get_guild_config(member.guild.id)
            if not guild_config:
                return
            
            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description="We're glad you joined our community.",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(
                name="Getting Started",
                value="1. Read the rules\n2. Verify your account\n3. Introduce yourself",
                inline=False
            )
            embed.add_field(
                name="Need Help?",
                value="Contact a moderator or check the pinned messages.",
                inline=False
            )
            
            try:
                await member.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Could not DM user {member.id}")
            
            logger.info(f"Welcome DM sent to {member.id} in guild {member.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in on_member_join: {e}", exc_info=True)
    
    @commands.command(name="ping")
    async def ping(self, ctx):
        """Check bot latency."""
        try:
            latency = round(self.bot.latency * 1000)
            await ctx.send(f"🏓 Pong! Latency: {latency}ms")
        except Exception as e:
            logger.error(f"Error in ping command: {e}", exc_info=True)
            await ctx.send("❌ Error checking latency.")
    
    @commands.command(name="serverinfo")
    async def server_info(self, ctx):
        """Get server information."""
        try:
            guild = ctx.guild
            embed = discord.Embed(
                title=f"Server Info: {guild.name}",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
            embed.add_field(name="Members", value=str(guild.member_count), inline=True)
            embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
            embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
            embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
            
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in server_info command: {e}", exc_info=True)
            await ctx.send("❌ Error retrieving server info.")

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Utility(bot))
