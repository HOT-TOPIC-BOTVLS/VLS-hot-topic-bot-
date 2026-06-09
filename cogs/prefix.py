import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

class Prefix(commands.Cog):
    """Simple custom prefix and mod role management."""

    def __init__(self, bot):
        self.bot = bot
        self.default_prefix = "!"

    async def get_prefix(self, guild_id: int) -> str:
        """Get custom prefix for a guild (you can connect this to your Database later)."""
        # TODO: Later replace with Database call
        return getattr(self.bot, f"prefix_{guild_id}", self.default_prefix)

    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ Prefix cog loaded")

    # ===================== PREFIX COMMANDS =====================

    prefix_group = app_commands.Group(name="prefix", description="Manage server prefix")

    @prefix_group.command(name="set", description="Set a custom prefix for this server")
    @app_commands.describe(new_prefix="The new prefix (max 5 characters)")
    async def prefix_set(self, interaction: discord.Interaction, new_prefix: str):
        if len(new_prefix) > 5:
            return await interaction.response.send_message("❌ Prefix must be 5 characters or less.", ephemeral=True)

        # Simple in-memory for now (replace with DB later)
        setattr(self.bot, f"prefix_{interaction.guild_id}", new_prefix.strip())

        await interaction.response.send_message(
            f"✅ Prefix updated to: `{new_prefix}`\n"
            f"Example: `{new_prefix}help`",
            ephemeral=False
        )

    @prefix_group.command(name="current", description="Show the current prefix")
    async def prefix_current(self, interaction: discord.Interaction):
        prefix = await self.get_prefix(interaction.guild_id)
        await interaction.response.send_message(f"Current prefix is: `{prefix}`", ephemeral=True)

    @prefix_group.command(name="reset", description="Reset prefix back to default (!)")
    async def prefix_reset(self, interaction: discord.Interaction):
        if hasattr(self.bot, f"prefix_{interaction.guild_id}"):
            delattr(self.bot, f"prefix_{interaction.guild_id}")

        await interaction.response.send_message("✅ Prefix reset to default `!`", ephemeral=False)

    # ===================== MOD ROLE MANAGEMENT =====================

    mod_group = app_commands.Group(name="modrole", description="Manage who can use mod commands")

    @mod_group.command(name="set", description="Set the moderator role")
    @app_commands.describe(role="The role that should have mod permissions")
    async def modrole_set(self, interaction: discord.Interaction, role: discord.Role):
        # TODO: Save to your Database later
        setattr(self.bot, f"mod_role_{interaction.guild_id}", role.id)

        await interaction.response.send_message(
            f"✅ Moderator role set to **{role.name}**\n"
            "Users with this role can now use mod commands.",
            ephemeral=False
        )

    @mod_group.command(name="remove", description="Remove the moderator role")
    async def modrole_remove(self, interaction: discord.Interaction):
        key = f"mod_role_{interaction.guild_id}"
        if hasattr(self.bot, key):
            delattr(self.bot, key)
            await interaction.response.send_message("✅ Moderator role removed.", ephemeral=False)
        else:
            await interaction.response.send_message("❌ No moderator role was set.", ephemeral=True)

    # Helper check you can use in other cogs
    def is_mod(self, member: discord.Member) -> bool:
        """Check if user has mod permissions."""
        if member.guild_permissions.administrator:
            return True
        mod_role_id = getattr(self.bot, f"mod_role_{member.guild.id}", None)
        if mod_role_id:
            return any(role.id == mod_role_id for role in member.roles)
        return False


async def setup(bot):
    await bot.add_cog(Prefix(bot))