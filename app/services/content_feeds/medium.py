"""Medium feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse
import re

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class MediumService:
    """Service for fetching Medium feeds"""

    def __init__(self):
        pass

    def is_medium_url(self, url: str) -> bool:
        """Check if URL is a Medium URL"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return "medium.com" in netloc
        except Exception:
            return False

    def convert_to_feed_url(self, url: str) -> Optional[str]:
        """Convert Medium URL to RSS feed URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # Handle different Medium URL formats
            # medium.com/@username -> medium.com/feed/@username
            if path.startswith("@") or re.match(r"^@[\w-]+", path):
                username = path.split("/")[0]
                return f"https://medium.com/feed/{username}"

            # medium.com/username -> medium.com/feed/username
            if path and not path.startswith("/"):
                return f"https://medium.com/feed/{path}"

            # If already a feed URL, return as is
            if "/feed/" in path:
                return url

            return None
        except Exception as e:
            logger.debug(f"Error converting Medium URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch Medium feed
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
                    "error": f"Could not convert Medium URL to feed: {url}",
                }

            logger.debug(f"Converting Medium URL to feed: {url} -> {feed_url}")
            return await rss_service.fetch_feed(feed_url)

        except Exception as e:
            logger.error(f"Error fetching Medium feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
medium_service = MediumService()
