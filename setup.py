"""Setup wizard and configuration cog for Hot Helper bot."""

import discord
from discord.ext import commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()

class SetupWizardView(discord.ui.View):
    """View for setup wizard navigation."""
    
    def __init__(self, ctx, step=1):
        super().__init__()
        self.ctx = ctx
        self.step = step
        self.config = {}
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next step."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ You can't use this button.", ephemeral=True)
            return
        
        self.step += 1
        if self.step > 5:
            await interaction.response.send_message("✅ Setup complete!", ephemeral=True)
            self.stop()
        else:
            await interaction.response.defer()

class Setup(commands.Cog):
    """Setup and configuration commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="setupwizard")
    @commands.has_permissions(administrator=True)
    async def setup_wizard(self, ctx):
        """Interactive setup wizard."""
        try:
            embed = discord.Embed(
                title="🔧 Setup Wizard",
                description="Let's configure Hot Helper for your server!",
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Step 1/5", value="Set log channel", inline=False)
            embed.add_field(name="Instructions", value="Reply with the log channel ID or mention the channel.", inline=False)
            
            await ctx.send(embed=embed)
            
            # Step 1: Log channel
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                log_channel = None
                
                # Try to parse channel mention or ID
                if msg.channel_mentions:
                    log_channel = msg.channel_mentions[0]
                else:
                    try:
                        log_channel = ctx.guild.get_channel(int(msg.content))
                    except:
                        pass
                
                if not log_channel:
                    await ctx.send("❌ Invalid channel.")
                    return
                
                db.set_guild_config(ctx.guild.id, log_channel_id=log_channel.id)
                await ctx.send(f"✅ Log channel set to {log_channel.mention}")
                
                # Step 2: Announcement channel
                embed = discord.Embed(
                    title="🔧 Setup Wizard",
                    description="Step 2/5: Set announcement channel",
                    color=EMBED_COLOR_BLACK
                )
                await ctx.send(embed=embed)
                
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                announce_channel = None
                
                if msg.channel_mentions:
                    announce_channel = msg.channel_mentions[0]
                else:
                    try:
                        announce_channel = ctx.guild.get_channel(int(msg.content))
                    except:
                        pass
                
                if not announce_channel:
                    await ctx.send("❌ Invalid channel.")
                    return
                
                db.set_guild_config(ctx.guild.id, announce_channel_id=announce_channel.id)
                await ctx.send(f"✅ Announcement channel set to {announce_channel.mention}")
                
                # Step 3: Mod role
                embed = discord.Embed(
                    title="🔧 Setup Wizard",
                    description="Step 3/5: Set mod role",
                    color=EMBED_COLOR_BLACK
                )
                await ctx.send(embed=embed)
                
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                mod_role = None
                
                if msg.role_mentions:
                    mod_role = msg.role_mentions[0]
                else:
                    try:
                        mod_role = ctx.guild.get_role(int(msg.content))
                    except:
                        pass
                
                if not mod_role:
                    await ctx.send("❌ Invalid role.")
                    return
                
                db.set_guild_config(ctx.guild.id, mod_role_id=mod_role.id)
                await ctx.send(f"✅ Mod role set to {mod_role.mention}")
                
                # Step 4: Admin role
                embed = discord.Embed(
                    title="🔧 Setup Wizard",
                    description="Step 4/5: Set admin role",
                    color=EMBED_COLOR_BLACK
                )
                await ctx.send(embed=embed)
                
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                admin_role = None
                
                if msg.role_mentions:
                    admin_role = msg.role_mentions[0]
                else:
                    try:
                        admin_role = ctx.guild.get_role(int(msg.content))
                    except:
                        pass
                
                if not admin_role:
                    await ctx.send("❌ Invalid role.")
                    return
                
                db.set_guild_config(ctx.guild.id, admin_role_id=admin_role.id)
                await ctx.send(f"✅ Admin role set to {admin_role.mention}")
                
                # Step 5: Application channel
                embed = discord.Embed(
                    title="🔧 Setup Wizard",
                    description="Step 5/5: Set application review channel",
                    color=EMBED_COLOR_BLACK
                )
                await ctx.send(embed=embed)
                
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                app_channel = None
                
                if msg.channel_mentions:
                    app_channel = msg.channel_mentions[0]
                else:
                    try:
                        app_channel = ctx.guild.get_channel(int(msg.content))
                    except:
                        pass
                
                if not app_channel:
                    await ctx.send("❌ Invalid channel.")
                    return
                
                db.set_guild_config(ctx.guild.id, app_channel_id=app_channel.id)
                await ctx.send(f"✅ Application channel set to {app_channel.mention}")
                
                # Complete
                embed = discord.Embed(
                    title="✅ Setup Complete",
                    description="Hot Helper is now configured for your server!",
                    color=EMBED_COLOR_BLACK
                )
                embed.add_field(name="Next Steps", value="1. Use `!setupcheck` to verify configuration\n2. Use `!setupverify` to post verification\n3. Use `!modrecruit` to post mod recruitment", inline=False)
                await ctx.send(embed=embed)
                
                logger.info(f"Setup wizard completed for guild {ctx.guild.id}")
            
            except asyncio.TimeoutError:
                await ctx.send("❌ Setup wizard timed out.")
        
        except Exception as e:
            logger.error(f"Error in setup_wizard command: {e}", exc_info=True)
            await ctx.send("❌ Error running setup wizard.")
    
    @commands.command(name="setupcheck")
    @commands.has_permissions(administrator=True)
    async def setup_check(self, ctx):
        """Check bot configuration and permissions."""
        try:
            embed = discord.Embed(
                title="🔍 Setup Check",
                description="Verifying Hot Helper configuration...",
                color=EMBED_COLOR_BLACK
            )
            
            # Check config
            config = db.get_guild_config(ctx.guild.id)
            if not config:
                embed.add_field(name="❌ Configuration", value="Not configured. Run `!setupwizard`", inline=False)
            else:
                embed.add_field(name="✅ Configuration", value="Configured", inline=False)
                
                # Check channels
                log_channel = ctx.guild.get_channel(config.get("log_channel_id"))
                embed.add_field(name="Log Channel", value=f"{'✅' if log_channel else '❌'} {log_channel.mention if log_channel else 'Not found'}", inline=False)
                
                announce_channel = ctx.guild.get_channel(config.get("announce_channel_id"))
                embed.add_field(name="Announcement Channel", value=f"{'✅' if announce_channel else '❌'} {announce_channel.mention if announce_channel else 'Not found'}", inline=False)
                
                app_channel = ctx.guild.get_channel(config.get("app_channel_id"))
                embed.add_field(name="Application Channel", value=f"{'✅' if app_channel else '❌'} {app_channel.mention if app_channel else 'Not found'}", inline=False)
                
                # Check roles
                mod_role = ctx.guild.get_role(config.get("mod_role_id"))
                embed.add_field(name="Mod Role", value=f"{'✅' if mod_role else '❌'} {mod_role.mention if mod_role else 'Not found'}", inline=False)
                
                admin_role = ctx.guild.get_role(config.get("admin_role_id"))
                embed.add_field(name="Admin Role", value=f"{'✅' if admin_role else '❌'} {admin_role.mention if admin_role else 'Not found'}", inline=False)
            
            # Check bot permissions
            bot_perms = ctx.guild.me.guild_permissions
            embed.add_field(name="Bot Permissions", value=f"{'✅' if bot_perms.administrator else '❌'} Administrator: {bot_perms.administrator}", inline=False)
            
            # Check database
            embed.add_field(name="Database", value="✅ Connected", inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f"Setup check performed in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in setup_check command: {e}", exc_info=True)
            await ctx.send("❌ Error checking setup.")
    
    @commands.command(name="transferownership")
    @commands.is_owner()
    async def transfer_ownership(self, ctx, user: discord.User):
        """Transfer bot ownership (owner only)."""
        try:
            # Confirmation
            embed = discord.Embed(
                title="⚠️ Transfer Ownership",
                description=f"Are you sure you want to transfer ownership to {user.mention}?",
                color=EMBED_COLOR_RED
            )
            
            msg = await ctx.send(embed=embed)
            
            def check(reaction, user_check):
                return user_check == ctx.author and str(reaction.emoji) in ["✅", "❌"]
            
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            
            try:
                reaction, user_check = await self.bot.wait_for("reaction_add", check=check, timeout=30)
                
                if str(reaction.emoji) == "✅":
                    db.set_guild_config(ctx.guild.id, owner_id=user.id)
                    await ctx.send(f"✅ Ownership transferred to {user.mention}")
                    logger.info(f"Ownership transferred to {user.id} in guild {ctx.guild.id}")
                else:
                    await ctx.send("❌ Transfer cancelled.")
            
            except asyncio.TimeoutError:
                await ctx.send("❌ Transfer timed out.")
        
        except Exception as e:
            logger.error(f"Error in transfer_ownership command: {e}", exc_info=True)
            await ctx.send("❌ Error transferring ownership.")

import asyncio

    @commands.command(name="setupcheck")
    @commands.has_permissions(administrator=True)
    async def setup_check(self, ctx):
        """Verify bot configuration and permissions."""
        try:
            import subprocess
            
            embed = discord.Embed(title="🔧 Setup Check", color=EMBED_COLOR_BLACK)
            
            # Check database connectivity
            try:
                config = db.get_guild_config(ctx.guild.id)
                db_ok = True
                embed.add_field(name="Database", value="✅ Connected", inline=False)
            except:
                db_ok = False
                embed.add_field(name="Database", value="❌ Connection failed", inline=False)
            
            # Check FFmpeg
            try:
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
                ffmpeg_ok = result.returncode == 0
                embed.add_field(name="FFmpeg", value="✅ Installed" if ffmpeg_ok else "❌ Not found", inline=False)
            except:
                embed.add_field(name="FFmpeg", value="❌ Not found", inline=False)
            
            # Check bot permissions
            perms = ctx.guild.me.guild_permissions
            perms_ok = all([
                perms.send_messages,
                perms.embed_links,
                perms.manage_roles,
                perms.ban_members,
                perms.kick_members,
                perms.manage_channels
            ])
            
            perms_text = "✅ All required" if perms_ok else "❌ Missing permissions"
            embed.add_field(name="Bot Permissions", value=perms_text, inline=False)
            
            # Check guild config
            if config:
                config_ok = all([
                    config.get("log_channel_id"),
                    config.get("announce_channel_id"),
                    config.get("mod_role_id"),
                    config.get("admin_role_id")
                ])
                embed.add_field(name="Guild Config", value="✅ Complete" if config_ok else "⚠️ Incomplete", inline=False)
            else:
                embed.add_field(name="Guild Config", value="❌ Not configured", inline=False)
            
            # Check channels exist
            if config:
                channels_ok = True
                if config.get("log_channel_id") and not ctx.guild.get_channel(config["log_channel_id"]):
                    channels_ok = False
                if config.get("announce_channel_id") and not ctx.guild.get_channel(config["announce_channel_id"]):
                    channels_ok = False
                
                embed.add_field(name="Channels", value="✅ All exist" if channels_ok else "❌ Some missing", inline=False)
            
            # Check roles exist
            if config:
                roles_ok = True
                if config.get("mod_role_id") and not ctx.guild.get_role(config["mod_role_id"]):
                    roles_ok = False
                if config.get("admin_role_id") and not ctx.guild.get_role(config["admin_role_id"]):
                    roles_ok = False
                
                embed.add_field(name="Roles", value="✅ All exist" if roles_ok else "❌ Some missing", inline=False)
            
            await ctx.send(embed=embed)
            logger.info(f"Setup check performed in guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"Error in setup_check command: {e}", exc_info=True)
            await ctx.send("❌ Error running setup check.")
    
async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Setup(bot))
