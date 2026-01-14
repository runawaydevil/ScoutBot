"""Async wrapper for spotDL library"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from app.config import settings
from app.utils.logger import get_logger
from app.utils.spotdl import Spotdl
from app.utils.spotdl.types.song import Song
from app.utils.ytdlp_config import build_ytdlp_common_opts, ytdlp_opts_to_args_string
from app.utils.logger import sanitize_cookie_path
from app.utils.youtube_auth import YoutubeAuthProvider

logger = get_logger(__name__)

# Global instance to reuse across downloads (SpotifyClient is a singleton)
_global_wrapper: Optional["SpotdlWrapper"] = None


class SpotdlWrapper:
    """Async wrapper for spotDL operations"""

    def __init__(self):
        """Initialize the wrapper with settings from config"""
        if not settings.spotify_client_id or not settings.spotify_client_secret:
            raise ValueError("Spotify credentials not configured")

        # Parse audio providers
        audio_providers = [
            p.strip() for p in settings.spotify_audio_providers.split(",") if p.strip()
        ]
        if not audio_providers:
            audio_providers = ["youtube-music", "youtube"]

        # Parse lyrics providers
        lyrics_providers = [
            p.strip() for p in settings.spotify_lyrics_providers.split(",") if p.strip()
        ]
        if not lyrics_providers:
            lyrics_providers = ["genius", "musixmatch", "azlyrics"]

        # Build downloader settings
        # Use /tmp as output directory since /app is not writable by the app user
        import tempfile
        temp_dir = tempfile.gettempdir()
        
        # Configure cookies based on YTDLP_AUTH_MODE setting
        # This allows flexibility: use cookies on VPS (where YouTube blocks), disable on local
        cookie_file = None
        auth_mode = getattr(settings, "ytdlp_auth_mode", "none").lower()
        
        logger.info(f"YTDLP_AUTH_MODE: {auth_mode}")
        
        if auth_mode in ("cookiefile", "both"):
            # Use cookies file if configured
            cookies_path = getattr(settings, "ytdlp_cookies_file", "/secrets/youtube-cookies.txt")
            logger.info(f"Checking cookies path: {cookies_path}")
            
            if Path(cookies_path).exists():
                cookie_file = cookies_path
                # Check file size to ensure it's not empty
                file_size = Path(cookies_path).stat().st_size
                logger.info(f"Using cookies file for Spotify downloads: {sanitize_cookie_path(cookies_path)} (size: {file_size} bytes)")
                
                if file_size < 100:
                    logger.warning(f"Cookies file seems too small ({file_size} bytes), may be invalid")
            else:
                logger.warning(f"Cookies file not found: {cookies_path}, proceeding without authentication")
        else:
            logger.info("Cookies authentication disabled (auth_mode=none)")
        
        # Build yt-dlp args for spotDL
        # Use minimal configuration to avoid YouTube blocking
        yt_dlp_args = None
        if cookie_file:
            # Pass cookies and ensure Node.js is available for signature solving
            # The --exec-before-download ensures Node.js is in PATH
            yt_dlp_args = f"--cookies {cookie_file} --extractor-args youtube:player_client=web,mweb"
            logger.info(f"Configured yt-dlp with cookies for Spotify downloads: {yt_dlp_args}")
        
        downloader_settings = {
            "format": settings.spotify_audio_format,
            "bitrate": settings.spotify_bitrate,
            "audio_providers": audio_providers,
            "lyrics_providers": lyrics_providers,
            "output": str(Path(temp_dir) / "{artists} - {title}.{output-ext}"),
            "threads": 1,  # Single thread for now
            "overwrite": "skip",
            "scan_for_songs": False,
            "save_file": None,
            "m3u": None,
            "archive": None,
            "print_errors": True,
            "save_errors": None,
            "simple_tui": True,
            "log_level": "INFO",  # Reduced from DEBUG for production
            "cookie_file": cookie_file,  # Use cookies if available
            "yt_dlp_args": yt_dlp_args,  # Pass cookies to yt-dlp
            "filter_results": True,  # Filter search results to get best match
            "only_verified_results": True,  # Only use verified results for better accuracy
        }

        # Initialize spotDL without passing a loop
        # The loop will be created in each thread that uses spotDL
        self.spotdl = Spotdl(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            user_auth=False,
            no_cache=False,
            headless=True,
            downloader_settings=downloader_settings,
            loop=None,  # Let spotDL create its own loop in each thread
        )

        logger.info(
            f"SpotdlWrapper initialized with format={settings.spotify_audio_format}, "
            f"bitrate={settings.spotify_bitrate}, "
            f"audio_providers={audio_providers}, "
            f"cookie_file={'configured' if cookie_file else 'none'}, "
            f"yt_dlp_args={'configured' if yt_dlp_args else 'none'}"
        )

    async def search_songs(self, query: List[str]) -> List[Song]:
        """
        Search for songs asynchronously.

        Args:
            query: List of search queries (URLs, song names, etc.)

        Returns:
            List of Song objects
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.spotdl.search, query)

    async def download_song(self, song: Song) -> Tuple[Song, Optional[Path]]:
        """
        Download a single song asynchronously.

        Args:
            song: Song object to download

        Returns:
            Tuple of (Song, Optional[Path]) - Path is None if download failed
        """
        def _download_in_thread():
            """Download song in a thread with its own event loop"""
            import asyncio
            import sys
            # Create a new event loop for this thread
            if sys.platform == "win32":
                loop = asyncio.ProactorEventLoop()
            else:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Update the downloader's loop to use the new loop
                # This allows reusing the existing spotDL instance
                self.spotdl.downloader.loop = loop
                # Also set it as the event loop for this thread
                asyncio.set_event_loop(loop)
                # Now we can use the existing spotDL instance
                return self.spotdl.download(song)
            finally:
                # Don't close the loop here as it might be used by other operations
                # Just remove it from the thread
                asyncio.set_event_loop(None)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _download_in_thread)

    async def download_multiple_songs(
        self, songs: List[Song]
    ) -> List[Tuple[Song, Optional[Path]]]:
        """
        Download multiple songs asynchronously.

        Args:
            songs: List of Song objects to download

        Returns:
            List of tuples (Song, Optional[Path]) - Path is None if download failed
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.spotdl.download_songs, songs)

    async def get_download_urls(self, songs: List[Song]) -> List[Optional[str]]:
        """
        Get download URLs for songs without downloading.

        Args:
            songs: List of Song objects

        Returns:
            List of download URLs (or None if not found)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.spotdl.get_download_urls, songs)


def get_spotdl_wrapper() -> SpotdlWrapper:
    """
    Get or create the global SpotdlWrapper instance.
    This ensures we reuse the same instance across downloads,
    preventing "A spotify client has already been initialized" errors.
    
    Returns:
        SpotdlWrapper instance
    """
    global _global_wrapper
    if _global_wrapper is None:
        _global_wrapper = SpotdlWrapper()
        logger.debug("Created new global SpotdlWrapper instance")
    return _global_wrapper
