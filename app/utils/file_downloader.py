"""Utility functions for downloading files from Telegram Bot API"""

import os
import shutil
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.types import File

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _sanitize_path_for_logging(file_path: str) -> str:
    """
    Sanitize file path for logging to avoid exposing bot token.
    
    When Bot API local is in --local mode, paths contain the bot token:
    /var/lib/telegram-bot-api/BOT_TOKEN/photos/file.jpg
    
    This function extracts only the safe relative part: photos/file.jpg
    
    Args:
        file_path: Original file path (absolute or relative)
    
    Returns:
        Sanitized path safe for logging (without token)
    """
    if not file_path.startswith("/var/lib/telegram-bot-api/"):
        # Not an absolute path from local Bot API, return as is
        return file_path.lstrip("/")
    
    # Extract relative path after bot token directory
    normalized = file_path.lstrip("/")
    parts = [p for p in normalized.split("/") if p]
    
    # Find bot token directory (contains ':' and is long enough)
    token_idx = None
    for i, part in enumerate(parts):
        if ":" in part and len(part) > 20:
            token_idx = i
            break
    
    if token_idx is not None and token_idx + 1 < len(parts):
        # Get everything after bot token directory
        relative_path = "/".join(parts[token_idx + 1:])
    elif parts:
        # Fallback: use just filename
        relative_path = parts[-1]
    else:
        relative_path = file_path.lstrip("/")
    
    # Ensure no leading slash
    return relative_path.lstrip("/")


def _copy_from_filesystem(
    source_path: Path,
    destination: Path,
    bot_api_data_path: Optional[Path] = None
) -> bool:
    """
    Try to copy file directly from filesystem (Bot API local volume).
    
    When Bot API local is in --local mode, files are stored in /var/lib/telegram-bot-api
    which is mounted as a Docker volume. This function attempts to copy the file directly
    from the mounted volume.
    
    Args:
        source_path: Absolute path to source file (e.g., /var/lib/telegram-bot-api/BOT_TOKEN/photos/file.jpg)
        destination: Path where to save the file
        bot_api_data_path: Optional path to Bot API data directory (for constructing alternative paths)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure destination directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Try direct copy first
        if source_path.exists() and source_path.is_file():
            # Sanitize path for logging (don't expose token)
            safe_source = _sanitize_path_for_logging(str(source_path))
            logger.debug(f"Copying file directly from filesystem: {safe_source} -> {destination}")
            shutil.copy2(source_path, destination)
            
            if destination.exists() and destination.stat().st_size > 0:
                logger.info(f"Successfully copied file from filesystem: {destination.stat().st_size} bytes")
                return True
        
        # If direct path doesn't work, try constructing from bot_api_data_path
        if bot_api_data_path and bot_api_data_path.exists():
            # Construct alternative path
            # source_path: /var/lib/telegram-bot-api/BOT_TOKEN/photos/file.jpg
            # Try: bot_api_data_path / BOT_TOKEN / photos / file.jpg
            parts = source_path.parts
            if len(parts) >= 2:
                # Find bot token directory index
                token_idx = None
                for i, part in enumerate(parts):
                    if ":" in part and len(part) > 20:
                        token_idx = i
                        break
                
                if token_idx is not None and token_idx + 1 < len(parts):
                    # Reconstruct path
                    alternative_path = bot_api_data_path / Path(*parts[token_idx:])
                    if alternative_path.exists() and alternative_path.is_file():
                        # Sanitize path for logging (don't expose token)
                        safe_alt = _sanitize_path_for_logging(str(alternative_path))
                        logger.debug(f"Copying file from alternative path: {safe_alt} -> {destination}")
                        shutil.copy2(alternative_path, destination)
                        
                        if destination.exists() and destination.stat().st_size > 0:
                            logger.info(f"Successfully copied file from alternative path: {destination.stat().st_size} bytes")
                            return True
        
        return False
    except PermissionError as e:
        # Sanitize path in error message
        safe_path = _sanitize_path_for_logging(str(source_path))
        logger.warning(f"Permission denied accessing filesystem: {safe_path} - {e}")
        return False
    except FileNotFoundError as e:
        # Sanitize path in error message
        safe_path = _sanitize_path_for_logging(str(source_path))
        logger.warning(f"File not found on filesystem: {safe_path} - {e}")
        return False
    except Exception as e:
        # Sanitize path in error message
        safe_path = _sanitize_path_for_logging(str(source_path))
        logger.warning(f"Error copying from filesystem: {safe_path} - {e}")
        return False


async def download_telegram_file(
    bot: Bot,
    file_info: File,
    destination: Path,
    bot_api_data_path: Optional[Path] = None
) -> bool:
    """
    Download file from Telegram, handling both local and cloud Bot API.
    
    When Bot API local is in --local mode, get_file() returns absolute paths.
    The correct approach is to read directly from the filesystem, not download via HTTP.
    
    Strategy:
    1. If file_path is absolute (local Bot API): copy directly from filesystem
    2. If file_path is relative (cloud Bot API): use bot.download_file() normally
    
    Args:
        bot: Bot instance (configured with TelegramAPIServer if using local API)
        file_info: File info from bot.get_file()
        destination: Path where to save the file
        bot_api_data_path: Optional path to Bot API data directory (defaults to /var/lib/telegram-bot-api)
    
    Returns:
        True if successful, False otherwise
    """
    if not file_info.file_path:
        logger.error("File path is empty")
        return False
    
    file_path = file_info.file_path
    safe_path = _sanitize_path_for_logging(file_path)  # For logging (no token exposure)
    
    # Determine Bot API data path
    if bot_api_data_path is None:
        if settings.telegram_bot_api_data_path:
            bot_api_data_path = Path(settings.telegram_bot_api_data_path)
        else:
            bot_api_data_path = Path("/var/lib/telegram-bot-api")
    
    # Ensure destination directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    # Strategy 1: Direct filesystem access (if file_path is absolute path from local Bot API)
    if file_path.startswith("/var/lib/telegram-bot-api/"):
        source_path = Path(file_path)
        logger.info(f"Attempting direct filesystem access: {safe_path}")
        
        if _copy_from_filesystem(source_path, destination, bot_api_data_path):
            logger.info(f"Successfully copied file from filesystem: {destination.stat().st_size} bytes")
            return True
        
        # If direct access fails, log clear error about UID/GID alignment
        logger.error(
            f"Failed to access file via filesystem: {safe_path}. "
            "This usually indicates a UID/GID mismatch. "
            "Ensure scoutbot container runs with user: '101:101' to match telegram-bot-api."
        )
        return False
    
    # Strategy 2: HTTP download (cloud Bot API or relative path)
    # This is the normal case when not using local Bot API
    try:
        logger.info(f"Downloading file via HTTP: {safe_path}")
        await bot.download_file(file_path, destination=destination)
        
        if destination.exists() and destination.stat().st_size > 0:
            logger.info(f"Successfully downloaded file via HTTP: {destination.stat().st_size} bytes")
            return True
        else:
            logger.error(f"Downloaded file is empty or missing: {safe_path}")
            return False
    except Exception as e:
        logger.error(f"HTTP download failed for {safe_path}: {e}")
        return False
