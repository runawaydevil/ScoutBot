"""GitLab feed service"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.services.rss_service import rss_service

logger = get_logger(__name__)


class GitLabService:
    """Service for fetching GitLab feeds"""

    def __init__(self):
        pass

    def is_gitlab_url(self, url: str) -> bool:
        """Check if URL is a GitLab URL"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return "gitlab.com" in netloc or "gitlab.io" in netloc or netloc.endswith(".gitlab.io")
        except Exception:
            return False

    def convert_to_feed_url(self, url: str, feed_type: str = "releases") -> Optional[str]:
        """
        Convert GitLab URL to RSS feed URL
        
        Args:
            url: GitLab URL (repository, group, etc.)
            feed_type: Type of feed - 'releases', 'tags', 'commits'
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            if not path:
                return None

            # GitLab feed format: gitlab.com/owner/repo -> gitlab.com/owner/repo/-/releases.atom
            # Or: gitlab.com/owner/repo -> gitlab.com/owner/repo/-/tags.atom
            # Or: gitlab.com/owner/repo -> gitlab.com/owner/repo/-/commits.atom

            parts = path.split("/")
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1]

                if feed_type == "releases":
                    return f"https://{parsed.netloc}/{owner}/{repo}/-/releases.atom"
                elif feed_type == "tags":
                    return f"https://{parsed.netloc}/{owner}/{repo}/-/tags.atom"
                elif feed_type == "commits":
                    branch = parts[2] if len(parts) > 2 and parts[2] not in ["releases", "tags", "-"] else "main"
                    return f"https://{parsed.netloc}/{owner}/{repo}/-/commits/{branch}.atom"

            return None
        except Exception as e:
            logger.debug(f"Error converting GitLab URL {url}: {e}")
            return None

    async def fetch_feed(self, url: str, feed_type: str = "releases") -> Dict[str, Any]:
        """
        Fetch GitLab feed
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        try:
            # Try releases first
            feed_url = self.convert_to_feed_url(url, feed_type="releases")
            if feed_url:
                result = await rss_service.fetch_feed(feed_url)
                if result.get("success"):
                    logger.debug(f"GitLab releases feed found: {url} -> {feed_url}")
                    return result

            # Try tags
            feed_url = self.convert_to_feed_url(url, feed_type="tags")
            if feed_url:
                result = await rss_service.fetch_feed(feed_url)
                if result.get("success"):
                    logger.debug(f"GitLab tags feed found: {url} -> {feed_url}")
                    return result

            return {
                "success": False,
                "error": f"Could not find GitLab feed for: {url}",
            }

        except Exception as e:
            logger.error(f"Error fetching GitLab feed for {url}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
gitlab_service = GitLabService()
