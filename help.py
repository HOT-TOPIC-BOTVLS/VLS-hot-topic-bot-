"""Help command cog for Hot Helper bot. Lists all prefix and slash commands."""

import discord
from discord.ext import commands
from discord import app_commands
from config import EMBED_COLOR_BLACK, BOT_PREFIX


class Help(commands.Cog):
    """Combined help command for prefix and slash commands."""

    def __init__(self, bot):
        self.bot = bot

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Hot Helper — Commands",
            description=f"Prefix commands use `{BOT_PREFIX}`, slash commands use `/`.",
            color=EMBED_COLOR_BLACK
        )

        # Prefix commands, grouped by cog
        prefix_by_cog = {}
        for cmd in self.bot.commands:
            if cmd.hidden:
                continue
            cog_name = cmd.cog_name or "Other"
            prefix_by_cog.setdefault(cog_name, []).append(cmd)

        for cog_name in sorted(prefix_by_cog):
            cmds = sorted(prefix_by_cog[cog_name], key=lambda c: c.name)
            value = "\n".join(
                f"`{BOT_PREFIX}{c.name}` — {c.help or 'No description'}"
                for c in cmds
            )
            embed.add_field(name=f"📌 {cog_name} (prefix)", value=value, inline=False)

        # Slash commands, flat list (app_commands doesn't group by cog the same way)
        slash_cmds = sorted(self.bot.tree.get_commands(), key=lambda c: c.name)
        if slash_cmds:
            value = "\n".join(
                f"`/{c.name}` — {c.description or 'No description'}"
                for c in slash_cmds
            )
            embed.add_field(name="⚡ Slash Commands", value=value, inline=False)

        embed.set_footer(text="Hot Helper")
        return embed

    @commands.command(name="help")
    async def help_prefix(self, ctx):
        """Shows all available commands."""
        await ctx.send(embed=self._build_embed())

    @app_commands.command(name="help", description="Shows all available commands")
    async def help_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._build_embed(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))