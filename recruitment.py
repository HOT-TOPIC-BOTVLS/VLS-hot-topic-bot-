"""Moderation recruitment system cog for Hot Helper bot."""

import discord
from discord.ext import commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED
import json

db = Database()

class RecruitmentModal(discord.ui.Modal, title="Mod Application"):
    """Modal for mod recruitment applications."""
    
    motivation = discord.ui.TextInput(
        label="Why do you want to be a moderator?",
        placeholder="Tell us about your motivation...",
        required=True,
        max_length=500
    )
    
    experience = discord.ui.TextInput(
        label="What moderation experience do you have?",
        placeholder="Describe your experience...",
        required=True,
        max_length=500
    )
    
    timezone = discord.ui.TextInput(
        label="What is your timezone?",
        placeholder="e.g., EST, PST, UTC...",
        required=True,
        max_length=50
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission."""
        try:
            guild_config = db.get_guild_config(interaction.guild.id)
            if not guild_config:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return
            
            # Save application
            answers = {
                "motivation": str(self.motivation),
                "experience": str(self.experience),
                "timezone": str(self.timezone)
            }
            
            app_channel_id = guild_config.get("app_channel_id")
            if not app_channel_id:
                await interaction.response.send_message("❌ Application channel not configured.", ephemeral=True)
                return
            
            app_channel = interaction.guild.get_channel(app_channel_id)
            if not app_channel:
                await interaction.response.send_message("❌ Application channel not found.", ephemeral=True)
                return
            
            # Post application to review channel
            embed = discord.Embed(
                title="📋 New Mod Application",
                description=f"From: {interaction.user.mention}",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Motivation", value=str(self.motivation), inline=False)
            embed.add_field(name="Experience", value=str(self.experience), inline=False)
            embed.add_field(name="Timezone", value=str(self.timezone), inline=False)
            embed.set_footer(text=f"User ID: {interaction.user.id}")
            
            view = RecruitmentReviewView(interaction.user.id, interaction.guild.id)
            await app_channel.send(embed=embed, view=view)
            
            await interaction.response.send_message("✅ Application submitted!", ephemeral=True)
            logger.info(f"Mod application submitted by {interaction.user.id} in guild {interaction.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in RecruitmentModal.on_submit: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error submitting application.", ephemeral=True)

class RecruitmentView(discord.ui.View):
    """View for recruitment button."""
    
    def __init__(self):
        super().__init__()
    
    @discord.ui.button(label="Apply", style=discord.ButtonStyle.green)
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show application modal."""
        await interaction.response.send_modal(RecruitmentModal())

class RecruitmentReviewView(discord.ui.View):
    """View for recruitment review buttons."""
    
    def __init__(self, applicant_id, guild_id):
        super().__init__()
        self.applicant_id = applicant_id
        self.guild_id = guild_id
    
    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Approve application."""
        try:
            guild_config = db.get_guild_config(self.guild_id)
            if not guild_config:
                await interaction.response.send_message("❌ Guild not configured.", ephemeral=True)
                return
            
            # Check if reviewer is owner
            if interaction.user.id != guild_config.get("owner_id"):
                await interaction.response.send_message("❌ Only the owner can approve applications.", ephemeral=True)
                return
            
            # Get applicant
            applicant = await interaction.client.fetch_user(self.applicant_id)
            
            # Assign mod role
            mod_role_id = guild_config.get("mod_role_id")
            if mod_role_id:
                guild = interaction.guild
                mod_role = guild.get_role(mod_role_id)
                if mod_role:
                    member = guild.get_member(self.applicant_id)
                    if member:
                        await member.add_roles(mod_role)
            
            # Send DM to applicant
            embed = discord.Embed(
                title="✅ Application Approved",
                description=f"Congratulations! You've been approved as a moderator in {interaction.guild.name}",
                color=EMBED_COLOR_BLACK
            )
            try:
                await applicant.send(embed=embed)
            except:
                pass
            
            # Update message
            embed = discord.Embed(
                title="✅ Application Approved",
                description=f"Approved by {interaction.user.mention}",
                color=EMBED_COLOR_BLACK
            )
            await interaction.response.edit_message(embed=embed, view=None)
            logger.info(f"Mod application approved for {self.applicant_id} in guild {self.guild_id}")
        
        except Exception as e:
            logger.error(f"Error in approve_button: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error approving application.", ephemeral=True)
    
    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deny application."""
        try:
            guild_config = db.get_guild_config(self.guild_id)
            if not guild_config:
                await interaction.response.send_message("❌ Guild not configured.", ephemeral=True)
                return
            
            # Check if reviewer is owner
            if interaction.user.id != guild_config.get("owner_id"):
                await interaction.response.send_message("❌ Only the owner can deny applications.", ephemeral=True)
                return
            
            # Get applicant
            applicant = await interaction.client.fetch_user(self.applicant_id)
            
            # Send DM to applicant
            embed = discord.Embed(
                title="❌ Application Denied",
                description=f"Unfortunately, your application for moderator in {interaction.guild.name} was not approved at this time.",
                color=EMBED_COLOR_RED
            )
            try:
                await applicant.send(embed=embed)
            except:
                pass
            
            # Update message
            embed = discord.Embed(
                title="❌ Application Denied",
                description=f"Denied by {interaction.user.mention}",
                color=EMBED_COLOR_RED
            )
            await interaction.response.edit_message(embed=embed, view=None)
            logger.info(f"Mod application denied for {self.applicant_id} in guild {self.guild_id}")
        
        except Exception as e:
            logger.error(f"Error in deny_button: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error denying application.", ephemeral=True)

class Recruitment(commands.Cog):
    """Moderation recruitment system."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="modrecruit")
    @commands.has_permissions(administrator=True)
    async def mod_recruit(self, ctx):
        """Post mod recruitment embed."""
        try:
            embed = discord.Embed(
                title="🎯 Moderator Recruitment",
                description="We're looking for dedicated moderators to help manage our community. Click the button below to apply!",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(
                name="Requirements",
                value="• Active in the community\n• Good communication skills\n• Ability to handle conflicts fairly",
                inline=False
            )
            
            view = RecruitmentView()
            await ctx.send(embed=embed, view=view)
            logger.info(f"Mod recruitment post created in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in mod_recruit command: {e}", exc_info=True)
            await ctx.send("❌ Error posting recruitment.")

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Recruitment(bot))
