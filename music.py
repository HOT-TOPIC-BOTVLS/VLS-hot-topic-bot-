"""Music playback system with real audio streaming (yt-dlp + FFmpeg).

Commands kept the same:
  !play, !skip, !pause, !resume, !stop, !queue, !nowplaying,
  !volume, !loop, !musicstatus
"""

import asyncio
import discord
from discord.ext import commands, tasks
import yt_dlp
import subprocess
from database import Database
from logger import logger
from config import (
    EMBED_COLOR_BLACK,
    MUSIC_INACTIVITY_TIMEOUT,
    MUSIC_STATE_SAVE_INTERVAL,
)

db = Database()

# yt-dlp: extract stream URL only (no download to disk)
YTDL_FORMAT_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

# FFmpeg: reconnect on flaky streams, audio only
FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"


class YTDLSource(discord.PCMVolumeTransformer):
    """Audio source built from a yt-dlp stream URL."""

    def __init__(self, source: discord.AudioSource, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Unknown")
        self.url = data.get("webpage_url") or data.get("url")
        self.requester = data.get("requester", "Unknown")

    @classmethod
    async def from_query(cls, query: str, *, loop: asyncio.AbstractEventLoop, volume: float = 0.5, requester: str = "Unknown"):
        loop = loop or asyncio.get_event_loop()

        def extract():
            with yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS) as ydl:
                # If it's not already a URL, search YouTube
                info = ydl.extract_info(query, download=False)
                if "entries" in info:
                    # search result or playlist — take first entry
                    info = info["entries"][0]
                return info

        data = await loop.run_in_executor(None, extract)
        if not data:
            raise ValueError("No results found")

        stream_url = data.get("url")
        if not stream_url:
            raise ValueError("Could not extract stream URL")

        data["requester"] = requester

        source = discord.FFmpegPCMAudio(
            stream_url,
            before_options=FFMPEG_BEFORE,
            options=FFMPEG_OPTIONS,
        )
        return cls(source, data=data, volume=volume)


class Music(commands.Cog):
    """Music playback system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> player state
        self.players: dict[int, dict] = {}
        self.save_music_state.start()
        self.check_inactivity.start()

    def cog_unload(self):
        self.save_music_state.cancel()
        self.check_inactivity.cancel()

    # ------------------------------------------------------------------
    # Player helpers
    # ------------------------------------------------------------------
    def _get_player(self, guild_id: int) -> dict:
        if guild_id not in self.players:
            self.players[guild_id] = {
                "queue": [],           # list of {"title", "query", "requester"}
                "current": None,       # currently playing song dict
                "volume": 0.5,         # 0.0 – 1.0
                "loop_mode": "off",    # off | one | all
                "last_activity": discord.utils.utcnow(),
            }
        return self.players[guild_id]

    def _touch(self, guild_id: int):
        self._get_player(guild_id)["last_activity"] = discord.utils.utcnow()

    async def _ensure_voice(self, ctx: commands.Context) -> discord.VoiceClient | None:
        """Connect to the author's voice channel if needed."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel to play music.")
            return None

        channel = ctx.author.voice.channel
        if ctx.voice_client:
            if ctx.voice_client.channel.id != channel.id:
                await ctx.voice_client.move_to(channel)
            return ctx.voice_client

        try:
            return await channel.connect(timeout=15.0, reconnect=True)
        except Exception as e:
            logger.error(f"Voice connect failed: {e}", exc_info=True)
            await ctx.send("❌ Could not join the voice channel.")
            return None

    def _after_play(self, guild: discord.Guild, error: Exception | None):
        """Called when a track ends (or errors). Runs in a thread — schedule async work safely."""
        if error:
            logger.error(f"Player error in guild {guild.id}: {error}")

        def schedule():
            asyncio.create_task(self._play_next(guild))

        try:
            self.bot.loop.call_soon_threadsafe(schedule)
        except Exception as e:
            logger.error(f"Failed to schedule next track: {e}")

    async def _play_next(self, guild: discord.Guild):
        """Play the next song in the queue (respects loop mode)."""
        player = self._get_player(guild.id)
        vc = guild.voice_client

        if not vc or not vc.is_connected():
            return

        # Handle loop for the song that just finished
        finished = player.get("current")
        if finished:
            mode = player.get("loop_mode", "off")
            if mode == "one":
                # put the same song back at the front
                player["queue"].insert(0, finished)
            elif mode == "all":
                player["queue"].append(finished)
            # mode == "off" → drop it

        player["current"] = None

        if not player["queue"]:
            # nothing left — stay connected a bit; inactivity task will leave
            return

        song = player["queue"].pop(0)
        player["current"] = song
        self._touch(guild.id)

        try:
            source = await YTDLSource.from_query(
                song["query"],
                loop=self.bot.loop,
                volume=player["volume"],
                requester=song.get("requester", "Unknown"),
            )
            # keep title in sync in case search resolved differently
            song["title"] = source.title
            player["current"] = song

            vc.play(source, after=lambda e: self._after_play(guild, e))
            logger.info(f"Now playing in {guild.id}: {source.title}")
        except Exception as e:
            logger.error(f"Failed to play next track: {e}", exc_info=True)
            # skip bad track and try the following one
            player["current"] = None
            await self._play_next(guild)

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------
    @tasks.loop(seconds=MUSIC_STATE_SAVE_INTERVAL)
    async def save_music_state(self):
        try:
            for guild_id, player in self.players.items():
                if player.get("queue") or player.get("current"):
                    db.save_music_queue(
                        guild_id,
                        player.get("queue", []),
                        player.get("current"),
                        False,
                        int(player.get("volume", 0.5) * 100),
                        player.get("loop_mode", "off"),
                    )
        except Exception as e:
            logger.error(f"Error saving music state: {e}", exc_info=True)

    @save_music_state.before_loop
    async def before_save_music_state(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=1)
    async def check_inactivity(self):
        try:
            now = discord.utils.utcnow()
            for guild_id, player in list(self.players.items()):
                last = player.get("last_activity")
                if not last:
                    continue
                elapsed = (now - last).total_seconds()
                if elapsed < MUSIC_INACTIVITY_TIMEOUT:
                    continue

                guild = self.bot.get_guild(guild_id)
                if not guild or not guild.voice_client:
                    continue

                # only leave if nothing is actually playing
                if guild.voice_client.is_playing() or guild.voice_client.is_paused():
                    continue

                try:
                    await guild.voice_client.disconnect()
                    logger.info(f"Left voice in guild {guild_id} due to inactivity")
                except Exception:
                    pass
                player["queue"].clear()
                player["current"] = None
        except Exception as e:
            logger.error(f"Error checking inactivity: {e}", exc_info=True)

    @check_inactivity.before_loop
    async def before_check_inactivity(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    @commands.command(name="play")
    async def play(self, ctx: commands.Context, *, query: str):
        """Play music from YouTube, SoundCloud, or a URL. Usage: !play <query or URL>"""
        vc = await self._ensure_voice(ctx)
        if not vc:
            return

        player = self._get_player(ctx.guild.id)
        self._touch(ctx.guild.id)

        # Resolve title early so the queue message looks nice
        status = await ctx.send(f"🔎 Searching for `{query[:80]}`…")

        try:
            # Quick extract just for the title (full stream extract happens at play time)
            def quick_info():
                opts = {**YTDL_FORMAT_OPTIONS, "skip_download": True}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if "entries" in info:
                        info = info["entries"][0]
                    return info.get("title", query), info.get("webpage_url") or query

            title, resolved = await self.bot.loop.run_in_executor(None, quick_info)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            await status.edit(content="❌ Could not find that song.")
            return

        song = {
            "title": title,
            "query": resolved or query,  # prefer stable webpage URL / original query
            "requester": ctx.author.display_name,
        }
        player["queue"].append(song)

        embed = discord.Embed(
            title="🎵 Added to Queue",
            description=title,
            color=EMBED_COLOR_BLACK,
        )
        embed.add_field(name="Position", value=str(len(player["queue"])), inline=True)
        embed.add_field(name="Requested by", value=ctx.author.display_name, inline=True)
        await status.edit(content=None, embed=embed)

        # Start playback if nothing is playing
        if not vc.is_playing() and not vc.is_paused():
            await self._play_next(ctx.guild)

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        """Skip to the next song."""
        if not ctx.voice_client or not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            await ctx.send("❌ Nothing is playing.")
            return

        player = self._get_player(ctx.guild.id)
        # force "off" behavior for the current track so it isn't re-queued by loop one
        if player.get("loop_mode") == "one":
            player["current"] = None

        ctx.voice_client.stop()  # triggers after → _play_next
        self._touch(ctx.guild.id)
        await ctx.send("⏭️ Skipped!")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause the current track."""
        if not ctx.voice_client:
            await ctx.send("❌ Bot is not in a voice channel.")
            return
        if ctx.voice_client.is_paused():
            await ctx.send("⏸️ Already paused.")
            return
        if not ctx.voice_client.is_playing():
            await ctx.send("❌ Nothing is playing.")
            return

        ctx.voice_client.pause()
        self._touch(ctx.guild.id)
        await ctx.send("⏸️ Paused!")

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        """Resume paused music."""
        if not ctx.voice_client:
            await ctx.send("❌ Bot is not in a voice channel.")
            return
        if not ctx.voice_client.is_paused():
            await ctx.send("▶️ Not paused.")
            return

        ctx.voice_client.resume()
        self._touch(ctx.guild.id)
        await ctx.send("▶️ Resumed!")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Stop music, clear the queue, and disconnect."""
        player = self._get_player(ctx.guild.id)
        player["queue"].clear()
        player["current"] = None
        player["loop_mode"] = "off"

        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()

        await ctx.send("⏹️ Stopped and disconnected!")

    @commands.command(name="queue")
    async def queue(self, ctx: commands.Context):
        """Show the music queue."""
        player = self._get_player(ctx.guild.id)
        current = player.get("current")
        q = player.get("queue", [])

        if not current and not q:
            await ctx.send("📭 Queue is empty.")
            return

        embed = discord.Embed(title="🎵 Music Queue", color=EMBED_COLOR_BLACK)
        if current:
            embed.add_field(
                name="▶️ Now Playing",
                value=f"**{current['title']}** — {current.get('requester', '?')}",
                inline=False,
            )

        if q:
            lines = []
            for i, song in enumerate(q[:10], start=1):
                lines.append(f"`{i}.` **{song['title']}** — {song.get('requester', '?')}")
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
            if len(q) > 10:
                embed.set_footer(text=f"… and {len(q) - 10} more")
        else:
            embed.add_field(name="Up Next", value="*(empty)*", inline=False)

        embed.add_field(
            name="Settings",
            value=f"Volume: **{int(player['volume'] * 100)}%** · Loop: **{player['loop_mode']}**",
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    async def now_playing(self, ctx: commands.Context):
        """Show the currently playing song."""
        player = self._get_player(ctx.guild.id)
        song = player.get("current")
        if not song or not ctx.voice_client or not (
            ctx.voice_client.is_playing() or ctx.voice_client.is_paused()
        ):
            await ctx.send("❌ Nothing is playing.")
            return

        status = "⏸️ Paused" if ctx.voice_client.is_paused() else "▶️ Playing"
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{song['title']}**",
            color=EMBED_COLOR_BLACK,
        )
        embed.add_field(name="Requested by", value=song.get("requester", "Unknown"), inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Volume", value=f"{int(player['volume'] * 100)}%", inline=True)
        embed.add_field(name="Loop", value=player["loop_mode"], inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, vol: int):
        """Set volume (1–100). Usage: !volume 50"""
        if vol < 1 or vol > 100:
            await ctx.send("❌ Volume must be between 1 and 100.")
            return

        player = self._get_player(ctx.guild.id)
        player["volume"] = vol / 100.0
        self._touch(ctx.guild.id)

        # Apply to the live source if possible
        if ctx.voice_client and ctx.voice_client.source:
            if isinstance(ctx.voice_client.source, discord.PCMVolumeTransformer):
                ctx.voice_client.source.volume = player["volume"]

        await ctx.send(f"🔊 Volume set to **{vol}%**")

    @commands.command(name="loop")
    async def loop(self, ctx: commands.Context, mode: str = "off"):
        """Set loop mode: off, one, or all. Usage: !loop one"""
        mode = mode.lower().strip()
        if mode not in ("off", "one", "all"):
            await ctx.send("❌ Loop mode must be: `off`, `one`, or `all`")
            return

        player = self._get_player(ctx.guild.id)
        player["loop_mode"] = mode
        self._touch(ctx.guild.id)
        await ctx.send(f"🔁 Loop mode set to: **{mode}**")

    @commands.command(name="musicstatus")
    async def music_status(self, ctx: commands.Context):
        """Diagnostic: FFmpeg, voice connection, queue, yt-dlp."""
        embed = discord.Embed(title="🎵 Music System Diagnostic", color=EMBED_COLOR_BLACK)

        # FFmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, timeout=5, text=True
            )
            ok = result.returncode == 0
            version = result.stdout.split("\n")[0] if ok else "not found"
            embed.add_field(
                name="FFmpeg",
                value=f"✅ {version[:60]}" if ok else "❌ Not found / not in PATH",
                inline=False,
            )
        except Exception:
            embed.add_field(name="FFmpeg", value="❌ Not found / not in PATH", inline=False)

        # Voice
        vc = ctx.voice_client
        if vc and vc.is_connected():
            state = "playing" if vc.is_playing() else ("paused" if vc.is_paused() else "idle")
            embed.add_field(
                name="Voice Connection",
                value=f"✅ Connected to **{vc.channel.name}** ({state})",
                inline=False,
            )
        else:
            embed.add_field(name="Voice Connection", value="❌ Not connected", inline=False)

        # yt-dlp
        try:
            import yt_dlp as ytdlp_mod
            ver = getattr(getattr(ytdlp_mod, "version", None), "__version__", "unknown")
            embed.add_field(name="yt-dlp", value=f"✅ v{ver}", inline=False)
        except Exception as e:
            embed.add_field(name="yt-dlp", value=f"❌ {e}", inline=False)

        player = self._get_player(ctx.guild.id)
        embed.add_field(
            name="Queue",
            value=f"{len(player['queue'])} waiting · current: {player['current']['title'] if player.get('current') else 'none'}",
            inline=False,
        )
        embed.add_field(
            name="Settings",
            value=f"Volume {int(player['volume']*100)}% · Loop `{player['loop_mode']}`",
            inline=False,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))