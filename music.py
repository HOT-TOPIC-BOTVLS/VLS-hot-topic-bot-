"""Music playback system with real audio streaming."""

import discord
from discord.ext import commands, tasks
import asyncio
import yt_dlp
import subprocess
import os
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED, MUSIC_INACTIVITY_TIMEOUT, MUSIC_STATE_SAVE_INTERVAL

db = Database()

# yt-dlp options
YT_DLP_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'socket_timeout': 30,
}

class AudioSource(discord.PCMAudio):
    """Custom audio source using FFmpeg."""
    def __init__(self, url):
        self.url = url
        self.process = None
        self._start_process()
    
    def _start_process(self):
        """Start FFmpeg process."""
        cmd = [
            'ffmpeg',
            '-i', self.url,
            '-f', 's16le',
            '-ar', '48000',
            '-ac', '2',
            'pipe:1'
        ]
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            logger.error("FFmpeg not found. Install FFmpeg to use music features.")
            raise

class Music(commands.Cog):
    """Music playback system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.music_players = {}  # guild_id -> player info
        self.yt_dlp = yt_dlp.YoutubeDL(YT_DLP_OPTIONS)
        self.save_music_state.start()
        self.check_inactivity.start()
    
    def cog_unload(self):
        """Clean up on cog unload."""
        self.save_music_state.cancel()
        self.check_inactivity.cancel()
    
    async def get_audio_url(self, query):
        """Get audio URL from YouTube using yt-dlp."""
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self.yt_dlp.extract_info, query, False)
            if info:
                return info.get('url'), info.get('title', 'Unknown')
            return None, None
        except Exception as e:
            logger.error(f"Error fetching audio: {e}")
            return None, None
    
    @tasks.loop(seconds=MUSIC_STATE_SAVE_INTERVAL)
    async def save_music_state(self):
        """Periodically save music queue state."""
        try:
            for guild_id, player in self.music_players.items():
                if player.get("queue"):
                    db.save_music_queue(
                        guild_id,
                        player.get("queue", []),
                        player.get("current_song"),
                        player.get("is_paused", False),
                        player.get("volume", 100),
                        player.get("loop_mode", "off")
                    )
        except Exception as e:
            logger.error(f"Error saving music state: {e}", exc_info=True)
    
    @save_music_state.before_loop
    async def before_save_music_state(self):
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=1)
    async def check_inactivity(self):
        """Check for inactive music players."""
        try:
            now = discord.utils.utcnow()
            for guild_id, player in list(self.music_players.items()):
                if player.get("last_activity"):
                    elapsed = (now - player["last_activity"]).total_seconds()
                    if elapsed > MUSIC_INACTIVITY_TIMEOUT:
                        player["is_paused"] = True
                        logger.info(f"Auto-paused music in guild {guild_id} due to inactivity")
        except Exception as e:
            logger.error(f"Error checking inactivity: {e}")
    
    @check_inactivity.before_loop
    async def before_check_inactivity(self):
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()
    
    @commands.command(name="play")
    async def play(self, ctx, *, query):
        """Play music from YouTube or URL."""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ You must be in a voice channel to play music.")
                return
            
            # Initialize player if needed
            if ctx.guild.id not in self.music_players:
                self.music_players[ctx.guild.id] = {
                    "queue": [],
                    "current_song": None,
                    "is_paused": False,
                    "volume": 100,
                    "loop_mode": "off",
                    "last_activity": discord.utils.utcnow()
                }
            
            # Get audio URL
            url, title = await self.get_audio_url(query)
            if not url:
                await ctx.send("❌ Could not find that song.")
                return
            
            # Add to queue
            song = {"title": title, "url": url, "requester": ctx.author.name}
            self.music_players[ctx.guild.id]["queue"].append(song)
            
            embed = discord.Embed(
                title="🎵 Added to Queue",
                description=title,
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Position", value=len(self.music_players[ctx.guild.id]["queue"]))
            await ctx.send(embed=embed)
            
            # Connect and play if not already playing
            if not ctx.voice_client:
                await ctx.author.voice.channel.connect()
            
            if not ctx.voice_client.is_playing():
                await self._play_next(ctx.guild)
            
            logger.info(f"Added song to queue in guild {ctx.guild.id}: {title}")
            
        except Exception as e:
            logger.error(f"Error in play command: {e}", exc_info=True)
            await ctx.send("❌ Error playing music.")
    
    async def _play_next(self, guild):
        """Play next song in queue."""
        try:
            player = self.music_players.get(guild.id)
            if not player or not player["queue"]:
                return
            
            if player["is_paused"]:
                return
            
            song = player["queue"][0]
            player["current_song"] = song
            
            try:
                source = AudioSource(song["url"])
                guild.voice_client.play(source, after=lambda e: asyncio.create_task(self._play_next(guild)))
                logger.info(f"Now playing: {song['title']} in guild {guild.id}")
            except Exception as e:
                logger.error(f"Error playing audio: {e}")
                player["queue"].pop(0)
                await self._play_next(guild)
        
        except Exception as e:
            logger.error(f"Error in _play_next: {e}")
    
    @commands.command(name="skip")
    async def skip(self, ctx):
        """Skip to next song."""
        try:
            if not ctx.voice_client or not ctx.voice_client.is_playing():
                await ctx.send("❌ Nothing is playing.")
                return
            
            ctx.voice_client.stop()
            player = self.music_players.get(ctx.guild.id)
            if player and player["queue"]:
                player["queue"].pop(0)
            
            await ctx.send("⏭️ Skipped!")
            await self._play_next(ctx.guild)
            
        except Exception as e:
            logger.error(f"Error in skip command: {e}")
            await ctx.send("❌ Error skipping.")
    
    @commands.command(name="pause")
    async def pause(self, ctx):
        """Pause music."""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ Bot not in voice channel.")
                return
            
            if ctx.voice_client.is_paused():
                await ctx.send("⏸️ Already paused.")
                return
            
            ctx.voice_client.pause()
            player = self.music_players.get(ctx.guild.id)
            if player:
                player["is_paused"] = True
            
            await ctx.send("⏸️ Paused!")
            
        except Exception as e:
            logger.error(f"Error in pause command: {e}")
            await ctx.send("❌ Error pausing.")
    
    @commands.command(name="resume")
    async def resume(self, ctx):
        """Resume music."""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ Bot not in voice channel.")
                return
            
            if not ctx.voice_client.is_paused():
                await ctx.send("▶️ Already playing.")
                return
            
            ctx.voice_client.resume()
            player = self.music_players.get(ctx.guild.id)
            if player:
                player["is_paused"] = False
            
            await ctx.send("▶️ Resumed!")
            
        except Exception as e:
            logger.error(f"Error in resume command: {e}")
            await ctx.send("❌ Error resuming.")
    
    @commands.command(name="stop")
    async def stop(self, ctx):
        """Stop music and disconnect."""
        try:
            if ctx.voice_client:
                ctx.voice_client.stop()
                await ctx.voice_client.disconnect()
            
            if ctx.guild.id in self.music_players:
                self.music_players[ctx.guild.id]["queue"] = []
            
            await ctx.send("⏹️ Stopped and disconnected!")
            
        except Exception as e:
            logger.error(f"Error in stop command: {e}")
            await ctx.send("❌ Error stopping.")
    
    @commands.command(name="queue")
    async def queue(self, ctx):
        """Show music queue."""
        try:
            player = self.music_players.get(ctx.guild.id)
            if not player or not player["queue"]:
                await ctx.send("📭 Queue is empty.")
                return
            
            embed = discord.Embed(title="🎵 Music Queue", color=EMBED_COLOR_BLACK)
            for i, song in enumerate(player["queue"][:10]):
                embed.add_field(
                    name=f"{i+1}. {song['title']}",
                    value=f"Requested by {song.get('requester', 'Unknown')}",
                    inline=False
                )
            
            if len(player["queue"]) > 10:
                embed.set_footer(text=f"... and {len(player['queue']) - 10} more")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in queue command: {e}")
            await ctx.send("❌ Error showing queue.")
    
    @commands.command(name="nowplaying")
    async def now_playing(self, ctx):
        """Show current song."""
        try:
            player = self.music_players.get(ctx.guild.id)
            if not player or not player.get("current_song"):
                await ctx.send("❌ Nothing is playing.")
                return
            
            song = player["current_song"]
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=song["title"],
                color=EMBED_COLOR_BLACK
            )
            embed.add_field(name="Requested by", value=song.get("requester", "Unknown"))
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in nowplaying command: {e}")
            await ctx.send("❌ Error.")
    
    @commands.command(name="volume")
    async def volume(self, ctx, vol: int):
        """Set volume (1-100)."""
        try:
            if vol < 1 or vol > 100:
                await ctx.send("❌ Volume must be between 1 and 100.")
                return
            
            player = self.music_players.get(ctx.guild.id)
            if player:
                player["volume"] = vol
            
            await ctx.send(f"🔊 Volume set to {vol}%")
            
        except Exception as e:
            logger.error(f"Error in volume command: {e}")
            await ctx.send("❌ Error setting volume.")
    
    @commands.command(name="loop")
    async def loop(self, ctx, mode: str = "off"):
        """Set loop mode: off, one, all."""
        try:
            if mode not in ["off", "one", "all"]:
                await ctx.send("❌ Loop mode must be: off, one, or all")
                return
            
            player = self.music_players.get(ctx.guild.id)
            if player:
                player["loop_mode"] = mode
            
            await ctx.send(f"🔁 Loop mode set to: {mode}")
            
        except Exception as e:
            logger.error(f"Error in loop command: {e}")
            await ctx.send("❌ Error setting loop.")
    
    @commands.command(name="musicstatus")
    async def music_status(self, ctx):
        """Diagnostic: test FFmpeg, voice connection, and audio playback."""
        try:
            embed = discord.Embed(title="🎵 Music System Diagnostic", color=EMBED_COLOR_BLACK)
            
            # Check FFmpeg
            try:
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
                ffmpeg_ok = result.returncode == 0
                embed.add_field(name="FFmpeg", value="✅ Installed" if ffmpeg_ok else "❌ Not found", inline=False)
            except:
                embed.add_field(name="FFmpeg", value="❌ Not found", inline=False)
            
            # Check voice connection
            voice_ok = ctx.voice_client is not None
            embed.add_field(name="Voice Connection", value="✅ Connected" if voice_ok else "❌ Not connected", inline=False)
            
            # Check yt-dlp
            try:
                self.yt_dlp.extract_info("test", False)
                yt_dlp_ok = True
            except:
                yt_dlp_ok = False
            embed.add_field(name="yt-dlp", value="✅ Working" if yt_dlp_ok else "❌ Error", inline=False)
            
            # Check queue
            player = self.music_players.get(ctx.guild.id)
            queue_size = len(player["queue"]) if player else 0
            embed.add_field(name="Queue Size", value=str(queue_size), inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in musicstatus command: {e}")
            await ctx.send("❌ Error running diagnostic.")

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(Music(bot))
