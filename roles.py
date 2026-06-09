"""Custom role management cog for Hot Helper bot."""

import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()


class RoleGroup(app_commands.Group, name="role", description="Manage custom roles"):
    """Slash command group for role management."""

    @app_commands.command(name="create", description="Create a new custom role")
    @app_commands.describe(
        name="Role name",
        color="Role color as hex (e.g. #00FF00)",
        hoist="Show role separately in member list",
        mentionable="Allow anyone to mention this role",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        color: str = None,
        hoist: bool = False,
        mentionable: bool = False,
    ):
        """Create a new custom role."""
        try:
            role_color = discord.Color.default()
            if color:
                try:
                    role_color = discord.Color(int(color.replace("#", ""), 16))
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Invalid color format. Use hex like `#00FF00`.", ephemeral=True
                    )
                    return

            new_role = await interaction.guild.create_role(
                name=name,
                color=role_color,
                hoist=hoist,
                mentionable=mentionable,
            )

            db.add_custom_role(interaction.guild.id, new_role.id, name, interaction.user.id)

            await interaction.response.send_message(
                f"✅ Role {new_role.mention} created.", ephemeral=True
            )
            logger.info(f"Role {new_role.id} created in guild {interaction.guild.id}")

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create roles.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in role create: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error creating role.", ephemeral=True)

    @app_commands.command(name="delete", description="Delete a custom role")
    @app_commands.describe(role="The role to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, role: discord.Role):
        """Delete a custom role."""
        try:
            role_name = role.name
            await role.delete(reason=f"Deleted by {interaction.user}")
            await interaction.response.send_message(
                f"✅ Role **{role_name}** deleted.", ephemeral=True
            )
            logger.info(f"Role {role.id} deleted in guild {interaction.guild.id}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to delete that role.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in role delete: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error deleting role.", ephemeral=True)

    @app_commands.command(name="assign", description="Give a role to a user")
    @app_commands.describe(role="The role to assign", user="The user to assign it to")
    @app_commands.checks.has_permissions(administrator=True)
    async def assign(
        self, interaction: discord.Interaction, role: discord.Role, user: discord.Member
    ):
        """Assign a role to a user."""
        try:
            await user.add_roles(role, reason=f"Assigned by {interaction.user}")
            await interaction.response.send_message(
                f"✅ {user.mention} assigned to {role.mention}.", ephemeral=True
            )
            logger.info(f"User {user.id} assigned role {role.id} in guild {interaction.guild.id}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to assign that role.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in role assign: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error assigning role.", ephemeral=True)

    @app_commands.command(name="remove", description="Remove a role from a user")
    @app_commands.describe(role="The role to remove", user="The user to remove it from")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(
        self, interaction: discord.Interaction, role: discord.Role, user: discord.Member
    ):
        """Remove a role from a user."""
        try:
            await user.remove_roles(role, reason=f"Removed by {interaction.user}")
            await interaction.response.send_message(
                f"✅ Removed {role.mention} from {user.mention}.", ephemeral=True
            )
            logger.info(f"Role {role.id} removed from user {user.id} in guild {interaction.guild.id}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to remove that role.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in role remove: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error removing role.", ephemeral=True)

    @app_commands.command(name="selfassign", description="Give yourself a self-assignable role")
    @app_commands.describe(role="The role to assign or remove from yourself")
    async def selfassign(self, interaction: discord.Interaction, role: discord.Role):
        """Self-assign or remove a self-assignable role."""
        try:
            custom_roles = db.get_custom_roles(interaction.guild.id)
            role_data = next((r for r in custom_roles if r["role_id"] == role.id), None)

            if not role_data or not role_data["is_self_assignable"]:
                await interaction.response.send_message(
                    "❌ That role is not self-assignable.", ephemeral=True
                )
                return

            member = interaction.guild.get_member(interaction.user.id)
            if role in member.roles:
                await member.remove_roles(role)
                await interaction.response.send_message(
                    f"✅ Removed {role.mention} from you.", ephemeral=True
                )
            else:
                await member.add_roles(role)
                await interaction.response.send_message(
                    f"✅ Gave you {role.mention}.", ephemeral=True
                )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to modify your roles.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in role selfassign: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error assigning role.", ephemeral=True)

    @app_commands.command(name="toggle-selfassign", description="Toggle whether users can self-assign a role")
    @app_commands.describe(role="The role to toggle")
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle_selfassign(self, interaction: discord.Interaction, role: discord.Role):
        """Toggle self-assign on a role."""
        try:
            db.toggle_self_assign(role.id, interaction.guild.id)
            await interaction.response.send_message(
                f"✅ Self-assign toggled for {role.mention}.", ephemeral=True
            )
            logger.info(f"Self-assign toggled for role {role.id} in guild {interaction.guild.id}")
        except Exception as e:
            logger.error(f"Error in toggle-selfassign: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error toggling self-assign.", ephemeral=True)

    @app_commands.command(name="list", description="List all custom roles and their self-assign status")
    async def list_roles(self, interaction: discord.Interaction):
        """List all custom roles."""
        try:
            custom_roles = db.get_custom_roles(interaction.guild.id)

            if not custom_roles:
                await interaction.response.send_message(
                    "No custom roles set up yet. Use `/role create` or `/role createdefaults`.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(title="Custom Roles", color=EMBED_COLOR_BLACK)

            for role_data in custom_roles:
                role = interaction.guild.get_role(role_data["role_id"])
                if role:
                    status = "✅ Self-assignable" if role_data["is_self_assignable"] else "❌ Not self-assignable"
                    embed.add_field(name=role.name, value=status, inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in role list: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error listing roles.", ephemeral=True)

    @app_commands.command(name="createdefaults", description="Create default starter roles: Gamer, Artist, Music Fan, Content Creator")
    @app_commands.checks.has_permissions(administrator=True)
    async def createdefaults(self, interaction: discord.Interaction):
        """Create default self-assignable roles."""
        try:
            await interaction.response.defer(ephemeral=True)

            default_roles = [
                {"name": "Gamer", "color": 0x00FF00},
                {"name": "Artist", "color": 0xFF00FF},
                {"name": "Music Fan", "color": 0x00FFFF},
                {"name": "Content Creator", "color": 0xFFFF00},
            ]

            created = []
            for role_config in default_roles:
                # Skip if role already exists
                existing = discord.utils.get(interaction.guild.roles, name=role_config["name"])
                if existing:
                    created.append(f"⚠️ {existing.mention} (already existed)")
                    continue

                new_role = await interaction.guild.create_role(
                    name=role_config["name"],
                    color=discord.Color(role_config["color"]),
                    mentionable=True,
                )
                db.add_custom_role(
                    interaction.guild.id, new_role.id, role_config["name"], interaction.user.id
                )
                db.toggle_self_assign(new_role.id, interaction.guild.id)
                created.append(f"✅ {new_role.mention}")

            await interaction.followup.send(
                "**Default roles created (all self-assignable):**\n" + "\n".join(created),
                ephemeral=True,
            )
            logger.info(f"Default roles created in guild {interaction.guild.id}")

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to create roles.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in createdefaults: {e}", exc_info=True)
            await interaction.followup.send("❌ Error creating default roles.", ephemeral=True)


class Roles(commands.Cog):
    """Custom role management cog."""

    def __init__(self, bot):
        self.bot = bot
        # Register the slash command group
        bot.tree.add_command(RoleGroup())

    async def cog_unload(self):
        self.bot.tree.remove_command("role")


async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Roles(bot))
