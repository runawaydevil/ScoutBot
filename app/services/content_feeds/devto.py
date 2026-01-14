"""Dev.to feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class DevToService:
    """Service for fetching Dev.to feeds"""

    def __init__(self):
        pass

    def is_devto_url(self, url: str) -> bool:
        """Check if URL is a Dev.to URL"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return "dev.to" in netloc
        except Exception:
            return False

    def convert_to_feed_url(self, url: str) -> Optional[str]:
        """Convert Dev.to URL to RSS feed URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # Dev.to feed format: dev.to/username -> dev.to/username/feed
            if path and not path.endswith("/feed"):
                # Remove any trailing paths (like /posts/...)
                username = path.split("/")[0]
                if username and username != "feed":
                    return f"https://{parsed.netloc}/{username}/feed"

            # If already a feed URL, return as is
            if path.endswith("/feed"):
                return url

            return None
        except Exception as e:
            logger.debug(f"Error converting Dev.to URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch Dev.to feed
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            feed_url = self.convert_to_feed_url(url)
            if not feed_url:
                return {
                    "success": False,
                    "error": f"Could not convert Dev.to URL to feed: {url}",
                }

            logger.debug(f"Converting Dev.to URL to feed: {url} -> {feed_url}")
            return await rss_service.fetch_feed(feed_url)

        except Exception as e:
            logger.error(f"Error fetching Dev.to feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
devto_service = DevToService()
