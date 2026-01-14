"""Vimeo feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class VimeoService:
    """Service for fetching Vimeo feeds"""

    def __init__(self):
        pass

    def is_vimeo_url(self, url: str) -> bool:
        """Check if URL is a Vimeo URL"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return "vimeo.com" in netloc
        except Exception:
            return False

    def convert_to_feed_url(self, url: str) -> Optional[str]:
        """Convert Vimeo URL to RSS feed URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # Vimeo feed format: vimeo.com/user/username -> vimeo.com/user/username/videos/rss
            # Or: vimeo.com/channels/channelname -> vimeo.com/channels/channelname/videos/rss
            if path:
                # Check if it's already a feed URL
                if "/videos/rss" in path or path.endswith("/rss"):
                    return url

                # Add /videos/rss to the path
                return f"https://{parsed.netloc}/{path}/videos/rss"

            return None
        except Exception as e:
            logger.debug(f"Error converting Vimeo URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch Vimeo feed
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
                    "error": f"Could not convert Vimeo URL to feed: {url}",
                }

            logger.debug(f"Converting Vimeo URL to feed: {url} -> {feed_url}")
            return await rss_service.fetch_feed(feed_url)

        except Exception as e:
            logger.error(f"Error fetching Vimeo feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
vimeo_service = VimeoService()
