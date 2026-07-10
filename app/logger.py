import logging
import os
import sys
from app.config import settings

# Ensure log directory exists
log_dir = os.path.dirname(settings.log_file)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

# Define detailed format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(filename)s:%(lineno)d | %(message)s"

# Setup the root logger
logger = logging.getLogger("docextract")
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

# File Handler (detailed, always appends to log file)
file_handler = logging.FileHandler(settings.log_file, encoding='utf-8')
file_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Add handlers
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def get_logger(name: str):
    """Get a child logger for a specific module."""
    return logger.getChild(name)
