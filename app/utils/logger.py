"""Structured logging setup using structlog"""

import logging
import os
import sys
from typing import Any, Optional

import structlog

from app.config import settings


def configure_third_party_loggers(log_level: int):
    """Configure third-party library loggers to reduce verbosity - ERROR only in production"""

    # Set all third-party loggers to ERROR minimum (suppress INFO, DEBUG, WARNING)
    error_level = logging.ERROR
    
    # Uvicorn - ERROR only
    logging.getLogger("uvicorn.access").setLevel(error_level)
    logging.getLogger("uvicorn.error").setLevel(error_level)

    # APScheduler - ERROR only
    logging.getLogger("apscheduler").setLevel(error_level)
    logging.getLogger("apscheduler.executors").setLevel(error_level)
    logging.getLogger("apscheduler.jobstores").setLevel(error_level)

    # Aiohttp - ERROR only
    logging.getLogger("aiohttp").setLevel(error_level)
    logging.getLogger("aiohttp.client").setLevel(error_level)
    logging.getLogger("aiohttp.server").setLevel(error_level)
    logging.getLogger("aiohttp.web").setLevel(error_level)
    
    # Feedparser - ERROR only
    logging.getLogger("feedparser").setLevel(error_level)
    
    # SQLAlchemy - ERROR only
    logging.getLogger("sqlalchemy").setLevel(error_level)
    logging.getLogger("sqlalchemy.engine").setLevel(error_level)
    logging.getLogger("sqlalchemy.pool").setLevel(error_level)
    logging.getLogger("sqlalchemy.dialects").setLevel(error_level)
    
    # Redis - ERROR only
    logging.getLogger("redis").setLevel(error_level)
    logging.getLogger("redis.client").setLevel(error_level)
    
    # Pytube - ERROR only (suppress "Unexpected renderer", "Processing query", etc.)
    logging.getLogger("pytube").setLevel(error_level)
    logging.getLogger("pytube.request").setLevel(error_level)
    logging.getLogger("pytube.streams").setLevel(error_level)
    
    # spotDL - ERROR only (suppress download progress, search terms)
    logging.getLogger("spotdl").setLevel(error_level)
    logging.getLogger("app.utils.spotdl").setLevel(error_level)
    
    # yt-dlp - ERROR only
    logging.getLogger("yt_dlp").setLevel(error_level)
    
    # HTTP libraries - ERROR only
    logging.getLogger("urllib3").setLevel(error_level)
    logging.getLogger("requests").setLevel(error_level)
    logging.getLogger("httpcore").setLevel(error_level)
    
    # Other common libraries - ERROR only
    logging.getLogger("asyncio").setLevel(error_level)
    logging.getLogger("multipart").setLevel(error_level)


def configure_logging():
    """Configure structured logging with environment-aware settings - ERROR only in production"""

    # Determine log level (default to ERROR in production)
    if settings.environment == "production" and not os.getenv("LOG_LEVEL"):
        # Force ERROR in production unless explicitly set
        log_level = logging.ERROR
    else:
        log_level = getattr(logging, settings.log_level.upper(), logging.ERROR)

    # Configure root logger
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Configure third-party loggers
    configure_third_party_loggers(log_level)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Get a logger instance"""
    return structlog.get_logger(name)


def get_debug_log_path() -> str:
    """
    Get the path to the debug log file.
    Works in both local development and Docker environments.
    
    Returns:
        Path to .cursor/debug.log relative to workspace root
    """
    import os
    from pathlib import Path
    
    # Try to find workspace root by looking for known files
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        # Check for project markers
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists() or (parent / "run.py").exists():
            debug_log = parent / ".cursor" / "debug.log"
            # Create .cursor directory if it doesn't exist
            debug_log.parent.mkdir(exist_ok=True)
            return str(debug_log)
    
    # Fallback: use current directory
    debug_log = Path(".cursor") / "debug.log"
    debug_log.parent.mkdir(exist_ok=True)
    return str(debug_log)


def sanitize_cookie_path(path: Optional[str]) -> str:
    """
    Sanitize cookie file paths for logging to avoid exposing sensitive information.
    
    Args:
        path: Cookie file path (can be None)
        
    Returns:
        Sanitized path safe for logging (e.g., "/secrets/youtube-cookies.txt" -> "[COOKIES_FILE]")
    """
    if not path:
        return "[NO_COOKIES]"
    
    # Check if path contains cookie-related keywords
    path_lower = path.lower()
    if any(keyword in path_lower for keyword in ["cookie", "youtube-cookies", "cookies.txt"]):
        # Extract just the filename or a safe identifier
        from pathlib import Path
        try:
            path_obj = Path(path)
            filename = path_obj.name
            # Return a generic identifier instead of full path
            if "youtube" in filename.lower() or "cookie" in filename.lower():
                return "[COOKIES_FILE]"
            else:
                return f"[COOKIES_FILE:{filename}]"
        except Exception:
            return "[COOKIES_FILE]"
    
    return path


def sanitize_cookie_content(content: str, max_length: int = 100) -> str:
    """
    Sanitize cookie content for logging to avoid exposing sensitive tokens.
    
    Args:
        content: Content that may contain cookies
        max_length: Maximum length to show before truncating
        
    Returns:
        Sanitized content with cookies masked
    """
    if not content:
        return content
    
    # Mask common cookie patterns
    import re
    
    # Mask cookie values (format: name=value)
    content = re.sub(r'([a-zA-Z0-9_-]+)=([a-zA-Z0-9_\-\.]+)', r'\1=[REDACTED]', content)
    
    # Mask long tokens (likely session tokens)
    content = re.sub(r'[a-zA-Z0-9]{32,}', '[TOKEN_REDACTED]', content)
    
    # Truncate if too long
    if len(content) > max_length:
        content = content[:max_length] + "... [TRUNCATED]"
    
    return content


def log_pentaract_config(logger: Any, config: Any) -> None:
    """
    Log Pentaract configuration safely without exposing credentials.
    
    Args:
        logger: Logger instance
        config: Settings object with Pentaract configuration
    """
    if not config.pentaract_enabled:
        logger.info("pentaract_config_loaded", enabled=False)
        return
    
    # Log configuration without sensitive data
    logger.info(
        "pentaract_config_loaded",
        enabled=config.pentaract_enabled,
        api_url=config.pentaract_api_url,
        email=config.pentaract_email if config.pentaract_email else "[NOT_SET]",
        password="[REDACTED]" if config.pentaract_password else "[NOT_SET]",
        upload_threshold_mb=config.pentaract_upload_threshold,
        auto_cleanup=config.pentaract_auto_cleanup,
        cleanup_interval_minutes=config.pentaract_cleanup_interval,
        max_concurrent_uploads=config.pentaract_max_concurrent_uploads,
        timeout_seconds=config.pentaract_timeout,
        retry_attempts=config.pentaract_retry_attempts,
    )


# Configure logging on import
configure_logging()
