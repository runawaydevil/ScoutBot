"""Substack feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class SubstackService:
    """Service for fetching Substack feeds"""

    def __init__(self):
        pass

    def is_substack_url(self, url: str) -> bool:
        """Check if URL is a Substack URL"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return "substack.com" in netloc
        except Exception:
            return False

    def convert_to_feed_url(self, url: str) -> Optional[str]:
        """Convert Substack URL to RSS feed URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # Substack feed format: substack.com/@username -> substack.com/feed/@username
            # Or: substack.com/@username/p/... -> substack.com/feed/@username
            if path.startswith("@") or "/@" in path:
                # Extract username
                if path.startswith("@"):
                    username = path.split("/")[0]
                else:
                    # Find @ in path and get the next segment
                    path_parts = path.split("/")
                    try:
                        at_index = path_parts.index("@")
                        if at_index + 1 < len(path_parts):
                            username = f"@{path_parts[at_index + 1]}"
                        else:
                            username = None
                    except ValueError:
                        username = None

                if username:
                    return f"https://{parsed.netloc}/feed/{username}"

            # If already a feed URL, return as is
            if "/feed/" in path:
                return url

            # Try adding /feed to the path
            if path:
                return f"https://{parsed.netloc}/feed/{path}"

            return None
        except Exception as e:
            logger.debug(f"Error converting Substack URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch Substack feed
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
                    "error": f"Could not convert Substack URL to feed: {url}",
                }

            logger.debug(f"Converting Substack URL to feed: {url} -> {feed_url}")
            return await rss_service.fetch_feed(feed_url)

        except Exception as e:
            logger.error(f"Error fetching Substack feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
substack_service = SubstackService()
