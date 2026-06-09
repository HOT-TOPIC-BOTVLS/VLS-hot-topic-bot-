"""Hot Helper Discord Bot - Main entry point."""

import discord
from discord.ext import commands, tasks
import asyncio
import os
import signal
from pathlib import Path
from config import DISCORD_TOKEN, OWNER_ID, BOT_PREFIX, BOT_STATUSES, BOT_NAME
from database import Database
from logger import logger
import aiohttp
from aiohttp import web

# Initialize database
db = Database()

# Create bot with hybrid commands (prefix + slash)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix=BOT_PREFIX,
    intents=intents,
    help_command=None,
    owner_id=OWNER_ID,
    activity=discord.Activity(type=discord.ActivityType.playing, name=BOT_STATUSES[0])
)

# Status rotation
@tasks.loop(minutes=5)
async def rotate_status():
    """Rotate bot status."""
    try:
        status = BOT_STATUSES[hash(asyncio.get_event_loop().time()) % len(BOT_STATUSES)]
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=status))
    except Exception as e:
        logger.error(f"Error rotating status: {e}")

@rotate_status.before_loop
async def before_rotate_status():
    """Wait for bot to be ready."""
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    """Called when bot is ready."""
    logger.info(f"Bot logged in as {bot.user}")
    logger.info(f"Connected to {len(bot.guilds)} guilds")
    
    # Start status rotation
    if not rotate_status.is_running():
        rotate_status.start()
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        logger.error(f"Command error: {error}", exc_info=True)
        await ctx.send("❌ An error occurred while executing the command.")

@bot.event
async def on_error(event, *args, **kwargs):
    """Handle general errors."""
    logger.error(f"Error in {event}", exc_info=True)

async def load_cogs():
    """Load all cogs."""
    cogs_dir = Path(__file__).parent
    
    for cog_file in cogs_dir.glob("*.py"):
        if cog_file.name.startswith("_"):
            continue
        
        cog_name = cog_file.stem
        try:
            if cog_name in ["main", "config", "database", "logger"]:
    continue

await bot.load_extension(f"{cog_name}")
            logger.info(f"Loaded cog: {cog_name}")
        except Exception as e:
            logger.error(f"Error loading cog {cog_name}: {e}", exc_info=True)

def handle_sigterm(signum, frame):
    """Handle SIGTERM signal for graceful shutdown."""
    logger.info("SIGTERM received, initiating graceful shutdown...")
    asyncio.create_task(graceful_shutdown())

async def graceful_shutdown():
    """Gracefully shutdown the bot and save state."""
    try:
        logger.info("Saving bot state before shutdown...")
        
        # Save any pending music states
        if hasattr(bot, 'get_cog'):
            music_cog = bot.get_cog('Music')
            if music_cog:
                for guild_id, player in music_cog.music_players.items():
                    if player.get("queue"):
                        db.save_music_queue(
                            guild_id,
                            player.get("queue", []),
                            player.get("current_song"),
                            player.get("is_paused", False),
                            player.get("volume", 100),
                            player.get("loop_mode", "off")
                        )
                        logger.info(f"Saved music state for guild {guild_id}")
        
        logger.info("State saved, closing bot connection...")
        await bot.close()
        
    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}", exc_info=True)
        await bot.close()

     
async def start_health_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    logger.info("Health check server started on port 10000")

async def main():
    """Main entry point."""
    try:
        # Register SIGTERM handler for graceful shutdown (Render sends this)
        signal.signal(signal.SIGTERM, handle_sigterm)
        
        # Load cogs
        await load_cogs()
        await start_health_server()

        
        # Connect to Discord
        logger.info(f"Starting {BOT_NAME}...")
        await bot.start(DISCORD_TOKEN)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
