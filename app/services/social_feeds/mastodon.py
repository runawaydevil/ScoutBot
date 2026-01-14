"""Mastodon feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class MastodonService:
    """Service for fetching Mastodon feeds"""

    def __init__(self):
        pass

    def is_mastodon_url(self, url: str) -> bool:
        """Check if URL is a Mastodon URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            # Mastodon URLs typically have @username or /users/username patterns
            # We can detect by path pattern, but since Mastodon instances can be any domain,
            # we'll check for common Mastodon path patterns
            if path.startswith("@") or path.startswith("users/"):
                return True
            return False
        except Exception:
            return False

    def convert_to_feed_url(self, url: str) -> Optional[str]:
        """Convert Mastodon URL to RSS feed URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # Mastodon feed format: instance.com/@username -> instance.com/@username.rss
            # Or: instance.com/users/username -> instance.com/users/username.rss
            if path.startswith("@") or path.startswith("users/"):
                if not path.endswith(".rss"):
                    return f"https://{parsed.netloc}/{path}.rss"

            # If already a feed URL, return as is
            if path.endswith(".rss"):
                return url

            return None
        except Exception as e:
            logger.debug(f"Error converting Mastodon URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch Mastodon feed
        Mastodon has native RSS support, so we try to convert URL to RSS format
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            # First try automatic feed detection (Mastodon usually has proper link tags)
            from app.services.feed_detector import feed_detector

            detected_feeds = await feed_detector.detect_from_page(url)
            if detected_feeds:
                feed_url = detected_feeds[0].url
                logger.debug(f"Auto-detected Mastodon feed: {url} -> {feed_url}")
                return await rss_service.fetch_feed(feed_url)

            # Fallback to RSS conversion
            feed_url = self.convert_to_feed_url(url)
            if feed_url:
                logger.debug(f"Converting Mastodon URL to feed: {url} -> {feed_url}")
                return await rss_service.fetch_feed(feed_url)

            return {
                "success": False,
                "error": f"Could not find Mastodon feed for: {url}",
            }

        except Exception as e:
            logger.error(f"Error fetching Mastodon feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
mastodon_service = MastodonService()
