"""Logging configuration for Hot Helper bot."""

import logging
import logging.handlers
from pathlib import Path
from config import LOGS_DIR, LOG_LEVEL

def setup_logger(name="hot_helper"):
    """Set up structured logging with file rotation."""
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with daily rotation
    log_file = LOGS_DIR / "bot.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=7  # Keep 7 days of logs
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Create global logger
logger = setup_logger()
