"""Custom role management cog for Hot Helper bot."""

import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()

class Roles(commands.Cog):
    """Custom role management commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="role", description="Manage custom roles")
    @app_commands.describe(
        action="Action to perform (create, delete, assign, remove, selfassign, toggle-selfassign, list, createdefaults)",
        name="Role name (for create)",
        color="Role color hex (for create)",
        hoist="Hoist role (for create)",
        mentionable="Make role mentionable (for create)",
        role="Target role",
        user="Target user"
    )
    async def role_command(self, interaction: discord.Interaction, action: str, name: str = None, color: str = None, hoist: bool = False, mentionable: bool = False, role: discord.Role = None, user: discord.User = None):
        """Manage custom roles."""
        try:
            if action == "create":
                if not name:
                    await interaction.response.send_message("❌ Role name required.", ephemeral=True)
                    return
                
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
                    return
                
                # Parse color
                role_color = discord.Color.default()
                if color:
                    try:
                        role_color = discord.Color(int(color.replace("#", ""), 16))
                    except:
                        pass
                
                # Create role
                new_role = await interaction.guild.create_role(
                    name=name,
                    color=role_color,
                    hoist=hoist,
                    mentionable=mentionable
                )
                
                # Save to database
                db.add_custom_role(interaction.guild.id, new_role.id, name, interaction.user.id)
                
                await interaction.response.send_message(f"✅ Role {new_role.mention} created.", ephemeral=True)
                logger.info(f"Role {new_role.id} created in guild {interaction.guild.id}")
            
            elif action == "delete":
                if not role:
                    await interaction.response.send_message("❌ Role required.", ephemeral=True)
                    return
                
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
                    return
                
                await role.delete()
                await interaction.response.send_message(f"✅ Role deleted.", ephemeral=True)
                logger.info(f"Role {role.id} deleted in guild {interaction.guild.id}")
            
            elif action == "assign":
                if not role or not user:
                    await interaction.response.send_message("❌ Role and user required.", ephemeral=True)
                    return
                
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
                    return
                
                member = interaction.guild.get_member(user.id)
                if not member:
                    await interaction.response.send_message("❌ User not in this server.", ephemeral=True)
                    return
                
                await member.add_roles(role)
                await interaction.response.send_message(f"✅ {user.mention} assigned to {role.mention}.", ephemeral=True)
                logger.info(f"User {user.id} assigned to role {role.id} in guild {interaction.guild.id}")
            
            elif action == "remove":
                if not role or not user:
                    await interaction.response.send_message("❌ Role and user required.", ephemeral=True)
                    return
                
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
                    return
                
                member = interaction.guild.get_member(user.id)
                if not member:
                    await interaction.response.send_message("❌ User not in this server.", ephemeral=True)
                    return
                
                await member.remove_roles(role)
                await interaction.response.send_message(f"✅ {user.mention} removed from {role.mention}.", ephemeral=True)
                logger.info(f"User {user.id} removed from role {role.id} in guild {interaction.guild.id}")
            
            elif action == "selfassign":
                if not role:
                    await interaction.response.send_message("❌ Role required.", ephemeral=True)
                    return
                
                # Check if role is self-assignable
                custom_roles = db.get_custom_roles(interaction.guild.id)
                role_data = next((r for r in custom_roles if r["role_id"] == role.id), None)
                
                if not role_data or not role_data["is_self_assignable"]:
                    await interaction.response.send_message("❌ This role is not self-assignable.", ephemeral=True)
                    return
                
                member = interaction.guild.get_member(interaction.user.id)
                if role in member.roles:
                    await member.remove_roles(role)
                    await interaction.response.send_message(f"✅ Removed from {role.mention}.", ephemeral=True)
                else:
                    await member.add_roles(role)
                    await interaction.response.send_message(f"✅ Added to {role.mention}.", ephemeral=True)
            
            elif action == "toggle-selfassign":
                if not role:
                    await interaction.response.send_message("❌ Role required.", ephemeral=True)
                    return
                
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
                    return
                
                db.toggle_self_assign(role.id, interaction.guild.id)
                await interaction.response.send_message(f"✅ Self-assign toggled for {role.mention}.", ephemeral=True)
                logger.info(f"Self-assign toggled for role {role.id} in guild {interaction.guild.id}")
            
            elif action == "list":
                custom_roles = db.get_custom_roles(interaction.guild.id)
                
                if not custom_roles:
                    await interaction.response.send_message("No custom roles.", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="Custom Roles",
                    color=EMBED_COLOR_BLACK
                )
                
                for role_data in custom_roles:
                    role = interaction.guild.get_role(role_data["role_id"])
                    if role:
                        status = "✅ Self-assignable" if role_data["is_self_assignable"] else "❌ Not self-assignable"
                        embed.add_field(name=role.mention, value=status, inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
            elif action == "createdefaults":
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
                    return
                
                default_roles = [
                    {"name": "Gamer", "color": 0x00FF00},
                    {"name": "Artist", "color": 0xFF00FF},
                    {"name": "Music Fan", "color": 0x00FFFF},
                    {"name": "Content Creator", "color": 0xFFFF00},
                ]
                
                for role_config in default_roles:
                    new_role = await interaction.guild.create_role(
                        name=role_config["name"],
                        color=discord.Color(role_config["color"]),
                        mentionable=True
                    )
                    db.add_custom_role(interaction.guild.id, new_role.id, role_config["name"], interaction.user.id)
                    db.toggle_self_assign(new_role.id, interaction.guild.id)
                
                await interaction.response.send_message("✅ Default roles created and set to self-assignable.", ephemeral=True)
                logger.info(f"Default roles created in guild {interaction.guild.id}")
            
            else:
                await interaction.response.send_message("❌ Invalid action.", ephemeral=True)
        
        except Exception as e:
            logger.error(f"Error in role_command: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error managing role.", ephemeral=True)

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Roles(bot))
