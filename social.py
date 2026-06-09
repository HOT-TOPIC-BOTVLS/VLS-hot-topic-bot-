"""Social and leveling system cog for Hot Helper bot."""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()

# XP cooldown to prevent spam
XP_COOLDOWN = 60  # seconds between XP gains per user
XP_PER_MESSAGE = 10  # base XP per message
XP_PER_REACTION = 5  # XP for giving reactions

class Social(commands.Cog):
    """Social and leveling system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldowns = {}  # user_id -> last_xp_time
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP for messages."""
        try:
            if message.author.bot or not message.guild:
                return
            
            user_id = message.author.id
            guild_id = message.guild.id
            
            # Check cooldown
            now = datetime.utcnow()
            last_xp = self.xp_cooldowns.get(user_id, now - timedelta(seconds=XP_COOLDOWN + 1))
            
            if (now - last_xp).total_seconds() < XP_COOLDOWN:
                return
            
            # Award XP
            self.xp_cooldowns[user_id] = now
            
            # Calculate XP based on message length
            xp_amount = XP_PER_MESSAGE + (len(message.content) // 10)
            leveled_up = db.add_xp(user_id, guild_id, xp_amount)
            
            # Update message stats
            db.add_user_stat(user_id, guild_id, "messages", 1)
            
            # Announce level up
            if leveled_up:
                user_xp = db.get_user_xp(user_id, guild_id)
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{message.author.mention} reached **Level {user_xp['level']}**!",
                    color=EMBED_COLOR_BLACK
                )
                embed.add_field(name="Total XP", value=f"{user_xp['total_xp']} XP", inline=False)
                
                try:
                    await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass
                
                logger.info(f"User {user_id} leveled up to {user_xp['level']} in guild {guild_id}")
        
        except Exception as e:
            logger.error(f"Error in on_message XP: {e}", exc_info=True)
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Award XP for reactions."""
        try:
            if user.bot or not reaction.message.guild:
                return
            
            guild_id = reaction.message.guild.id
            
            # Award XP to reactor
            db.add_xp(user.id, guild_id, XP_PER_REACTION)
            db.add_user_stat(user.id, guild_id, "reactions", 1)
            
            logger.debug(f"User {user.id} earned XP for reaction in guild {guild_id}")
        
        except Exception as e:
            logger.error(f"Error in on_reaction_add XP: {e}", exc_info=True)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track voice chat time."""
        try:
            if member.bot or not member.guild:
                return
            
            guild_id = member.guild.id
            
            # User joined voice
            if before.channel is None and after.channel is not None:
                # Store join time in memory (simplified)
                if not hasattr(self, 'voice_joins'):
                    self.voice_joins = {}
                self.voice_joins[member.id] = datetime.utcnow()
            
            # User left voice
            elif before.channel is not None and after.channel is None:
                if hasattr(self, 'voice_joins') and member.id in self.voice_joins:
                    join_time = self.voice_joins[member.id]
                    voice_minutes = int((datetime.utcnow() - join_time).total_seconds() / 60)
                    
                    if voice_minutes > 0:
                        # Award XP (1 XP per minute)
                        db.add_xp(member.id, guild_id, voice_minutes)
                        db.add_user_stat(member.id, guild_id, "voice", voice_minutes)
                        
                        logger.info(f"User {member.id} earned {voice_minutes} XP for voice chat in guild {guild_id}")
                    
                    del self.voice_joins[member.id]
        
        except Exception as e:
            logger.error(f"Error in on_voice_state_update: {e}", exc_info=True)
    
    @commands.command(name="rank")
    async def rank(self, ctx, user: discord.User = None):
        """Show user's rank and XP."""
        try:
            target = user or ctx.author
            
            user_xp = db.get_user_xp(target.id, ctx.guild.id)
            if not user_xp:
                await ctx.send(f"❌ {target.mention} has no XP yet.")
                return
            
            rank = db.get_user_rank(target.id, ctx.guild.id)
            xp_to_next = (user_xp['level'] * 100) - user_xp['total_xp']
            
            embed = discord.Embed(
                title=f"📊 {target.name}'s Rank",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Level", value=str(user_xp['level']), inline=True)
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            embed.add_field(name="Total XP", value=f"{user_xp['total_xp']} XP", inline=True)
            embed.add_field(name="XP to Next Level", value=f"{xp_to_next} XP", inline=False)
            
            # Progress bar
            progress = int((user_xp['xp'] / (user_xp['level'] * 100)) * 20)
            progress_bar = "█" * progress + "░" * (20 - progress)
            embed.add_field(name="Progress", value=f"`{progress_bar}`", inline=False)
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            await ctx.send(embed=embed)
            logger.info(f"Rank command used for {target.id} in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in rank command: {e}", exc_info=True)
            await ctx.send("❌ Error retrieving rank.")
    
    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx, page: int = 1):
        """Show server leaderboard."""
        try:
            limit = 10
            offset = (page - 1) * limit
            
            leaderboard = db.get_leaderboard(ctx.guild.id, limit=limit + offset)
            
            if not leaderboard:
                await ctx.send("📭 No users on leaderboard yet.")
                return
            
            leaderboard = leaderboard[offset:offset + limit]
            
            embed = discord.Embed(
                title="🏆 Server Leaderboard",
                description=f"Page {page}",
                color=EMBED_COLOR_BLACK
            )
            
            for i, user_data in enumerate(leaderboard, start=offset + 1):
                user = await self.bot.fetch_user(user_data['user_id'])
                embed.add_field(
                    name=f"#{i} - {user.name}",
                    value=f"Level {user_data['level']} • {user_data['total_xp']} XP",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            logger.info(f"Leaderboard displayed (page {page}) in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}", exc_info=True)
            await ctx.send("❌ Error retrieving leaderboard.")
    
    @commands.command(name="stats")
    async def stats(self, ctx, user: discord.User = None):
        """Show user statistics."""
        try:
            target = user or ctx.author
            
            user_stats = db.get_user_stats(target.id, ctx.guild.id)
            if not user_stats:
                await ctx.send(f"❌ {target.mention} has no stats yet.")
                return
            
            embed = discord.Embed(
                title=f"📈 {target.name}'s Statistics",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Messages Sent", value=str(user_stats['messages_sent']), inline=True)
            embed.add_field(name="Reactions Given", value=str(user_stats['reactions_given']), inline=True)
            embed.add_field(name="Voice Minutes", value=f"{user_stats['voice_minutes']} min", inline=True)
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            await ctx.send(embed=embed)
            logger.info(f"Stats command used for {target.id} in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in stats command: {e}", exc_info=True)
            await ctx.send("❌ Error retrieving statistics.")
    
    @commands.command(name="addxp")
    @commands.has_permissions(administrator=True)
    async def add_xp(self, ctx, user: discord.User, amount: int):
        """Manually add XP to a user (admin only)."""
        try:
            if amount < 0:
                await ctx.send("❌ XP amount must be positive.")
                return
            
            leveled_up = db.add_xp(user.id, ctx.guild.id, amount)
            user_xp = db.get_user_xp(user.id, ctx.guild.id)
            
            embed = discord.Embed(
                title="✅ XP Added",
                description=f"Added {amount} XP to {user.mention}",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="New Level", value=str(user_xp['level']), inline=True)
            embed.add_field(name="Total XP", value=f"{user_xp['total_xp']} XP", inline=True)
            
            if leveled_up:
                embed.add_field(name="Bonus", value="🎉 Level Up!", inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f"Admin {ctx.author.id} added {amount} XP to {user.id} in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in addxp command: {e}", exc_info=True)
            await ctx.send("❌ Error adding XP.")
    
    @commands.command(name="resetxp")
    @commands.has_permissions(administrator=True)
    async def reset_xp(self, ctx, user: discord.User):
        """Reset a user's XP (admin only)."""
        try:
            db.add_xp(user.id, ctx.guild.id, -999999)  # Crude but effective
            await ctx.send(f"✅ XP reset for {user.mention}")
            logger.info(f"Admin {ctx.author.id} reset XP for {user.id} in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in resetxp command: {e}", exc_info=True)
            await ctx.send("❌ Error resetting XP.")

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Social(bot))
