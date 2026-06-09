"""Raid detection and lockdown cog for Hot Helper bot."""

import discord
from discord.ext import commands
from datetime import datetime, timedelta
from collections import defaultdict
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED, DEFAULT_RAID_JOIN_THRESHOLD, DEFAULT_RAID_WINDOW, DEFAULT_RAID_PATTERN_COUNT, RAID_LOCKDOWN_DURATION
import json

db = Database()

class Raid(commands.Cog):
    """Raid detection and lockdown system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.join_tracker = defaultdict(list)  # guild_id -> [(user_id, timestamp), ...]
        self.name_patterns = defaultdict(list)  # guild_id -> [name, name, ...]
        self.locked_down_guilds = set()
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Track member joins for raid detection."""
        try:
            guild = member.guild
            guild_config = db.get_guild_config(guild.id)
            
            if not guild_config:
                return
            
            # Get raid settings
            join_threshold = guild_config.get("raid_join_threshold", DEFAULT_RAID_JOIN_THRESHOLD)
            window = guild_config.get("raid_window", DEFAULT_RAID_WINDOW)
            pattern_count = guild_config.get("raid_pattern_count", DEFAULT_RAID_PATTERN_COUNT)
            
            # Track join
            now = datetime.utcnow()
            self.join_tracker[guild.id].append((member.id, now))
            self.name_patterns[guild.id].append(member.name.lower())
            
            # Clean old entries
            cutoff = now - timedelta(seconds=window)
            self.join_tracker[guild.id] = [(uid, ts) for uid, ts in self.join_tracker[guild.id] if ts > cutoff]
            
            # Check for raid
            join_count = len(self.join_tracker[guild.id])
            
            # Count similar names
            recent_names = self.name_patterns[guild.id][-pattern_count:]
            similar_count = sum(1 for name in recent_names if member.name.lower() in name or name in member.name.lower())
            
            if join_count >= join_threshold or similar_count >= pattern_count:
                await self.trigger_raid(guild, member)
        
        except Exception as e:
            logger.error(f"Error in on_member_join: {e}", exc_info=True)
    
    async def trigger_raid(self, guild, member):
        """Trigger raid lockdown."""
        try:
            if guild.id in self.locked_down_guilds:
                return  # Already locked down
            
            self.locked_down_guilds.add(guild.id)
            
            guild_config = db.get_guild_config(guild.id)
            if not guild_config:
                return
            
            # Save current permissions
            permissions_data = {}
            for channel in guild.channels:
                permissions_data[str(channel.id)] = {}
                for role in guild.roles:
                    overwrite = channel.permissions_for(role)
                    permissions_data[str(channel.id)][str(role.id)] = {
                        "send_messages": overwrite.send_messages,
                        "speak": overwrite.speak
                    }
            
            db.save_raid_state(guild.id, json.dumps(permissions_data))
            
            # Enable lockdown
            for channel in guild.text_channels:
                try:
                    everyone_role = guild.default_role
                    await channel.set_permissions(everyone_role, send_messages=False)
                except:
                    pass
            
            # Post announcement
            announce_channel_id = guild_config.get("announce_channel_id")
            if announce_channel_id:
                announce_channel = guild.get_channel(announce_channel_id)
                if announce_channel:
                    embed = discord.Embed(
                        title="🚨 RAID DETECTED 🚨",
                        description=f"THIS IS NOT A DRILL — RAID DETECTED. {member.mention} attempted to raid at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}. Bot action: banned. PLEASE CONTACT AN ADMIN IMMEDIATELY and inform them of the situation. Report any suspicious activity now.",
                        color=EMBED_COLOR_RED
                    )
                    await announce_channel.send(embed=embed)
            
            # Ban the raider
            try:
                await guild.ban(member, reason="Raid detection")
            except:
                pass
            
            # Log
            log_channel_id = guild_config.get("log_channel_id")
            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🚨 Raid Detected",
                        description=f"Raid triggered by {member.mention}",
                        color=EMBED_COLOR_RED
                    )
                    embed.add_field(name="Action", value="Lockdown enabled, user banned", inline=False)
                    await log_channel.send(embed=embed)
            
            logger.info(f"Raid detected in guild {guild.id}, lockdown enabled")
            # Real raids stay locked until !unlock is used manually
        
        except Exception as e:
            logger.error(f"Error in trigger_raid: {e}", exc_info=True)
    
    async def unlock_server(self, guild):
        """Unlock the server after raid."""
        try:
            if guild.id not in self.locked_down_guilds:
                return
            
            self.locked_down_guilds.remove(guild.id)
            
            # Restore permissions
            raid_state = db.get_raid_state(guild.id)
            if raid_state:
                permissions_data = json.loads(raid_state["permissions_json"])
                
                for channel_id_str, perms in permissions_data.items():
                    channel_id = int(channel_id_str)
                    channel = guild.get_channel(channel_id)
                    if channel:
                        for role_id_str, perm_dict in perms.items():
                            role_id = int(role_id_str)
                            role = guild.get_role(role_id)
                            if role:
                                try:
                                    await channel.set_permissions(
                                        role,
                                        send_messages=perm_dict.get("send_messages"),
                                        speak=perm_dict.get("speak")
                                    )
                                except:
                                    pass
                
                db.clear_raid_state(guild.id)
            
            # Post unlock message
            guild_config = db.get_guild_config(guild.id)
            if guild_config:
                announce_channel_id = guild_config.get("announce_channel_id")
                if announce_channel_id:
                    announce_channel = guild.get_channel(announce_channel_id)
                    if announce_channel:
                        embed = discord.Embed(
                            title="✅ Lockdown Ended",
                            description="Server restored to normal.",
                            color=EMBED_COLOR_BLACK
                        )
                        await announce_channel.send(embed=embed)
            
            logger.info(f"Raid lockdown ended in guild {guild.id}")
        
        except Exception as e:
            logger.error(f"Error in unlock_server: {e}", exc_info=True)
    
    @commands.command(name="drill")
    @commands.is_owner()
    async def drill(self, ctx):
        """Run a raid drill (owner only)."""
        try:
            guild_config = db.get_guild_config(ctx.guild.id)
            if not guild_config:
                await ctx.send("❌ Server not configured.")
                return
            
            if ctx.guild.id in self.locked_down_guilds:
                await ctx.send("❌ Server already locked down.")
                return
            
            self.locked_down_guilds.add(ctx.guild.id)
            
            # Save permissions
            permissions_data = {}
            for channel in ctx.guild.channels:
                permissions_data[str(channel.id)] = {}
                for role in ctx.guild.roles:
                    overwrite = channel.permissions_for(role)
                    permissions_data[str(channel.id)][str(role.id)] = {
                        "send_messages": overwrite.send_messages,
                        "speak": overwrite.speak
                    }
            
            db.save_raid_state(ctx.guild.id, json.dumps(permissions_data))
            
            # Enable lockdown
            for channel in ctx.guild.text_channels:
                try:
                    everyone_role = ctx.guild.default_role
                    await channel.set_permissions(everyone_role, send_messages=False)
                except:
                    pass
            
            # Post announcement
            announce_channel_id = guild_config.get("announce_channel_id")
            if announce_channel_id:
                announce_channel = ctx.guild.get_channel(announce_channel_id)
                if announce_channel:
                    embed = discord.Embed(
                        title="🚨 RAID DRILL 🚨",
                        description="THIS IS A DRILL — RAID DRILL INITIATED BY OWNER. This is only a test. PLEASE CONTACT AN ADMIN and ask them to unlock the server. Stand down once unlocked.",
                        color=EMBED_COLOR_RED
                    )
                    await announce_channel.send(embed=embed)
            
            await ctx.send("✅ Raid drill initiated. Use `!unlock` to end.")
            logger.info(f"Raid drill started in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in drill command: {e}", exc_info=True)
            await ctx.send("❌ Error starting drill.")
    
    @commands.command(name="unlock")
    async def unlock(self, ctx):
        """Unlock the server (admin or owner only)."""
        try:
            guild_config = db.get_guild_config(ctx.guild.id)
            if not guild_config:
                await ctx.send("❌ Server not configured.")
                return
            
            # Check permissions
            if ctx.author.id != guild_config.get("owner_id"):
                admin_role_id = guild_config.get("admin_role_id")
                if not admin_role_id or not ctx.author.get_role(admin_role_id):
                    await ctx.send("❌ You don't have permission to unlock the server.")
                    return
            
            await self.unlock_server(ctx.guild)
            await ctx.send("✅ Server unlocked.")
        
        except Exception as e:
            logger.error(f"Error in unlock command: {e}", exc_info=True)
            await ctx.send("❌ Error unlocking server.")
    
    @commands.command(name="setraidsettings")
    @commands.has_permissions(administrator=True)
    async def set_raid_settings(self, ctx, joins: int, seconds: int, patterns: int):
        """Set raid detection settings."""
        try:
            db.set_guild_config(
                ctx.guild.id,
                raid_join_threshold=joins,
                raid_window=seconds,
                raid_pattern_count=patterns
            )
            await ctx.send(f"✅ Raid settings updated: {joins} joins in {seconds}s or {patterns} similar names")
            logger.info(f"Raid settings updated in guild {ctx.guild.id}")
        except Exception as e:
            logger.error(f"Error in set_raid_settings command: {e}", exc_info=True)
            await ctx.send("❌ Error setting raid settings.")

import asyncio

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Raid(bot))
