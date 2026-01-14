"""Structured logging setup using structlog"""

import logging
import sys
from typing import Any, Optional

import structlog

from app.config import settings


def configure_third_party_loggers(log_level: int):
    """Configure third-party library loggers to reduce verbosity"""

    # Uvicorn access logs - suppress in production unless error
    if settings.environment == "production" and log_level > logging.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    else:
        logging.getLogger("uvicorn.access").setLevel(log_level)

    # Uvicorn error logs
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    # APScheduler - reduce verbosity
    if log_level > logging.DEBUG:
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
    else:
        logging.getLogger("apscheduler").setLevel(log_level)

    # Aiohttp - reduce verbosity
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    # Feedparser - reduce verbosity
    logging.getLogger("feedparser").setLevel(logging.WARNING)
    
    # SQLAlchemy - reduce verbosity in production
    if settings.environment == "production" and log_level > logging.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    
    # Redis - reduce verbosity
    logging.getLogger("redis").setLevel(logging.WARNING)


def configure_logging():
    """Configure structured logging with environment-aware settings"""

    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

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


# Configure logging on import
configure_logging()
