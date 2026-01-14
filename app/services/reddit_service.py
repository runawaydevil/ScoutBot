"""Reddit service for fetching Reddit feeds via RSS or OAuth API"""

from typing import Dict, Any
from urllib.parse import urlparse

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RedditService:
    """Reddit service for fetching Reddit feeds"""

    def __init__(self):
        self.use_reddit_api = settings.use_reddit_api
        self.use_reddit_json_fallback = settings.use_reddit_json_fallback
        self.client_id = settings.reddit_client_id
        self.client_secret = settings.reddit_client_secret
        self.username = settings.reddit_username
        self.password = settings.reddit_password

    def is_reddit_url(self, url: str) -> bool:
        """Check if URL is a Reddit URL"""
        try:
            parsed = urlparse(url)
            return "reddit.com" in parsed.netloc.lower() or "redd.it" in parsed.netloc.lower()
        except Exception:
            return False

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch Reddit feed
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            original_url = url

            # Convert to RSS URL if not already in RSS format
            if not url.endswith(".rss") and not url.endswith(".xml"):
                # Convert to RSS URL
                if "/r/" in url:
                    subreddit = url.split("/r/")[1].split("/")[0]
                    rss_url = f"https://www.reddit.com/r/{subreddit}/.rss"
                    logger.info(f"Converting Reddit URL to RSS: {url} -> {rss_url}")
                    url = rss_url
                else:
                    rss_url = f"{url}.rss"
                    logger.info(f"Converting Reddit URL to RSS: {url} -> {rss_url}")
                    url = rss_url
            else:
                logger.info(f"Reddit URL already in RSS format: {url}")

            # Import here to avoid circular dependency
            from app.services.rss_service import rss_service

            # If URL is already RSS, fetch directly to avoid recursion
            # Use _fetch_feed_from_url directly instead of fetch_feed to skip detection
            if rss_service._is_rss_url(url):
                logger.info(f"Fetching Reddit RSS feed directly (already converted): {url}")
                result = await rss_service._fetch_feed_from_url(url)
            else:
                # Fallback to fetch_feed if for some reason URL wasn't detected as RSS
                logger.info(f"Fetching Reddit feed via RSS service: {url}")
                result = await rss_service.fetch_feed(url)

            if result.get("success") and result.get("feed"):
                logger.info(f"✅ Successfully fetched Reddit feed: {original_url}")
                return result

            error_msg = result.get("error") or "Failed to fetch Reddit feed"
            logger.error(f"Failed to fetch Reddit feed {original_url}: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
            }

        except Exception as e:
            logger.error(f"Exception while fetching Reddit feed {url}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }


# Global Reddit service instance
reddit_service = RedditService()
