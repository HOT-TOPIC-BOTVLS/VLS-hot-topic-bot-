"""Question of the Day (QOTD) cog for Hot Helper bot."""

import discord
from discord.ext import commands, tasks
from datetime import datetime, time
import asyncio
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK

db = Database()

# Default QOTD questions
DEFAULT_QUESTIONS = [
    "If you could have any superpower for a day, what would it be?",
    "What's your favorite Hot Topic memory?",
    "If you could design your own band merchandise, what would it look like?",
    "What's the most underrated music genre?",
    "If you could attend any concert in history, which would it be?",
    "What's your go-to comfort food?",
    "If you could dye your hair any color, what would it be?",
    "What's the best album of the last decade?",
    "If you could live in any fictional universe, which would it be?",
    "What's your unpopular opinion about fashion?",
    "If you could start a band, what would you call it?",
    "What's the most iconic music video ever made?",
    "If you could meet any artist, who would it be?",
    "What's your favorite thing about online communities?",
    "If you could change one thing about the internet, what would it be?",
]

class QOTD(commands.Cog):
    """Question of the Day system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.daily_qotd.start()
        
        # Initialize questions if empty
        if not db.get_random_qotd():
            for question in DEFAULT_QUESTIONS:
                db.add_qotd(question)
    
    def cog_unload(self):
        """Clean up on cog unload."""
        self.daily_qotd.cancel()
    
    @tasks.loop(time=time(10, 0, 0))  # Run at exactly 10:00 AM UTC
    async def daily_qotd(self):
        """Post QOTD daily at 10:00 AM UTC."""
        try:
            # Get a random question
            question = db.get_random_qotd()
            if not question:
                # Reset if all used
                db.reset_qotd()
                question = db.get_random_qotd()
            
            if not question:
                logger.warning("No QOTD questions available")
                return
            
            # Mark as used
            db.mark_qotd_used(question["id"])
            
            # Post to all guilds
            for guild in self.bot.guilds:
                try:
                    guild_config = db.get_guild_config(guild.id)
                    if not guild_config:
                        continue
                    
                    announce_channel_id = guild_config.get("announce_channel_id")
                    if not announce_channel_id:
                        continue
                    
                    channel = guild.get_channel(announce_channel_id)
                    if not channel:
                        continue
                    
                    embed = discord.Embed(
                        title="🎤 Question of the Day",
                        description=f"Somewhere in the world a Hot Topic is opening, here's today's question...\n\n{question['question']}",
                        color=EMBED_COLOR_BLACK
                    )
                    embed.set_footer(text="Reply in the thread to answer!")
                    
                    message = await channel.send(embed=embed)
                    await message.create_thread(name=f"QOTD - {question['id']}")
                    
                except Exception as e:
                    logger.error(f"Error posting QOTD to guild {guild.id}: {e}")
        
        except Exception as e:
            logger.error(f"Error in daily_qotd: {e}", exc_info=True)
    
    @daily_qotd.before_loop
    async def before_daily_qotd(self):
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()
        logger.info("QOTD scheduled for 10:00 AM UTC daily")
    
    @commands.command(name="qotd")
    async def qotd_manual(self, ctx):
        """Post QOTD manually."""
        try:
            # Get a random question
            question = db.get_random_qotd()
            if not question:
                # Reset if all used
                db.reset_qotd()
                question = db.get_random_qotd()
            
            if not question:
                await ctx.send("❌ No QOTD questions available.")
                return
            
            # Mark as used
            db.mark_qotd_used(question["id"])
            
            embed = discord.Embed(
                title="🎤 Question of the Day",
                description=f"Somewhere in the world a Hot Topic is opening, here's today's question...\n\n{question['question']}",
                color=EMBED_COLOR_BLACK
            )
            embed.set_footer(text="Reply in the thread to answer!")
            
            message = await ctx.send(embed=embed)
            await message.create_thread(name=f"QOTD - {question['id']}")
            
            logger.info(f"QOTD posted manually in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in qotd_manual command: {e}", exc_info=True)
            await ctx.send("❌ Error posting QOTD.")
    
    @commands.command(name="addqotd")
    @commands.is_owner()
    async def add_qotd(self, ctx, *, question: str):
        """Add a QOTD question (owner only)."""
        try:
            db.add_qotd(question)
            await ctx.send("✅ Question added to QOTD pool.")
            logger.info(f"QOTD question added by {ctx.author.id}")
        except Exception as e:
            logger.error(f"Error in add_qotd command: {e}", exc_info=True)
            await ctx.send("❌ Error adding question.")

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(QOTD(bot))
