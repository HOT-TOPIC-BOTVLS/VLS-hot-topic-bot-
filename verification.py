"""Verification system cog for Hot Helper bot."""

import random
import asyncio

import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()

# ─────────────────────────────────────────────────────────────────
# Self-role config — edit role list/emojis here
# ─────────────────────────────────────────────────────────────────

VERIFIED_ROLE_NAME = "Verified"

# (emoji, role_name, color) - auto-created by /setup_roles, shown in self-role DM menu
SELF_ROLES = [
    # Music / aesthetic identity
    ("🖤", "Emo", discord.Color.dark_gray()),
    ("🦇", "Goth", discord.Color.dark_purple()),
    ("🤘", "Punk", discord.Color.red()),
    ("🌈", "Scene", discord.Color.magenta()),
    ("⛓️", "Metalhead", discord.Color.darker_grey()),
    ("💀", "Alt", discord.Color.dark_teal()),

    # Gaming platform
    ("🎮", "Console", discord.Color.blue()),
    ("🖥️", "PC", discord.Color.green()),
    ("📱", "Mobile", discord.Color.gold()),

    # Pronouns
    ("👨", "He/Him", discord.Color.blue()),
    ("👩", "She/Her", discord.Color.pink()),
    ("🌀", "They/Them", discord.Color.purple()),
    ("❓", "Ask Me", discord.Color.light_grey()),
]

VERIFY_TIMEOUT_SECONDS = 120


def generate_algebra_question():
    """y = mx + b. Returns (question_text, correct_answer)."""
    m = random.randint(2, 9)
    b = random.randint(1, 20)
    x = random.randint(1, 10)
    answer = m * x + b
    question = (
        f"**Verification Question**\n"
        f"Using the slope-intercept formula `y = mx + b`:\n\n"
        f"If `m = {m}`, `b = {b}`, and `x = {x}`, what is `y`?\n\n"
        f"Reply with just the number."
    )
    return question, answer


def build_role_menu_text():
    lines = ["**Pick your roles!** React below to add/remove roles.\n"]
    for emoji, name, _ in SELF_ROLES:
        lines.append(f"{emoji} — {name}")
    return "\n".join(lines)


class VerificationView(discord.ui.View):
    """View for verification button."""

    def __init__(self, cog: "Verification"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.green, custom_id="hothelper_verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle verification button click."""
        try:
            guild = interaction.guild
            user = interaction.user

            if db.is_verified(user.id, guild.id):
                await interaction.response.send_message("You're already verified!", ephemeral=True)
                return

            await interaction.response.send_message("Check your DMs to verify!", ephemeral=True)

            try:
                dm = await user.create_dm()
            except discord.Forbidden:
                await interaction.followup.send(
                    "I couldn't DM you. Please enable DMs from server members and try again.",
                    ephemeral=True,
                )
                return

            success = await self.cog.run_verification_loop(dm, user)
            if not success:
                return

            # Look for a "Verified" role first, create it if missing
            verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
            if not verified_role:
                try:
                    verified_role = await guild.create_role(
                        name=VERIFIED_ROLE_NAME,
                        color=discord.Color.green(),
                        reason="Hot Helper verification system"
                    )
                    logger.info(f"Created Verified role in guild {guild.id}")
                except discord.Forbidden:
                    await dm.send("Bot lacks permissions to create role. Contact an admin.")
                    logger.error(f"Cannot create Verified role in guild {guild.id}: Permission denied")
                    return

            try:
                await user.add_roles(verified_role)
            except discord.Forbidden:
                await dm.send("Bot lacks permissions to assign role. Contact an admin.")
                logger.error(f"Cannot assign Verified role to user {user.id} in guild {guild.id}")
                return

            db.add_verification(user.id, guild.id)

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
            await dm.send(embed=embed)

            logger.info(f"User {user.id} verified in guild {guild.id}")

            # Send self-role menu
            await self.cog.send_self_role_menu(dm, guild.id)

        except Exception as e:
            logger.error(f"Error in verify_button: {e}", exc_info=True)
            try:
                await interaction.followup.send("An error occurred during verification.", ephemeral=True)
            except discord.HTTPException:
                pass


class Verification(commands.Cog):
    """Verification system commands."""

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerificationView(self))
        # message_id -> guild_id, for DM reaction handling
        self.active_role_menus = {}

    async def run_verification_loop(self, dm: discord.DMChannel, user: discord.User) -> bool:
        """Sends algebra questions until correct or timeout. Returns True on success."""
        while True:
            question, answer = generate_algebra_question()
            await dm.send(question)

            def check(m: discord.Message):
                return m.author.id == user.id and m.channel.id == dm.id

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=VERIFY_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                await dm.send("Verification timed out. Click ✅ Verify again to retry.")
                return False

            try:
                user_answer = int(reply.content.strip())
            except ValueError:
                await dm.send("That's not a number. Let's try a new question.")
                continue

            if user_answer == answer:
                return True
            else:
                await dm.send("❌ Incorrect. Here's a new question:")
                continue

    async def send_self_role_menu(self, dm: discord.DMChannel, guild_id: int):
        text = build_role_menu_text()
        menu_msg = await dm.send(text)

        for emoji, _, _ in SELF_ROLES:
            try:
                await menu_msg.add_reaction(emoji)
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.3)

        self.active_role_menus[menu_msg.id] = guild_id

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        await self._handle_reaction(reaction, user, adding=True)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        await self._handle_reaction(reaction, user, adding=False)

    async def _handle_reaction(self, reaction: discord.Reaction, user: discord.User, adding: bool):
        if user.bot:
            return
        if reaction.message.id not in self.active_role_menus:
            return

        guild_id = self.active_role_menus[reaction.message.id]
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        member = guild.get_member(user.id)
        if member is None:
            return

        emoji_str = str(reaction.emoji)
        match = next((r for r in SELF_ROLES if r[0] == emoji_str), None)
        if match is None:
            return

        _, role_name, _ = match
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            return

        try:
            if adding:
                await member.add_roles(role, reason="Self-role via DM reaction")
            else:
                await member.remove_roles(role, reason="Self-role removed via DM reaction")
        except discord.Forbidden:
            pass

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

            view = VerificationView(self)
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

            view = VerificationView(self)
            await interaction.response.send_message(embed=embed, view=view)

            logger.info(f"Verification embed posted in guild {interaction.guild.id}")

        except Exception as e:
            logger.error(f"Error in slash_setup_verify: {e}", exc_info=True)
            await interaction.response.send_message("❌ Error setting up verification.", ephemeral=True)

    @app_commands.command(name="setup_roles", description="Create all themed self-roles if they don't exist yet.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def setup_roles(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        existing_names = {role.name for role in guild.roles}
        created = []
        skipped = []

        if VERIFIED_ROLE_NAME not in existing_names:
            try:
                await guild.create_role(name=VERIFIED_ROLE_NAME, reason="Auto-created by /setup_roles")
                created.append(VERIFIED_ROLE_NAME)
            except discord.Forbidden:
                await interaction.followup.send(
                    "I don't have permission to create roles. Check my role's permissions.",
                    ephemeral=True,
                )
                return
        else:
            skipped.append(VERIFIED_ROLE_NAME)

        for emoji, name, color in SELF_ROLES:
            if name in existing_names:
                skipped.append(name)
                continue
            try:
                await guild.create_role(name=name, color=color, reason="Auto-created by /setup_roles")
                created.append(name)
            except discord.Forbidden:
                await interaction.followup.send(
                    "I don't have permission to create roles. Check my role's permissions.",
                    ephemeral=True,
                )
                return
            await asyncio.sleep(0.5)

        msg = ""
        if created:
            msg += f"**Created:** {', '.join(created)}\n"
        if skipped:
            msg += f"**Already existed (skipped):** {', '.join(skipped)}\n"
        if not msg:
            msg = "Nothing to do."

        await interaction.followup.send(msg, ephemeral=True)


async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Verification(bot))