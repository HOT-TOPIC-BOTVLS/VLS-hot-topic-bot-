"""Configuration management for Hot Helper bot."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
owner_id_str = os.getenv("OWNER_ID", "")
if not owner_id_str:
    raise ValueError("OWNER_ID not set in .env file")
OWNER_ID = int(owner_id_str)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/hot_helper.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Dashboard Configuration
DISCORD_CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DASHBOARD_SECRET_KEY  = os.getenv("DASHBOARD_SECRET_KEY", "change-me")
DASHBOARD_PORT        = int(os.getenv("DASHBOARD_PORT", "8080"))

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH  = DATA_DIR / "hot_helper.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Bot Configuration
BOT_NAME = "Hot Helper"
BOT_PREFIX = "!"
BOT_STATUSES = [
    "Shopping at Hot Topic",
    "Helping the server",
    "Playing music",
]

# Embed Colors
EMBED_COLOR_BLACK = 0x000000
EMBED_COLOR_RED   = 0xFF0000
EMBED_COLOR_WHITE = 0xFFFFFF

# Moderation Configuration
MUTE_ROLE_NAME    = "Muted"
MIN_MUTE_DURATION = 5 * 60
MOD_MAX_MUTE      = 7  * 24 * 60 * 60
ADMIN_MAX_MUTE    = 30 * 24 * 60 * 60

# Raid Detection Configuration
DEFAULT_RAID_JOIN_THRESHOLD = 10
DEFAULT_RAID_WINDOW         = 60
DEFAULT_RAID_PATTERN_COUNT  = 5
RAID_LOCKDOWN_DURATION      = 5 * 60

# Music Configuration
MUSIC_INACTIVITY_TIMEOUT  = 30 * 60
MUSIC_STATE_SAVE_INTERVAL = 30

# Rate Limiting
SECURITY_FAILURE_THRESHOLD = 5
SECURITY_FAILURE_WINDOW    = 5 * 60

# Validation
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN not set in .env file")