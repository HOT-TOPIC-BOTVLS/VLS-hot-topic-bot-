"""Moderation system cog for Hot Helper bot."""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED, MUTE_ROLE_NAME, MOD_MAX_MUTE, ADMIN_MAX_MUTE, MIN_MUTE_DURATION

db = Database()

def parse_duration(duration_str):
    """Parse duration string to seconds."""
    if not duration_str:
        return None
        
    duration_str = "".join(duration_str.lower().split())
    
    if duration_str in ["infinite", "permanent", "forever"]:
        return None
    
    multipliers = {
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
        "w": 7 * 24 * 60 * 60,
    }
    
    for suffix, multiplier in multipliers.items():
        if duration_str.endswith(suffix):
            try:
                value_str = duration_str[:-1]
                if not value_str.isdigit():
                    return None
                value = int(value_str)
                return value * multiplier
            except ValueError:
                return None
    
    return None

def get_user_role_level(user, guild_config):
    """Get user's role level (0=user, 1=mod, 2=admin, 3=owner)."""
    if user.id == guild_config.get("owner_id"):
        return 3
    
    admin_role_id = guild_config.get("admin_role_id")
    mod_role_id = guild_config.get("mod_role_id")
    
    if admin_role_id and user.get_role(admin_role_id):
        return 2
    if mod_role_id and user.get_role(mod_role_id):
        return 1
    
    return 0

class Moderation(commands.Cog):
    """Moderation commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="warn")
    async def warn(self, ctx, user: discord.User, *, situation: str):
        """Warn a user."""
        try:
            guild_config = db.get_guild_config(ctx.guild.id)
            if not guild_config:
                await ctx.send("❌ Server not configured.")
                return
            
            user_level = get_user_role_level(ctx.author, guild_config)
            if user_level < 1:
                await ctx.send("❌ You don't have permission to warn users.")
                return
            
            # Add warning
            warning_num = db.add_warning(user.id, ctx.guild.id, situation, ctx.author.id)
            
            # Get log channel
            log_channel_id = guild_config.get("log_channel_id")
            if log_channel_id:
                log_channel = ctx.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="⚠️ User Warned",
                        description=f"{user.mention} has been warned (Warning #{warning_num})",
                        color=EMBED_COLOR_RED
                    )
                    embed.add_field(name="Situation", value=situation, inline=False)
                    embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                    embed.set_footer(text=f"User ID: {user.id}")
                    await log_channel.send(embed=embed)
            
            await ctx.send(f"✅ {user.mention} warned (Warning #{warning_num})")
            logger.info(f"User {user.id} warned in guild {ctx.guild.id} by {ctx.author.id}")
            
        except Exception as e:
            logger.error(f"Error in warn command: {e}", exc_info=True)
            await ctx.send("❌ Error warning user.")
    
    @commands.command(name="kick")
    async def kick(self, ctx, user: discord.User, *, situation: str):
        """Kick a user."""
        try:
            guild_config = db.get_guild_config(ctx.guild.id)
            if not guild_config:
                await ctx.send("❌ Server not configured.")
                return
            
            user_level = get_user_role_level(ctx.author, guild_config)
            if user_level < 1:
                await ctx.send("❌ You don't have permission to kick users.")
                return
            
            member = ctx.guild.get_member(user.id)
            if not member:
                await ctx.send("❌ User not found in this server.")
                return
            
            # Kick user
            await member.kick(reason=situation)
            
            # Log
            log_channel_id = guild_config.get("log_channel_id")
            if log_channel_id:
                log_channel = ctx.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="👢 User Kicked",
                        description=f"{user.mention} has been kicked",
                        color=EMBED_COLOR_RED
                    )
                    embed.add_field(name="Reason", value=situation, inline=False)
                    embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                    embed.set_footer(text=f"User ID: {user.id}")
                    await log_channel.send(embed=embed)
            
            await ctx.send(f"✅ {user.mention} kicked")
            logger.info(f"User {user.id} kicked from guild {ctx.guild.id} by {ctx.author.id}")
            
        except Exception as e:
            logger.error(f"Error in kick command: {e}", exc_info=True)
            await ctx.send("❌ Error kicking user.")
    
    @commands.command(name="ban")
    async def ban(self, ctx, user: discord.User, *, situation: str):
        """Ban a user."""
        try:
            guild_config = db.get_guild_config(ctx.guild.id)
            if not guild_config:
                await ctx.send("❌ Server not configured.")
                return
            
            user_level = get_user_role_level(ctx.author, guild_config)
            if user_level < 2:
                await ctx.send("❌ You don't have permission to ban users.")
                return
            
            # Ban user
            await ctx.guild.ban(user, reason=situation)
            
            # Log
            log_channel_id = guild_config.get("log_channel_id")
            if log_channel_id:
                log_channel = ctx.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🔨 User Banned",
                        description=f"{user.mention} has been banned",
                        color=EMBED_COLOR_RED
                    )
                    embed.add_field(name="Reason", value=situation, inline=False)
                    embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                    embed.set_footer(text=f"User ID: {user.id}")
                    await log_channel.send(embed=embed)
            
            await ctx.send(f"✅ {user.mention} banned")
            logger.info(f"User {user.id} banned from guild {ctx.guild.id} by {ctx.author.id}")
            
        except Exception as e:
            logger.error(f"Error in ban command: {e}", exc_info=True)
            await ctx.send("❌ Error banning user.")
    
    @commands.command(name="mute")
    async def mute(self, ctx, user: discord.User, duration: str, *, situation: str):
        """Mute a user."""
        try:
            guild_config = db.get_guild_config(ctx.guild.id)
            if not guild_config:
                await ctx.send("❌ Server not configured.")
                return
            
            user_level = get_user_role_level(ctx.author, guild_config)
            if user_level < 1:
                await ctx.send("❌ You don't have permission to mute users.")
                return
            
            # Parse duration
            duration_seconds = parse_duration(duration)
            if duration_seconds is None and duration.lower() not in ["infinite", "permanent", "forever"]:
                await ctx.send("❌ Invalid duration format. Use: 5m, 1h, 1d, 1w, 30d, infinite, permanent")
                return
            
            # Check duration limits
            if duration_seconds:
                if user_level == 1 and duration_seconds > MOD_MAX_MUTE:
                    await ctx.send(f"❌ Mods can only mute up to 7 days.")
                    return
                if user_level == 2 and duration_seconds > ADMIN_MAX_MUTE:
                    await ctx.send(f"❌ Admins can only mute up to 30 days.")
                    return
            
            # Check if approval needed
            needs_approval = False
            if duration_seconds and user_level < 3:
                if user_level == 1 and duration_seconds > MOD_MAX_MUTE:
                    needs_approval = True
                elif user_level == 2 and duration_seconds > ADMIN_MAX_MUTE:
                    needs_approval = True
            elif duration_seconds is None and user_level < 3:
                needs_approval = True
            
            # Create muted role if needed
            muted_role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
            if not muted_role:
                try:
                    muted_role = await ctx.guild.create_role(name=MUTE_ROLE_NAME, color=discord.Color.dark_gray())
                    # Set permissions in all channels
                    for channel in ctx.guild.channels:
                        await channel.set_permissions(muted_role, send_messages=False, speak=False)
                except Exception as e:
                    logger.error(f"Error creating muted role: {e}")
                    await ctx.send("❌ Error creating muted role.")
                    return
            
            member = ctx.guild.get_member(user.id)
            if not member:
                await ctx.send("❌ User not found in this server.")
                return
            
            # Calculate expiry
            expires_at = None
            if duration_seconds:
                expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
            
            if needs_approval:
                # Add to pending approvals
                approval_id = db.add_pending_approval(
                    user.id,
                    ctx.guild.id,
                    "mute",
                    duration_seconds,
                    situation,
                    ctx.author.id
                )
                await ctx.send(f"✅ Mute request submitted for approval (ID: {approval_id})")
                logger.info(f"Mute approval requested for user {user.id} in guild {ctx.guild.id}")
            else:
                # Apply mute immediately
                await member.add_roles(muted_role)
                mute_id = db.add_mute(user.id, ctx.guild.id, duration_seconds, situation, ctx.author.id, expires_at)
                
                # Log
                log_channel_id = guild_config.get("log_channel_id")
                if log_channel_id:
                    log_channel = ctx.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔇 User Muted",
                            description=f"{user.mention} has been muted",
                            color=EMBED_COLOR_RED
                        )
                        embed.add_field(name="Duration", value=duration, inline=False)
                        embed.add_field(name="Reason", value=situation, inline=False)
                        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                        embed.set_footer(text=f"User ID: {user.id}")
                        await log_channel.send(embed=embed)
                
                await ctx.send(f"✅ {user.mention} muted for {duration}")
                logger.info(f"User {user.id} muted in guild {ctx.guild.id} by {ctx.author.id}")
            
        except Exception as e:
            logger.error(f"Error in mute command: {e}", exc_info=True)
            await ctx.send("❌ Error muting user.")
    
    @commands.command(name="unmute")
    async def unmute(self, ctx, user: discord.User):
        """Unmute a user."""
        try:
            guild_config = db.get_guild_config(ctx.guild.id)
            if not guild_config:
                await ctx.send("❌ Server not configured.")
                return
            
            user_level = get_user_role_level(ctx.author, guild_config)
            if user_level < 1:
                await ctx.send("❌ You don't have permission to unmute users.")
                return
            
            # Get muted role
            muted_role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
            if not muted_role:
                await ctx.send("❌ Muted role not found.")
                return
            
            member = ctx.guild.get_member(user.id)
            if not member:
                await ctx.send("❌ User not found in this server.")
                return
            
            # Remove muted role
            await member.remove_roles(muted_role)
            
            # Update database
            db.unmute_user(user.id, ctx.guild.id)
            
            # Log
            log_channel_id = guild_config.get("log_channel_id")
            if log_channel_id:
                log_channel = ctx.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🔊 User Unmuted",
                        description=f"{user.mention} has been unmuted",
                        color=EMBED_COLOR_BLACK
                    )
                    embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                    embed.set_footer(text=f"User ID: {user.id}")
                    await log_channel.send(embed=embed)
            
            await ctx.send(f"✅ {user.mention} unmuted")
            logger.info(f"User {user.id} unmuted in guild {ctx.guild.id} by {ctx.author.id}")
            
        except Exception as e:
            logger.error(f"Error in unmute command: {e}", exc_info=True)
            await ctx.send("❌ Error unmuting user.")
    
    @commands.command(name="warnings")
    async def warnings(self, ctx, user: discord.User):
        """Get user's warnings."""
        try:
            warnings = db.get_warnings(user.id, ctx.guild.id)
            
            if not warnings:
                await ctx.send(f"{user.mention} has no warnings.")
                return
            
            embed = discord.Embed(
                title=f"Warnings for {user}",
                color=EMBED_COLOR_RED
            )
            
            for warning in warnings:
                embed.add_field(
                    name=f"Warning #{warning['number']}",
                    value=f"**Situation:** {warning['situation']}\n**Moderator:** <@{warning['mod_id']}>\n**Date:** {warning['timestamp']}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in warnings command: {e}", exc_info=True)
            await ctx.send("❌ Error retrieving warnings.")
    
    @commands.command(name="purge")
    @commands.is_owner()
    async def purge(self, ctx, number: int):
        """Delete messages (owner only)."""
        try:
            if number <= 0:
                await ctx.send("❌ Number must be greater than 0.")
                return
            
            deleted = await ctx.channel.purge(limit=number)
            await ctx.send(f"✅ Deleted {len(deleted)} messages.")
            logger.info(f"Purged {len(deleted)} messages in guild {ctx.guild.id} by {ctx.author.id}")
            
        except Exception as e:
            logger.error(f"Error in purge command: {e}", exc_info=True)
            await ctx.send("❌ Error purging messages.")
    
    @commands.command(name="setmodrole")
    @commands.has_permissions(administrator=True)
    async def set_mod_role(self, ctx, role: discord.Role):
        """Set the mod role."""
        try:
            db.set_guild_config(ctx.guild.id, mod_role_id=role.id)
            await ctx.send(f"✅ Mod role set to {role.mention}")
            logger.info(f"Mod role set to {role.id} in guild {ctx.guild.id}")
        except Exception as e:
            logger.error(f"Error in set_mod_role command: {e}", exc_info=True)
            await ctx.send("❌ Error setting mod role.")
    
    @commands.command(name="setadminrole")
    @commands.has_permissions(administrator=True)
    async def set_admin_role(self, ctx, role: discord.Role):
        """Set the admin role."""
        try:
            db.set_guild_config(ctx.guild.id, admin_role_id=role.id)
            await ctx.send(f"✅ Admin role set to {role.mention}")
            logger.info(f"Admin role set to {role.id} in guild {ctx.guild.id}")
        except Exception as e:
            logger.error(f"Error in set_admin_role command: {e}", exc_info=True)
            await ctx.send("❌ Error setting admin role.")

    @commands.command(name="modlogs")
    async def mod_logs(self, ctx, user: discord.User):
        """Show moderation history for a user."""
        try:
            logs = db.get_mod_logs(user.id, ctx.guild.id, limit=50)
            
            if not logs:
                await ctx.send(f"No moderation history for {user.mention}.")
                return
            
            embed = discord.Embed(
                title=f"Moderation History - {user}",
                description=f"Last 50 actions",
                color=EMBED_COLOR_BLACK
            )
            
            for log in logs:
                log_type = log["type"].upper()
                timestamp = log["timestamp"]
                reason = log["reason"]
                mod_id = log["mod_id"]
                
                embed.add_field(
                    name=f"{log_type} - {timestamp}",
                    value=f"Reason: {reason}\nMod: <@{mod_id}>",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            logger.info(f"Mod logs requested for {user.id} in guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"Error in mod_logs command: {e}", exc_info=True)
            await ctx.send("❌ Error retrieving moderation history.")
    
async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Moderation(bot))
