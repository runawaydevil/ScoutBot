"""Utility functions for downloads"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, quote_plus

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def sizeof_fmt(num: int, suffix: str = "B") -> str:
    """Format bytes to human readable format"""
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def timeof_fmt(seconds: float) -> str:
    """Format seconds to human readable time"""
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f"{int(period_value)}{period_name}"
    return result


def is_youtube(url: str) -> bool:
    """Check if URL is a YouTube URL"""
    try:
        if not url or not isinstance(url, str):
            return False

        parsed = urlparse(url)
        return parsed.netloc.lower() in {"youtube.com", "www.youtube.com", "youtu.be"}
    except Exception:
        return False


def is_spotify_url(url: str) -> bool:
    """Check if URL is a Spotify URL"""
    try:
        if not url or not isinstance(url, str):
            return False
        
        return bool(re.match(r'https?://(open\.spotify\.com|spotify\.com)/', url, re.I))
    except Exception:
        return False


def normalize_spotify_url(url: str) -> str:
    """
    Normalize Spotify URL by removing localized paths and query parameters.
    
    Removes:
    - Localized paths like /intl-pt/, /intl-en/, etc.
    - Query parameters like ?si=..., &si=..., etc.
    
    Args:
        url: Spotify URL to normalize
        
    Returns:
        Normalized URL in format: https://open.spotify.com/{type}/{id}
        Returns original URL if not a Spotify URL
    """
    try:
        if not url or not isinstance(url, str):
            return url
        
        # Check if it's a Spotify URL
        if not is_spotify_url(url):
            return url
        
        # Parse URL
        parsed = urlparse(url)
        
        # Remove localized paths (e.g., /intl-pt/, /intl-en/)
        path = re.sub(r'/intl-\w+/', '/', parsed.path)
        
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
        
        # Reconstruct URL without query parameters
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize Spotify URL {url}: {e}")
        return url


def detect_downloader_type(url: str) -> str:
    """Detect which downloader to use based on URL"""
    try:
        if not url or not isinstance(url, str):
            return "direct"
        
        # Spotify detection (check first before parsing)
        if is_spotify_url(url):
            return "spotify"
        
        parsed = urlparse(url)
        hostname = parsed.netloc.lower().replace("www.", "")
        
        # YouTube detection
        if hostname in {"youtube.com", "youtu.be", "m.youtube.com"}:
            return "youtube"
        
        # Instagram/Threads detection
        if "instagram.com" in hostname or "threads.net" in hostname:
            return "instagram"
        
        # Pixeldrain detection
        if "pixeldrain.com" in hostname:
            return "pixeldrain"
        
        # KrakenFiles detection
        if "krakenfiles.com" in hostname:
            return "krakenfiles"
        
        # Default to direct download
        return "direct"
    except Exception:
        return "direct"


def shorten_url(url: str, max_length: int) -> str:
    """Shorten URL if it exceeds max length"""
    if len(url) <= max_length:
        return url
    return url[: max_length - 3] + "..."


def extract_url_and_name(message_text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract URL and optional name from message text"""
    # Regular expression to match the URL
    url_pattern = r"(https?://[^\s]+)"
    # Regular expression to match the new name after '-n'
    name_pattern = r"-n\s+(.+)$"

    # Find the URL in the message_text
    url_match = re.search(url_pattern, message_text)
    url = url_match.group(0) if url_match else None

    # Find the new name in the message_text
    name_match = re.search(name_pattern, message_text)
    new_name = name_match.group(1) if name_match else None

    return url, new_name


def parse_download_command(message_text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse download command to extract URL, format type, and optional name.
    
    Args:
        message_text: The full command text (e.g., "/download mp3 https://youtube.com/...")
    
    Returns:
        Tuple of (url, format_type, name) where:
        - url: The video URL
        - format_type: "mp3" if MP3 format requested, None otherwise
        - name: Optional custom name from -n parameter
    """
    if not message_text:
        return None, None, None
    
    # Remove command prefix if present
    text = message_text.strip()
    if text.startswith("/download"):
        text = text[9:].strip()  # Remove "/download"
    
    # Check for mp3 parameter (case-insensitive)
    mp3_pattern = r"^mp3\s+(.+)"
    mp3_match = re.match(mp3_pattern, text, re.IGNORECASE)
    
    if mp3_match:
        # MP3 format requested
        remaining_text = mp3_match.group(1).strip()
        format_type = "mp3"
    else:
        # Normal video download
        remaining_text = text
        format_type = None
    
    # Extract URL from remaining text
    url_pattern = r"(https?://[^\s]+)"
    url_match = re.search(url_pattern, remaining_text)
    url = url_match.group(0) if url_match else None
    
    # Extract optional name after -n
    name_pattern = r"-n\s+(.+)$"
    name_match = re.search(name_pattern, remaining_text)
    name = name_match.group(1).strip() if name_match else None
    
    return url, format_type, name


def extract_filename_from_response(response) -> str:
    """Extract filename from HTTP response"""
    try:
        content_disposition = response.headers.get("content-disposition")
        if content_disposition:
            filename_match = re.findall(r"filename=(.+)", content_disposition)
            if filename_match:
                return filename_match[0].strip('"\'')
    except (TypeError, IndexError):
        pass

    # Fallback if Content-Disposition header is missing
    filename = response.url.rsplit("/")[-1]
    if not filename:
        filename = quote_plus(response.url)
    return filename


def get_tmpfile_path() -> Path:
    """Get temporary file path"""
    if settings.tmpfile_path:
        tmp_path = Path(settings.tmpfile_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path
    import tempfile

    return Path(tempfile.gettempdir())
