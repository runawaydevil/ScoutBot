"""WordPress feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service
from app.services.feed_detector import feed_detector

logger = get_logger(__name__)


class WordPressService:
    """Service for fetching WordPress feeds"""

    def __init__(self):
        pass

    def is_wordpress_url(self, url: str) -> bool:
        """Check if URL is likely a WordPress site"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()

            # Check for WordPress.com
            if "wordpress.com" in netloc:
                return True

            # Try to detect WordPress by common patterns
            # This is a heuristic - could be improved with actual detection
            # For now, we'll rely on feed detection to find WordPress feeds
            return False
        except Exception:
            return False

    def convert_to_feed_url(self, url: str) -> Optional[str]:
        """Convert WordPress URL to RSS feed URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # WordPress.com format: username.wordpress.com -> username.wordpress.com/feed/
            if "wordpress.com" in parsed.netloc.lower():
                if not path.endswith("/feed") and not path.endswith("/feed/"):
                    return f"https://{parsed.netloc}/feed/"

            # Self-hosted WordPress: usually /feed/ or /feed
            # Try common WordPress feed paths
            if not path.endswith("/feed") and not path.endswith("/feed/"):
                return f"{url.rstrip('/')}/feed/"

            return None
        except Exception as e:
            logger.debug(f"Error converting WordPress URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch WordPress feed
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            # First try automatic feed detection (WordPress sites usually have proper link tags)
            detected_feeds = await feed_detector.detect_from_page(url)
            if detected_feeds:
                feed_url = detected_feeds[0].url
                logger.debug(f"Auto-detected WordPress feed: {url} -> {feed_url}")
                return await rss_service.fetch_feed(feed_url)

            # Fallback to common feed paths
            feed_url = self.convert_to_feed_url(url)
            if feed_url:
                logger.debug(f"Converting WordPress URL to feed: {url} -> {feed_url}")
                return await rss_service.fetch_feed(feed_url)

            return {
                "success": False,
                "error": f"Could not find WordPress feed for: {url}",
            }

        except Exception as e:
            logger.error(f"Error fetching WordPress feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
wordpress_service = WordPressService()
