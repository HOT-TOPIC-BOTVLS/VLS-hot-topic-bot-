"""Help command cog for Hot Helper bot. Lists all prefix and slash commands."""

import discord
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR_BLACK, BOT_PREFIX

MAX_FIELD_LEN = 1000  # stay safely under Discord's 1024 hard limit
MAX_FIELDS_PER_EMBED = 24  # stay under 25, leave room for footer/etc.


def chunk_lines(lines, max_len=MAX_FIELD_LEN):
    """Split a list of command lines into chunks that each fit in one embed field."""
    chunks = []
    current = ""
    for line in lines:
        addition = (line + "\n")
        if len(current) + len(addition) > max_len:
            chunks.append(current.rstrip())
            current = ""
        current += addition
    if current:
        chunks.append(current.rstrip())
    return chunks


class Help(commands.Cog):
    """Combined help command for prefix and slash commands."""

    def __init__(self, bot):
        self.bot = bot

    def _build_embeds(self) -> list[discord.Embed]:
        """Returns a list of embeds (paginated) instead of a single embed,
        since the full command list no longer fits in one."""
        embeds = []

        def new_embed(title_suffix=""):
            e = discord.Embed(
                title=f"Hot Helper — Commands{title_suffix}",
                description=f"Prefix commands use `{BOT_PREFIX}`, slash commands use `/`."
                if not title_suffix else None,
                color=EMBED_COLOR_BLACK
            )
            e.set_footer(text="Hot Helper")
            return e

        embed = new_embed()
        field_count = 0

        def add_field_safely(name, value):
            nonlocal embed, field_count
            if field_count >= MAX_FIELDS_PER_EMBED:
                embeds.append(embed)
                embed = new_embed(" (cont.)")
                field_count = 0
            embed.add_field(name=name, value=value or "—", inline=False)
            field_count += 1

        # Prefix commands, grouped by cog
        prefix_by_cog = {}
        for cmd in self.bot.commands:
            if cmd.hidden:
                continue
            cog_name = cmd.cog_name or "Other"
            prefix_by_cog.setdefault(cog_name, []).append(cmd)

        for cog_name in sorted(prefix_by_cog):
            cmds = sorted(prefix_by_cog[cog_name], key=lambda c: c.name)
            lines = [f"`{BOT_PREFIX}{c.name}` — {c.help or 'No description'}" for c in cmds]
            chunks = chunk_lines(lines)
            total = len(chunks)
            for i, chunk in enumerate(chunks, start=1):
                label = f"📌 {cog_name} (prefix)" if total == 1 else f"📌 {cog_name} (prefix) {i}/{total}"
                add_field_safely(label, chunk)

        # Slash commands, flat list, also chunked
        slash_cmds = sorted(self.bot.tree.get_commands(), key=lambda c: c.name)
        if slash_cmds:
            lines = [f"`/{c.name}` — {c.description or 'No description'}" for c in slash_cmds]
            chunks = chunk_lines(lines)
            total = len(chunks)
            for i, chunk in enumerate(chunks, start=1):
                label = "⚡ Slash Commands" if total == 1 else f"⚡ Slash Commands {i}/{total}"
                add_field_safely(label, chunk)

        embeds.append(embed)
        return embeds

    @commands.command(name="help")
    async def help_prefix(self, ctx):
        """Shows all available commands."""
        embeds = self._build_embeds()
        for embed in embeds:
            await ctx.send(embed=embed)

    @app_commands.command(name="help", description="Shows all available commands")
    async def help_slash(self, interaction: discord.Interaction):
        embeds = self._build_embeds()
        await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        for embed in embeds[1:]:
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))