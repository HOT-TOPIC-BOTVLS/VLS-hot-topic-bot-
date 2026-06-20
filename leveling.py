"""
Leveling / XP Auto-Rank System
------------------------------
discord.py cog that:
  - Tracks XP per user (gained from sending messages, with cooldown)
  - Auto-creates Discord roles for each defined rank if they don't exist
  - Automatically assigns the correct rank role as users level up
    (and removes the previous rank role so only one applies at a time)
  - Persists data in SQLite so it survives restarts

Drop this file in your bot's /cogs folder and load it with:
    await bot.load_extension("cogs.leveling")
"""

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import time
import random
import math

DB_PATH = "leveling.db"

# ---------------------------------------------------------------------------
# RANK DEFINITIONS
# Edit this list to whatever ranks you want. Each entry:
#   name        -> role name (created automatically if it doesn't exist)
#   xp_required -> total XP needed to reach this rank
#   color       -> discord.Color for the role (optional, cosmetic)
# Keep them sorted ascending by xp_required.
# ---------------------------------------------------------------------------
RANKS = [
    {"name": "Mall Rat",        "xp_required": 0,     "color": discord.Color.light_gray()},
    {"name": "Lurker",          "xp_required": 100,   "color": discord.Color.dark_gray()},
    {"name": "Clearance Rack",  "xp_required": 300,   "color": discord.Color.dark_teal()},
    {"name": "Regular",         "xp_required": 700,   "color": discord.Color.blue()},
    {"name": "Black Nail Elite","xp_required": 1500,  "color": discord.Color.dark_purple()},
    {"name": "Fit Check Icon",  "xp_required": 3000,  "color": discord.Color.magenta()},
    {"name": "Goth Icon",       "xp_required": 6000,  "color": discord.Color.purple()},
    {"name": "Cave Veteran",    "xp_required": 10000, "color": discord.Color.dark_magenta()},
    {"name": "Cave Legend",     "xp_required": 18000, "color": discord.Color.dark_red()},
]

# XP gain settings
XP_MIN = 5
XP_MAX = 15
XP_COOLDOWN_SECONDS = 60  # one XP-eligible message per user per this many seconds


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldowns: dict[int, float] = {}  # user_id -> last xp timestamp
        self._init_db()

    # -------------------------------------------------------------------
    # DB setup
    # -------------------------------------------------------------------
    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                guild_id INTEGER,
                user_id INTEGER,
                xp INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        conn.commit()
        conn.close()

    def get_xp(self, guild_id: int, user_id: int) -> int:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT xp FROM users WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0

    def set_xp(self, guild_id: int, user_id: int, xp: int):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (guild_id, user_id, xp) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET xp=excluded.xp
        """, (guild_id, user_id, xp))
        conn.commit()
        conn.close()

    def add_xp(self, guild_id: int, user_id: int, amount: int) -> int:
        new_xp = self.get_xp(guild_id, user_id) + amount
        self.set_xp(guild_id, user_id, new_xp)
        return new_xp

    # -------------------------------------------------------------------
    # Rank helpers
    # -------------------------------------------------------------------
    def rank_for_xp(self, xp: int) -> dict:
        """Return the highest rank dict the user qualifies for."""
        current = RANKS[0]
        for rank in RANKS:
            if xp >= rank["xp_required"]:
                current = rank
            else:
                break
        return current

    def next_rank_for_xp(self, xp: int) -> dict | None:
        for rank in RANKS:
            if xp < rank["xp_required"]:
                return rank
        return None  # already maxed

    async def ensure_roles_exist(self, guild: discord.Guild) -> dict[str, discord.Role]:
        """Create any missing rank roles in the guild. Returns name -> Role map."""
        existing = {r.name: r for r in guild.roles}
        role_map = {}
        for rank in RANKS:
            if rank["name"] in existing:
                role_map[rank["name"]] = existing[rank["name"]]
            else:
                try:
                    new_role = await guild.create_role(
                        name=rank["name"],
                        color=rank.get("color", discord.Color.default()),
                        reason="Auto-created by leveling system",
                    )
                    role_map[rank["name"]] = new_role
                except discord.Forbidden:
                    print(f"[leveling] Missing permissions to create role '{rank['name']}' in {guild.name}")
        return role_map

    async def apply_rank(self, member: discord.Member, xp: int):
        """Assign the correct rank role and strip any other rank roles."""
        guild = member.guild
        role_map = await self.ensure_roles_exist(guild)
        target_rank = self.rank_for_xp(xp)
        target_role = role_map.get(target_rank["name"])
        if target_role is None:
            return

        all_rank_roles = set(role_map.values())
        member_rank_roles = set(member.roles) & all_rank_roles

        # Already correct, nothing to do
        if member_rank_roles == {target_role}:
            return

        to_remove = member_rank_roles - {target_role}
        to_add = [] if target_role in member.roles else [target_role]

        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason="Rank update")
            if to_add:
                await member.add_roles(*to_add, reason="Rank update")
        except discord.Forbidden:
            print(f"[leveling] Missing permissions to update roles for {member} in {guild.name}")

        return target_role

    # -------------------------------------------------------------------
    # Listeners
    # -------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        # Make sure rank roles exist in every guild the bot is in
        for guild in self.bot.guilds:
            await self.ensure_roles_exist(guild)
        print("[leveling] Ranks verified/created across all guilds.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        now = time.time()
        last = self.cooldowns.get(message.author.id, 0)
        if now - last < XP_COOLDOWN_SECONDS:
            return
        self.cooldowns[message.author.id] = now

        gained = random.randint(XP_MIN, XP_MAX)
        new_xp = self.add_xp(message.guild.id, message.author.id, gained)

        old_rank = self.rank_for_xp(new_xp - gained)
        new_rank = self.rank_for_xp(new_xp)

        if new_rank["name"] != old_rank["name"]:
            new_role = await self.apply_rank(message.author, new_xp)
            if new_role:
                try:
                    await message.channel.send(
                        f"🎖️ {message.author.mention} ranked up to **{new_rank['name']}**!"
                    )
                except discord.Forbidden:
                    pass
        else:
            # Still ensure role is correct even without rank-up (e.g. role was manually removed)
            await self.apply_rank(message.author, new_xp)

    # -------------------------------------------------------------------
    # Slash commands
    # -------------------------------------------------------------------
    @app_commands.command(name="rank", description="Check your (or someone else's) current rank and XP.")
    @app_commands.describe(member="The member to check (defaults to you)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        xp = self.get_xp(interaction.guild_id, member.id)
        current = self.rank_for_xp(xp)
        nxt = self.next_rank_for_xp(xp)

        embed = discord.Embed(title=f"{member.display_name}'s Rank", color=current.get("color", discord.Color.default()))
        embed.add_field(name="Current Rank", value=current["name"], inline=True)
        embed.add_field(name="XP", value=str(xp), inline=True)
        if nxt:
            remaining = nxt["xp_required"] - xp
            embed.add_field(name="Next Rank", value=f"{nxt['name']} ({remaining} XP to go)", inline=False)
        else:
            embed.add_field(name="Next Rank", value="Max rank reached", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the top-XP members in this server.")
    async def leaderboard(self, interaction: discord.Interaction):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT user_id, xp FROM users WHERE guild_id=? ORDER BY xp DESC LIMIT 10",
            (interaction.guild_id,),
        )
        rows = c.fetchall()
        conn.close()

        if not rows:
            await interaction.response.send_message("No XP data yet.")
            return

        lines = []
        for i, (user_id, xp) in enumerate(rows, start=1):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            rank_name = self.rank_for_xp(xp)["name"]
            lines.append(f"**{i}.** {name} — {xp} XP ({rank_name})")

        embed = discord.Embed(title="🏆 XP Leaderboard", description="\n".join(lines), color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setxp", description="[Admin] Manually set a member's XP.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="Member to update", xp="New XP value")
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        self.set_xp(interaction.guild_id, member.id, xp)
        await self.apply_rank(member, xp)
        await interaction.response.send_message(
            f"Set {member.mention}'s XP to {xp}. Rank updated to **{self.rank_for_xp(xp)['name']}**.",
            ephemeral=True,
        )

    @app_commands.command(name="initranks", description="[Admin] Force-create all rank roles now.")
    @app_commands.checks.has_permissions(administrator=True)
    async def initranks(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role_map = await self.ensure_roles_exist(interaction.guild)
        await interaction.followup.send(
            f"Verified/created {len(role_map)} rank roles: " + ", ".join(role_map.keys()),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))