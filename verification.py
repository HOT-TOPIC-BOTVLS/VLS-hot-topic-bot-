"""Verification system cog for Hot Helper bot."""

import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()

class VerificationView(discord.ui.View):
    """View for verification button."""
    
    def __init__(self):
        super().__init__(timeout=none)
    
    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.green)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle verification button click."""
        try:
            guild = interaction.guild
            user = interaction.user
            
            # Check if already verified
            if db.is_verified(user.id, guild.id):
                await interaction.response.send_message(
                    "You're already verified!",
                    ephemeral=True
                )
                return
            
            # Look for a "Verified" role first, create it if missing
            verified_role = discord.utils.get(guild.roles, name="Verified")
            if not verified_role:
                try:
                    verified_role = await guild.create_role(
                        name="Verified",
                        color=discord.Color.green(),
                        reason="Hot Helper verification system"
                    )
                    logger.info(f"Created Verified role in guild {guild.id}")
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "Bot lacks permissions to create role. Contact an admin.",
                        ephemeral=True
                    )
                    logger.error(f"Cannot create Verified role in guild {guild.id}: Permission denied")
                    return
            
            # Assign role
            try:
                await user.add_roles(verified_role)
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Bot lacks permissions to assign role. Contact an admin.",
                    ephemeral=True
                )
                logger.error(f"Cannot assign Verified role to user {user.id} in guild {guild.id}")
                return
            
            # Log to database
            db.add_verification(user.id, guild.id)
            
            # Send confirmation
            await interaction.response.send_message(
                "✅ You've been verified!",
                ephemeral=True
            )
            
            # Send welcome DM
            try:
                embed = discord.Embed(
                    title=f"Welcome to {guild.name}!",
                    description="You've been verified and can now access the server.",
                    color=EMBED_COLOR_BLACK
                )
                embed.add_field(
                    name="Need help?",
                    value="Check the rules channel or ask a moderator.",
                    inline=False
                )
                await user.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user.id} after verification")
            
            logger.info(f"User {user.id} verified in guild {guild.id}")
            
        except Exception as e:
            logger.error(f"Error in verify_button: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred during verification.",
                ephemeral=True
            )

class Verification(commands.Cog):
    """Verification system commands."""
    
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerificationView())
    
    @commands.command(name="setupverify")
    @commands.has_permissions(administrator=True)
    async def setup_verify(self, ctx):
        """Post verification embed with button."""
        try:
            embed = discord.Embed(
                title="Verification Required",
                description="Click the button below to verify and gain access to the server.",
                color=EMBED_COLOR_BLACK
            )
            embed.set_footer(text="Hot Helper Verification System")
            
            view = VerificationView()
            await ctx.send(embed=embed, view=view)
            
            logger.info(f"Verification embed posted in guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"Error in setup_verify: {e}", exc_info=True)
            await ctx.send("❌ Error setting up verification.")
    
    @app_commands.command(name="setupverify", description="Post verification embed with button")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_setup_verify(self, interaction: discord.Interaction):
        """Slash command for setup verify."""
        try:
            embed = discord.Embed(
                title="Verification Required",
                description="Click the button below to verify and gain access to the server.",
                color=EMBED_COLOR_BLACK
            )
            embed.set_footer(text="Hot Helper Verification System")
            
            view = VerificationView()
            await interaction.response.send_message(embed=embed, view=view)
            
            logger.info(f"Verification embed posted in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error in slash_setup_verify: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error setting up verification.", ephemeral=True)

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Verification(bot))
