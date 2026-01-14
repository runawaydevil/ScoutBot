"""GitHub feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class GitHubService:
    """Service for fetching GitHub feeds"""

    def __init__(self):
        pass

    def is_github_url(self, url: str) -> bool:
        """Check if URL is a GitHub URL"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return "github.com" in netloc
        except Exception:
            return False

    def convert_to_feed_url(self, url: str, feed_type: str = "releases") -> Optional[str]:
        """
        Convert GitHub URL to RSS feed URL
        
        Args:
            url: GitHub URL (repository, user, etc.)
            feed_type: Type of feed - 'releases', 'tags', 'commits', 'activity'
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            if not path:
                return None

            # GitHub feed format: github.com/owner/repo -> github.com/owner/repo/releases.atom
            # Or: github.com/owner/repo -> github.com/owner/repo/tags.atom
            # Or: github.com/owner/repo -> github.com/owner/repo/commits.atom

            parts = path.split("/")
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1]

                # Repository-specific feeds
                if feed_type == "releases":
                    return f"https://github.com/{owner}/{repo}/releases.atom"
                elif feed_type == "tags":
                    return f"https://github.com/{owner}/{repo}/tags.atom"
                elif feed_type == "commits":
                    branch = parts[2] if len(parts) > 2 and parts[2] != "releases" and parts[2] != "tags" else "main"
                    return f"https://github.com/{owner}/{repo}/commits/{branch}.atom"
                elif feed_type == "activity":
                    return f"https://github.com/{owner}/{repo}.atom"

            # User/Organization activity feed
            elif len(parts) == 1:
                username = parts[0]
                return f"https://github.com/{username}.atom"

            return None
        except Exception as e:
            logger.debug(f"Error converting GitHub URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str, feed_type: str = "releases") -> Dict[str, Any]:
        """
        Fetch GitHub feed
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            # Try releases first (most common use case)
            feed_url = self.convert_to_feed_url(url, feed_type="releases")
            if feed_url:
                result = await rss_service.fetch_feed(feed_url)
                if result.get("success"):
                    logger.debug(f"GitHub releases feed found: {url} -> {feed_url}")
                    return result

            # Try tags
            feed_url = self.convert_to_feed_url(url, feed_type="tags")
            if feed_url:
                result = await rss_service.fetch_feed(feed_url)
                if result.get("success"):
                    logger.debug(f"GitHub tags feed found: {url} -> {feed_url}")
                    return result

            # Try activity
            feed_url = self.convert_to_feed_url(url, feed_type="activity")
            if feed_url:
                result = await rss_service.fetch_feed(feed_url)
                if result.get("success"):
                    logger.debug(f"GitHub activity feed found: {url} -> {feed_url}")
                    return result

            return {
                "success": False,
                "error": f"Could not find GitHub feed for: {url}",
            }

        except Exception as e:
            logger.error(f"Error fetching GitHub feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
github_service = GitHubService()
