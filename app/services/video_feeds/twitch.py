"""Twitch feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class TwitchService:
    """Service for fetching Twitch feeds"""

    def __init__(self):
        pass

    def is_twitch_url(self, url: str) -> bool:
        """Check if URL is a Twitch URL"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return "twitch.tv" in netloc
        except Exception:
            return False

    def convert_to_feed_url(self, url: str) -> Optional[str]:
        """Convert Twitch URL to RSS feed URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # Twitch doesn't have native RSS, but we can use third-party services
            # For now, return None and let feed detector try to find feeds
            # In the future, could integrate with Twitch API or RSSHub
            if path:
                # Extract channel name
                channel = path.split("/")[0] if path else None
                if channel:
                    # Try RSSHub format (if available)
                    # twitch.tv/username -> rsshub.app/twitch/video/username
                    # For now, return None to let feed detector handle it
                    pass

            return None
        except Exception as e:
            logger.debug(f"Error converting Twitch URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch Twitch feed
        Note: Twitch doesn't have native RSS. This will try feed detection.
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            # Twitch doesn't have native RSS feeds
            # Try feed detection first
            from app.services.feed_detector import feed_detector

            detected_feeds = await feed_detector.detect_from_page(url)
            if detected_feeds:
                feed_url = detected_feeds[0].url
                logger.debug(f"Auto-detected Twitch feed: {url} -> {feed_url}")
                return await rss_service.fetch_feed(feed_url)

            return {
                "success": False,
                "error": "Twitch does not provide native RSS feeds. Consider using a third-party service like RSSHub.",
            }

        except Exception as e:
            logger.error(f"Error fetching Twitch feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
twitch_service = TwitchService()
