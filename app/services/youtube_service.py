"""YouTube service for fetching YouTube channel feeds via RSS"""

from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
import re

from app.utils.logger import get_logger

logger = get_logger(__name__)


class YouTubeService:
    """YouTube service for fetching YouTube channel feeds"""

    def __init__(self):
        pass

    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL"""
        try:
            url_clean = url.strip()

            # Handle plain channel ID (starts with UC, typically 24 chars total)
            if re.match(r"^UC[a-zA-Z0-9_-]{20,}$", url_clean):
                return True

            # Check for @handle format
            if url_clean.startswith("@"):
                return True

            # Try to parse as URL
            try:
                parsed = urlparse(url_clean)
                netloc = parsed.netloc.lower()

                # Check for youtube.com or youtu.be domains
                if "youtube.com" in netloc or "youtu.be" in netloc:
                    return True
            except Exception:
                # If parsing fails, might still be a valid format
                pass

            return False
        except Exception:
            return False

    def extract_channel_info(self, url: str) -> Dict[str, Optional[str]]:
        """
        Extract channel ID or username from URL
        Returns: {
            'channel_id': Optional[str],
            'username': Optional[str],
            'user_id': Optional[str],
            'type': str  # 'channel_id', 'username', 'user_id', or 'unknown'
        }
        """
        try:
            # Handle plain channel ID (starts with UC, typically 24 chars total)
            url_clean = url.strip()
            if re.match(r"^UC[a-zA-Z0-9_-]{20,}$", url_clean):
                return {
                    "channel_id": url_clean,
                    "username": None,
                    "user_id": None,
                    "type": "channel_id",
                }

            # Handle @handle format
            if url.strip().startswith("@"):
                username = url.strip().lstrip("@")
                return {
                    "channel_id": None,
                    "username": username,
                    "user_id": None,
                    "type": "username",
                }

            # Try to parse as URL
            parsed = None
            try:
                parsed = urlparse(url_clean)
                path = parsed.path

                # Extract channel ID from /channel/UCxxxxx
                channel_match = re.search(r"/channel/([a-zA-Z0-9_-]+)", path)
                if channel_match:
                    channel_id = channel_match.group(1)
                    # Validate it looks like a channel ID (starts with UC)
                    if channel_id.startswith("UC"):
                        return {
                            "channel_id": channel_id,
                            "username": None,
                            "user_id": None,
                            "type": "channel_id",
                        }

                # Extract @handle from /@username
                handle_match = re.search(r"/@([a-zA-Z0-9_-]+)", path)
                if handle_match:
                    return {
                        "channel_id": None,
                        "username": handle_match.group(1),
                        "user_id": None,
                        "type": "username",
                    }

                # Extract from /c/ handle (some channels use /c/ instead of /@)
                c_match = re.search(r"/c/([a-zA-Z0-9_-]+)", path)
                if c_match:
                    # /c/ is typically a custom URL, treat as username
                    return {
                        "channel_id": None,
                        "username": c_match.group(1),
                        "user_id": None,
                        "type": "username",
                    }

                # Extract user ID from /user/username
                user_match = re.search(r"/user/([a-zA-Z0-9_-]+)", path)
                if user_match:
                    return {
                        "channel_id": None,
                        "username": None,
                        "user_id": user_match.group(1),
                        "type": "user_id",
                    }
            except Exception:
                # If URL parsing fails, might be plain text format
                parsed = None

            # Try to extract from query parameters if we have a parsed URL
            if parsed:
                try:
                    query_params = parse_qs(parsed.query)
                    if "channel_id" in query_params:
                        return {
                            "channel_id": query_params["channel_id"][0],
                            "username": None,
                            "user_id": None,
                            "type": "channel_id",
                        }
                except Exception:
                    pass

            return {"channel_id": None, "username": None, "user_id": None, "type": "unknown"}
        except Exception as e:
            logger.error(f"Failed to extract channel info from {url}: {e}")
            return {"channel_id": None, "username": None, "user_id": None, "type": "unknown"}

    def convert_to_rss_url(self, url: str) -> Optional[str]:
        """
        Convert YouTube URL to RSS feed URL
        Returns RSS URL or None if conversion fails
        """
        try:
            channel_info = self.extract_channel_info(url)

            # Channel ID - direct RSS URL
            if channel_info["channel_id"]:
                channel_id = channel_info["channel_id"]
                # Validate channel ID format (should start with UC and be at least 22 chars)
                # YouTube channel IDs are typically 24 characters but can vary
                if channel_id.startswith("UC") and len(channel_id) >= 22:
                    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                    logger.info(f"Converted YouTube channel ID to RSS: {channel_id} -> {rss_url}")
                    return rss_url

            # User ID (old format)
            if channel_info["user_id"]:
                user_id = channel_info["user_id"]
                rss_url = f"https://www.youtube.com/feeds/videos.xml?user={user_id}"
                logger.info(f"Converted YouTube user ID to RSS: {user_id} -> {rss_url}")
                return rss_url

            # Username (@handle) - try to use username directly
            # Note: YouTube may require channel ID, but we try username first
            if channel_info["username"]:
                username = channel_info["username"]
                # Try user format first (for old usernames)
                rss_url = f"https://www.youtube.com/feeds/videos.xml?user={username}"
                logger.info(f"Converted YouTube username to RSS: {username} -> {rss_url}")
                # Note: This may not work for all usernames, may need to resolve to channel ID
                return rss_url

            logger.error(f"Could not convert YouTube URL to RSS: {url}")
            return None

        except Exception as e:
            logger.error(f"Failed to convert YouTube URL {url} to RSS: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch YouTube channel feed
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            original_url = url

            # Check if URL is already a YouTube RSS feed URL
            if (
                "feeds/videos.xml" in url.lower()
                or url.lower().endswith(".rss")
                or url.lower().endswith(".xml")
            ):
                logger.info(f"YouTube URL already in RSS format: {url}")
                rss_url = url
            else:
                # Convert to RSS URL
                rss_url = self.convert_to_rss_url(url)
                if not rss_url:
                    logger.error(f"Could not convert YouTube URL to RSS: {url}")
                    return {
                        "success": False,
                        "error": f"Could not convert YouTube URL to RSS: {url}",
                    }
                logger.info(f"Converting YouTube URL to RSS: {url} -> {rss_url}")

            # Import here to avoid circular dependency
            from app.services.rss_service import rss_service

            # If URL is already RSS, fetch directly to avoid recursion
            # Use _fetch_feed_from_url directly instead of fetch_feed to skip detection
            if rss_service._is_rss_url(rss_url):
                logger.info(f"Fetching YouTube RSS feed directly (already converted): {rss_url}")
                result = await rss_service._fetch_feed_from_url(rss_url)
            else:
                # Fallback to fetch_feed if for some reason URL wasn't detected as RSS
                logger.info(f"Fetching YouTube feed via RSS service: {rss_url}")
                result = await rss_service.fetch_feed(rss_url)

            if result.get("success") and result.get("feed"):
                logger.debug(f"✅ Successfully fetched YouTube feed: {original_url}")
                return result

            error_msg = result.get("error") or "Failed to fetch YouTube feed"
            logger.error(f"Failed to fetch YouTube feed {original_url}: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
            }

        except Exception as e:
            logger.error(f"Exception while fetching YouTube feed {url}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }


# Global YouTube service instance
youtube_service = YouTubeService()
