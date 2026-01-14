"""Unified yt-dlp configuration builder"""

from typing import Dict, Any, Optional
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger
from app.utils.youtube_auth import YoutubeAuthProvider

logger = get_logger(__name__)


def build_ytdlp_common_opts(tempdir: Optional[Path] = None, disable_cookies: bool = False) -> Dict[str, Any]:
    """
    Build common yt-dlp options with unified configuration.

    This function creates a consistent set of yt-dlp options that can be used
    by both YouTube downloader and spotDL (via yt_dlp_args).

    Args:
        tempdir: Temporary directory path (for cookies file if needed)
        disable_cookies: If True, skip cookie authentication (useful for spotDL)

    Returns:
        Dictionary with yt-dlp options ready to use
    """
    # Get sleep intervals from settings
    sleep_interval = getattr(settings, "ytdlp_sleep_interval", 6)
    max_sleep_interval = getattr(settings, "ytdlp_max_sleep_interval", 10)
    retries = getattr(settings, "ytdlp_retries", 5)

    # Build base options
    opts: Dict[str, Any] = {
        "retries": retries,
        "fragment_retries": retries,
        "extractor_retries": 3,
        "sleep_interval": sleep_interval,
        "max_sleep_interval": max_sleep_interval,
        "skip_unavailable_fragments": True,
        "ignoreerrors": False,
    }

    # Add rate limiting (from existing settings)
    if hasattr(settings, "youtube_limit_rate") and settings.youtube_limit_rate:
        opts["limit_rate"] = settings.youtube_limit_rate

    # Add concurrent fragments (lower = less aggressive, better for VPS)
    if hasattr(settings, "youtube_concurrent_fragments"):
        opts["concurrent_fragments"] = settings.youtube_concurrent_fragments
    else:
        opts["concurrent_fragments"] = 1  # Conservative default for VPS

    # Add user agent if specified
    if hasattr(settings, "youtube_user_agent") and settings.youtube_user_agent:
        opts["user_agent"] = settings.youtube_user_agent

    # Add realistic HTTP headers
    opts["http_headers"] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.youtube.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # Add authentication (cookies, browser, PO Token)
    # Skip if disable_cookies is True (used by spotDL)
    if not disable_cookies:
        auth_provider = YoutubeAuthProvider()
        auth_opts = auth_provider.build_auth_opts(
            tempdir=str(tempdir) if tempdir else None
        )
        if auth_opts:
            # Handle extractor_args merge separately
            auth_extractor_args = auth_opts.pop("extractor_args", None)
            
            # Update other options first
            opts.update(auth_opts)
            
            # Merge extractor_args if both exist
            if auth_extractor_args:
                if "extractor_args" not in opts:
                    opts["extractor_args"] = {}
                # Merge each extractor's params
                for extractor, params in auth_extractor_args.items():
                    if extractor not in opts["extractor_args"]:
                        opts["extractor_args"][extractor] = {}
                    if isinstance(params, dict):
                        opts["extractor_args"][extractor].update(params)

    # Add player clients if configured (merge with existing extractor_args if any)
    if hasattr(settings, "youtube_player_clients") and settings.youtube_player_clients:
        clients = [c.strip() for c in settings.youtube_player_clients.split(",") if c.strip()]
        if clients:
            # Build extractor args for player clients
            if "extractor_args" not in opts:
                opts["extractor_args"] = {}
            if "youtube" not in opts["extractor_args"]:
                opts["extractor_args"]["youtube"] = {}
            # Merge player_client with existing youtube extractor args
            if "player_client" in opts["extractor_args"]["youtube"]:
                # Merge with existing player clients
                existing = opts["extractor_args"]["youtube"]["player_client"].split(",")
                merged = list(set(existing + clients))
                opts["extractor_args"]["youtube"]["player_client"] = ",".join(merged)
            else:
                opts["extractor_args"]["youtube"]["player_client"] = ",".join(clients)
            logger.debug(f"Using YouTube player clients: {opts['extractor_args']['youtube']['player_client']}")

    # Debug log: verify extractor_args before returning (check for youtubepot-wpc)
    if "extractor_args" in opts:
        extractor_keys = list(opts["extractor_args"].keys())
        if "youtubepot-wpc" in extractor_keys:
            logger.warning(f"WARNING: youtubepot-wpc found in extractor_args! Keys: {extractor_keys}")
        else:
            logger.debug(f"extractor_args keys (no youtubepot-wpc): {extractor_keys}")

    return opts


def ytdlp_opts_to_args_string(opts: Dict[str, Any]) -> str:
    """
    Convert yt-dlp options dict to command-line arguments string.

    This is used to pass options to spotDL via yt_dlp_args.

    Args:
        opts: Dictionary with yt-dlp options

    Returns:
        String with command-line arguments
    """
    import shlex

    args = []

    # Handle simple key-value options
    simple_opts = {
        "retries": "--retries",
        "fragment_retries": "--fragment-retries",
        "extractor_retries": "--extractor-retries",
        "sleep_interval": "--sleep-interval",
        "max_sleep_interval": "--max-sleep-interval",
        "limit_rate": "--limit-rate",
        "concurrent_fragments": "--concurrent-fragments",
        "user_agent": "--user-agent",
        "cookiefile": "--cookies",
    }

    for key, flag in simple_opts.items():
        if key in opts:
            value = opts[key]
            if value is not None:
                args.append(f"{flag}")
                args.append(str(value))

    # Handle cookiesfrombrowser
    if "cookiesfrombrowser" in opts:
        browser_tuple = opts["cookiesfrombrowser"]
        if isinstance(browser_tuple, tuple):
            browser_str = ":".join(browser_tuple)
            args.append("--cookies-from-browser")
            args.append(browser_str)

    # Handle extractor_args (complex, needs special formatting)
    if "extractor_args" in opts:
        extractor_args = opts["extractor_args"]
        if isinstance(extractor_args, dict):
            for extractor, params in extractor_args.items():
                # Skip youtubepot-wpc if PO Provider is disabled
                # This is a safety check in case it somehow got into extractor_args
                if extractor == "youtubepot-wpc":
                    logger.warning("Skipping youtubepot-wpc in extractor_args (should not be included when PO Provider disabled)")
                    continue
                    
                if isinstance(params, dict):
                    # Format: extractor:key=value;key2=value2
                    param_strs = []
                    for k, v in params.items():
                        if v is not None:
                            # Handle nested dicts (e.g., youtubepot-wpc: {browser_path: ...})
                            if isinstance(v, dict):
                                # For nested dicts, format as key=value pairs
                                for nk, nv in v.items():
                                    if nv is not None:
                                        param_strs.append(f"{k}.{nk}={nv}")
                            else:
                                param_strs.append(f"{k}={v}")
                    if param_strs:
                        args.append("--extractor-args")
                        args.append(f"{extractor}:{';'.join(param_strs)}")

    return " ".join(shlex.quote(str(arg)) for arg in args)
