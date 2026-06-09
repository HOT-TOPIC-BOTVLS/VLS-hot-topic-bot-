"""Voice Master cog for enhanced voice channel interaction."""

import discord
from discord.ext import commands
from database import Database
from logger import logger
from config import EMBED_COLOR_BLACK, EMBED_COLOR_RED

db = Database()

class VoiceMaster(commands.Cog):
    """Voice channel management and following system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.follow_mode = {}  # guild_id -> user_id (who to follow)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Auto-follow users if follow mode is enabled."""
        try:
            if member.bot or not member.guild:
                return
            
            guild_id = member.guild.id
            
            # Check if follow mode is active for this guild
            if guild_id not in self.follow_mode:
                return
            
            # Only follow the specific user
            if member.id != self.follow_mode[guild_id]:
                return
            
            # User moved to a new channel
            if before.channel != after.channel and after.channel is not None:
                voice_client = member.guild.voice_client
                
                if voice_client and voice_client.is_connected():
                    try:
                        await voice_client.move_to(after.channel)
                        logger.info(f"Bot followed {member.id} to {after.channel.name} in guild {guild_id}")
                    except Exception as e:
                        logger.error(f"Error moving bot to channel: {e}")
        
        except Exception as e:
            logger.error(f"Error in on_voice_state_update: {e}", exc_info=True)
    
    @commands.command(name="summon")
    async def summon(self, ctx):
        """Summon the bot to your voice channel."""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ You must be in a voice channel to summon the bot.")
                return
            
            channel = ctx.author.voice.channel
            
            # Disconnect if already connected
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
            
            # Connect to channel
            try:
                await channel.connect()
                embed = discord.Embed(
                    title="🎤 Connected",
                    description=f"Joined {channel.mention}",
                    color=EMBED_COLOR_BLACK
                )
                await ctx.send(embed=embed)
                logger.info(f"Bot summoned to {channel.name} in guild {ctx.guild.id}")
            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to join that channel.")
            except discord.DiscordException as e:
                await ctx.send(f"❌ Error joining channel: {e}")
        
        except Exception as e:
            logger.error(f"Error in summon command: {e}", exc_info=True)
            await ctx.send("❌ Error summoning bot.")
    
    @commands.command(name="follow")
    async def follow(self, ctx, user: discord.User = None):
        """Enable follow mode - bot will follow you between voice channels."""
        try:
            target = user or ctx.author
            
            if not target.voice:
                await ctx.send(f"❌ {target.mention} is not in a voice channel.")
                return
            
            # Enable follow mode
            self.follow_mode[ctx.guild.id] = target.id
            
            # Connect to user's channel if bot isn't already connected
            if not ctx.voice_client:
                try:
                    await target.voice.channel.connect()
                except Exception as e:
                    logger.error(f"Error connecting to channel: {e}")
                    await ctx.send("❌ Could not connect to voice channel.")
                    return
            
            embed = discord.Embed(
                title="👁️ Follow Mode Enabled",
                description=f"I will follow {target.mention} between voice channels.",
                color=EMBED_COLOR_BLACK
            )
            await ctx.send(embed=embed)
            logger.info(f"Follow mode enabled for {target.id} in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in follow command: {e}", exc_info=True)
            await ctx.send("❌ Error enabling follow mode.")
    
    @commands.command(name="unfollow")
    async def unfollow(self, ctx):
        """Disable follow mode."""
        try:
            if ctx.guild.id in self.follow_mode:
                del self.follow_mode[ctx.guild.id]
            
            embed = discord.Embed(
                title="👁️ Follow Mode Disabled",
                description="I will no longer automatically follow you.",
                color=EMBED_COLOR_BLACK
            )
            await ctx.send(embed=embed)
            logger.info(f"Follow mode disabled in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in unfollow command: {e}", exc_info=True)
            await ctx.send("❌ Error disabling follow mode.")
    
    @commands.command(name="leave")
    async def leave(self, ctx):
        """Disconnect the bot from voice channel."""
        try:
            if not ctx.voice_client:
                await ctx.send("❌ Bot is not in a voice channel.")
                return
            
            # Disable follow mode if active
            if ctx.guild.id in self.follow_mode:
                del self.follow_mode[ctx.guild.id]
            
            await ctx.voice_client.disconnect()
            
            embed = discord.Embed(
                title="👋 Disconnected",
                description="Left the voice channel.",
                color=EMBED_COLOR_BLACK
            )
            await ctx.send(embed=embed)
            logger.info(f"Bot disconnected from voice in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in leave command: {e}", exc_info=True)
            await ctx.send("❌ Error disconnecting.")
    
    @commands.command(name="playnow")
    async def play_now(self, ctx, *, query):
        """Skip queue and immediately play a song."""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ You must be in a voice channel.")
                return
            
            # Get music cog
            music_cog = self.bot.get_cog('Music')
            if not music_cog:
                await ctx.send("❌ Music system not available.")
                return
            
            # Get audio URL
            url, title = await music_cog.get_audio_url(query)
            if not url:
                await ctx.send("❌ Could not find that song.")
                return
            
            # Initialize player if needed
            if ctx.guild.id not in music_cog.music_players:
                music_cog.music_players[ctx.guild.id] = {
                    "queue": [],
                    "current_song": None,
                    "is_paused": False,
                    "volume": 100,
                    "loop_mode": "off",
                    "last_activity": discord.utils.utcnow()
                }
            
            # Create song object
            song = {"title": title, "url": url, "requester": ctx.author.name}
            
            # Insert at front of queue (play now)
            music_cog.music_players[ctx.guild.id]["queue"].insert(0, song)
            
            # Stop current song to play the new one
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            
            # Connect if needed
            if not ctx.voice_client:
                try:
                    await ctx.author.voice.channel.connect()
                except Exception as e:
                    logger.error(f"Error connecting: {e}")
                    await ctx.send("❌ Could not connect to voice channel.")
                    return
            
            embed = discord.Embed(
                title="⏭️ Playing Now",
                description=title,
                color=EMBED_COLOR_BLACK
            )
            await ctx.send(embed=embed)
            
            # Play the song
            await music_cog._play_next(ctx.guild)
            logger.info(f"Playing now: {title} in guild {ctx.guild.id}")
        
        except Exception as e:
            logger.error(f"Error in playnow command: {e}", exc_info=True)
            await ctx.send("❌ Error playing song.")
    
    @commands.command(name="vcstatus")
    async def vc_status(self, ctx):
        """Show voice channel status."""
        try:
            embed = discord.Embed(
                title="🎤 Voice Channel Status",
                color=EMBED_COLOR_BLACK
            )
            
            # Bot connection status
            if ctx.voice_client:
                embed.add_field(
                    name="Bot Status",
                    value=f"✅ Connected to {ctx.voice_client.channel.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Bot Status",
                    value="❌ Not connected",
                    inline=False
                )
            
            # Follow mode status
            if ctx.guild.id in self.follow_mode:
                user_id = self.follow_mode[ctx.guild.id]
                user = await self.bot.fetch_user(user_id)
                embed.add_field(
                    name="Follow Mode",
                    value=f"👁️ Following {user.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Follow Mode",
                    value="❌ Disabled",
                    inline=False
                )
            
            # User voice status
            if ctx.author.voice:
                embed.add_field(
                    name="Your Status",
                    value=f"✅ In {ctx.author.voice.channel.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Your Status",
                    value="❌ Not in voice",
                    inline=False
                )
            
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in vcstatus command: {e}", exc_info=True)
            await ctx.send("❌ Error checking voice status.")

async def setup(bot):
    """Load the cog."""
    await bot.add_cog(VoiceMaster(bot))
