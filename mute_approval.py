"""Mute approval system cog for Hot Helper bot."""

import discord
from discord.ext import commands
from datetime import datetime, timedelta
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED, MUTE_ROLE_NAME

db = Database()

class MuteApprovalView(discord.ui.View):
    """View for mute approval buttons."""
    
    def __init__(self, approval_id, user_id, guild_id, duration, reason, mod_id):
        super().__init__()
        self.approval_id = approval_id
        self.user_id = user_id
        self.guild_id = guild_id
        self.duration = duration
        self.reason = reason
        self.mod_id = mod_id
    
    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Approve the mute."""
        try:
            guild = interaction.guild
            
            # Get guild config
            guild_config = db.get_guild_config(guild.id)
            if not guild_config:
                await interaction.response.send_message("❌ Guild not configured.", ephemeral=True)
                return
            
            # Check if user is admin or owner
            if interaction.user.id != guild_config.get("owner_id"):
                admin_role_id = guild_config.get("admin_role_id")
                if not admin_role_id or not interaction.user.get_role(admin_role_id):
                    await interaction.response.send_message("❌ You don't have permission to approve mutes.", ephemeral=True)
                    return
            
            # Approve in database
            db.approve_mute(self.approval_id, interaction.user.id)
            
            # Get user and apply mute
            user = await guild.fetch_user(self.user_id)
            member = guild.get_member(self.user_id)
            
            if member:
                # Get or create muted role
                muted_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
                if not muted_role:
                    muted_role = await guild.create_role(name=MUTE_ROLE_NAME, color=discord.Color.dark_gray())
                    for channel in guild.channels:
                        await channel.set_permissions(muted_role, send_messages=False, speak=False)
                
                await member.add_roles(muted_role)
                
                # Calculate expiry
                expires_at = None
                if self.duration:
                    expires_at = datetime.utcnow() + timedelta(seconds=self.duration)
                
                # Add to mutes
                db.add_mute(self.user_id, guild.id, self.duration, self.reason, self.mod_id, expires_at)
                
                # Log
                log_channel_id = guild_config.get("log_channel_id")
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔇 User Muted (Approved)",
                            description=f"{user.mention} has been muted",
                            color=EMBED_COLOR_RED
                        )
                        embed.add_field(name="Duration", value=f"{self.duration}s" if self.duration else "Permanent", inline=False)
                        embed.add_field(name="Reason", value=self.reason, inline=False)
                        embed.add_field(name="Approved By", value=interaction.user.mention, inline=False)
                        embed.set_footer(text=f"User ID: {self.user_id}")
                        await log_channel.send(embed=embed)
            
            # Update message
            embed = discord.Embed(
                title="✅ Mute Approved",
                description=f"Mute for {user.mention} has been approved.",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Approved By", value=interaction.user.mention, inline=False)
            
            await interaction.response.edit_message(embed=embed, view=None)
            logger.info(f"Mute approved for user {self.user_id} in guild {guild.id}")
            
        except Exception as e:
            logger.error(f"Error in approve_button: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error approving mute.", ephemeral=True)
    
    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deny the mute."""
        try:
            guild = interaction.guild
            
            # Get guild config
            guild_config = db.get_guild_config(guild.id)
            if not guild_config:
                await interaction.response.send_message("❌ Guild not configured.", ephemeral=True)
                return
            
            # Check if user is admin or owner
            if interaction.user.id != guild_config.get("owner_id"):
                admin_role_id = guild_config.get("admin_role_id")
                if not admin_role_id or not interaction.user.get_role(admin_role_id):
                    await interaction.response.send_message("❌ You don't have permission to deny mutes.", ephemeral=True)
                    return
            
            # Deny in database
            db.deny_mute(self.approval_id, interaction.user.id)
            
            # Get user
            user = await guild.fetch_user(self.user_id)
            
            # Update message
            embed = discord.Embed(
                title="❌ Mute Denied",
                description=f"Mute for {user.mention} has been denied.",
                color=EMBED_COLOR_RED
            )
            embed.add_field(name="Denied By", value=interaction.user.mention, inline=False)
            
            await interaction.response.edit_message(embed=embed, view=None)
            logger.info(f"Mute denied for user {self.user_id} in guild {guild.id}")
            
        except Exception as e:
            logger.error(f"Error in deny_button: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error denying mute.", ephemeral=True)

class MuteApproval(commands.Cog):
    """Mute approval system."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="pendingmutes")
    async def pending_mutes(self, ctx):
        """Show pending mute approvals."""
        try:
            pending = db.get_pending_approvals(ctx.guild.id)
            
            if not pending:
                await ctx.send("No pending mute approvals.")
                return
            
            for approval in pending:
                user = await ctx.bot.fetch_user(approval["user_id"])
                mod = await ctx.bot.fetch_user(approval["mod_id"])
                
                embed = discord.Embed(
                    title="⏳ Pending Mute Approval",
                    description=f"User: {user.mention}\nModerator: {mod.mention}",
                    color=EMBED_COLOR_BLACK
                )
                embed.add_field(name="Duration", value=f"{approval['duration']}s" if approval['duration'] else "Permanent", inline=False)
                embed.add_field(name="Reason", value=approval['reason'], inline=False)
                embed.add_field(name="Requested", value=approval['issued_at'], inline=False)
                
                view = MuteApprovalView(
                    approval["id"],
                    approval["user_id"],
                    ctx.guild.id,
                    approval["duration"],
                    approval["reason"],
                    approval["mod_id"]
                )
                
                await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error in pending_mutes command: {e}", exc_info=True)
            await ctx.send("❌ Error retrieving pending mutes.")

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(MuteApproval(bot))
