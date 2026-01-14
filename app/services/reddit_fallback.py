"""Reddit fallback chain for accessing blocked feeds"""

import base64
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RedditFallbackChain:
    """Implements fallback chain for Reddit access"""

    def __init__(self):
        self.successful_methods: Dict[str, tuple] = {}  # subreddit -> (method, timestamp)
        self.method_cache_ttl = 86400  # 24 hours
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def fetch_reddit_feed(self, subreddit: str, rss_service) -> dict:
        """Fetch Reddit feed using fallback chain"""

        # Try cached successful method first
        if subreddit in self.successful_methods:
            method, timestamp = self.successful_methods[subreddit]
            if time.time() - timestamp < self.method_cache_ttl:
                logger.debug(f"Using cached method '{method}' for r/{subreddit}")
                result = await self._try_method(method, subreddit, rss_service)
                if result["success"]:
                    return result
                else:
                    # Cached method failed, remove from cache
                    del self.successful_methods[subreddit]

        # Try all methods in order
        # If OAuth credentials are available, try OAuth first
        methods = []
        if self._has_oauth_credentials():
            methods.append(("oauth", self._fetch_oauth))
        methods.append(("rss", self._fetch_rss))
        if settings.use_reddit_json_fallback:
            methods.append(("json", self._fetch_json))
        methods.append(("old_rss", self._fetch_old_rss))

        for method_name, method_func in methods:
            logger.debug(f"Trying method '{method_name}' for r/{subreddit}")
            result = await method_func(subreddit, rss_service)
            if result["success"]:
                self.successful_methods[subreddit] = (method_name, time.time())
                logger.debug(f"✅ Reddit access successful via {method_name}: r/{subreddit}")
                return result
            else:
                logger.debug(
                    f"Method '{method_name}' failed for r/{subreddit}: {result.get('error')}"
                )

        # All methods failed
        logger.error(f"❌ All Reddit access methods failed for r/{subreddit}")
        return {"success": False, "error": "All methods failed"}

    def _has_oauth_credentials(self) -> bool:
        """Check if OAuth credentials are available"""
        return bool(
            settings.reddit_client_id
            and settings.reddit_client_secret
            and settings.reddit_username
            and settings.reddit_password
            and settings.use_reddit_api
        )

    async def _get_oauth_token(self) -> Optional[str]:
        """Get OAuth access token, refreshing if necessary"""
        # Check if token is still valid (refresh 5 minutes before expiry)
        if self._access_token and time.time() < (self._token_expires_at - 300):
            return self._access_token

        # Refresh token
        try:
            from app.utils.session_manager import session_manager

            domain = "reddit.com"
            session = await session_manager.get_session(domain)

            # Build Basic Auth header
            credentials = f"{settings.reddit_client_id}:{settings.reddit_client_secret}"
            auth_header = base64.b64encode(credentials.encode()).decode()

            # Request token
            token_url = "https://www.reddit.com/api/v1/access_token"
            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ScoutBot/1.0",
            }
            data = {
                "grant_type": "password",
                "username": settings.reddit_username,
                "password": settings.reddit_password,
            }

            async with session.post(token_url, headers=headers, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Reddit OAuth failed: {response.status} - {error_text}")
                    return None

                result = await response.json()
                self._access_token = result.get("access_token")
                expires_in = result.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in

                logger.debug(f"✅ Reddit OAuth token obtained, expires in {expires_in}s")
                return self._access_token

        except Exception as e:
            logger.error(f"Failed to get Reddit OAuth token: {e}", exc_info=True)
            return None

    async def _try_method(self, method: str, subreddit: str, rss_service) -> dict:
        """Try specific method"""
        if method == "oauth":
            return await self._fetch_oauth(subreddit, rss_service)
        elif method == "rss":
            return await self._fetch_rss(subreddit, rss_service)
        elif method == "json":
            return await self._fetch_json(subreddit, rss_service)
        elif method == "old_rss":
            return await self._fetch_old_rss(subreddit, rss_service)
        return {"success": False, "error": "Unknown method"}

    async def _fetch_oauth(self, subreddit: str, rss_service) -> dict:
        """Try OAuth API endpoint with authentication"""
        token = await self._get_oauth_token()
        if not token:
            return {"success": False, "error": "Failed to obtain OAuth token"}

        url = f"https://oauth.reddit.com/r/{subreddit}/new.json?limit=25"

        try:
            from app.utils.session_manager import session_manager

            domain = "reddit.com"
            session = await session_manager.get_session(domain)

            headers = {
                "Authorization": f"bearer {token}",
                "User-Agent": "ScoutBot/1.0",
            }

            async with session.get(url, headers=headers) as response:
                if response.status == 401:
                    # Token expired, clear it and retry
                    self._access_token = None
                    self._token_expires_at = 0
                    logger.warning("OAuth token expired, will retry with new token")
                    return {"success": False, "error": "Token expired"}

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Reddit OAuth API failed: {response.status} - {error_text}")
                    return {"success": False, "error": f"HTTP {response.status}"}

                # Parse JSON response (same structure as public JSON API)
                data = await response.json()

                if not data or "data" not in data or "children" not in data["data"]:
                    return {"success": False, "error": "Invalid JSON structure"}

                # Import here to avoid circular dependency
                from app.services.rss_service import RSSItem, RSSFeed
                
                # Convert Reddit JSON to RSS items (same logic as _fetch_json)
                items: List[RSSItem] = []
                for child in data["data"]["children"]:
                    post = child.get("data", {})
                    if not post:
                        continue

                    # Extract post data
                    post_id = post.get("id", "")
                    title = post.get("title", "")
                    link = post.get("url", "")
                    if not link.startswith("http"):
                        link = f"https://www.reddit.com{post.get('permalink', '')}"

                    # Parse date (Reddit uses Unix timestamp)
                    pub_date = None
                    created_utc = post.get("created_utc")
                    if created_utc:
                        try:
                            pub_date = datetime.utcfromtimestamp(created_utc)
                        except (ValueError, TypeError):
                            pass

                    # Get author
                    author = post.get("author", "")

                    # Get selftext as description
                    description = post.get("selftext", "")

                    # Create RSS item
                    item = RSSItem(
                        id=post_id,
                        title=title,
                        link=link,
                        description=description,
                        pub_date=pub_date,
                        author=author,
                    )
                    items.append(item)

                if not items:
                    return {"success": False, "error": "No items found in OAuth API response"}

                # Create RSS feed
                feed = RSSFeed(
                    items=items,
                    title=f"r/{subreddit}",
                    description=f"Reddit feed for r/{subreddit} (OAuth)",
                    link=f"https://www.reddit.com/r/{subreddit}",
                )

                logger.debug(f"✅ Successfully parsed {len(items)} items from Reddit OAuth API")
                return {"success": True, "feed": feed}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OAuth JSON response: {e}")
            return {"success": False, "error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"Error fetching Reddit OAuth API: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _fetch_rss(self, subreddit: str, rss_service) -> dict:
        """Try standard RSS endpoint"""
        url = f"https://www.reddit.com/r/{subreddit}/.rss"
        return await rss_service._fetch_feed_from_url(url)

    async def _fetch_json(self, subreddit: str, rss_service) -> dict:
        """Try JSON API endpoint and convert to RSS format"""
        url = f"https://www.reddit.com/r/{subreddit}.json"
        
        try:
            # Get session from session manager
            from app.utils.session_manager import session_manager
            from app.utils.user_agents import user_agent_pool
            from app.utils.header_builder import header_builder
            
            domain = "reddit.com"
            session = await session_manager.get_session(domain)
            user_agent = user_agent_pool.get_for_domain(domain)
            headers = header_builder.build_headers(url, user_agent)
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return {"success": False, "error": f"HTTP {response.status}"}
                
                # Parse JSON response
                data = await response.json()
                
                if not data or "data" not in data or "children" not in data["data"]:
                    return {"success": False, "error": "Invalid JSON structure"}
                
                # Import here to avoid circular dependency
                from app.services.rss_service import RSSItem, RSSFeed
                
                # Convert Reddit JSON to RSS items
                items: List[RSSItem] = []
                for child in data["data"]["children"]:
                    post = child.get("data", {})
                    if not post:
                        continue
                    
                    # Extract post data
                    post_id = post.get("id", "")
                    title = post.get("title", "")
                    link = post.get("url", "")
                    if not link.startswith("http"):
                        link = f"https://www.reddit.com{post.get('permalink', '')}"
                    
                    # Parse date (Reddit uses Unix timestamp)
                    pub_date = None
                    created_utc = post.get("created_utc")
                    if created_utc:
                        try:
                            pub_date = datetime.utcfromtimestamp(created_utc)
                        except (ValueError, TypeError):
                            pass
                    
                    # Get author
                    author = post.get("author", "")
                    
                    # Get selftext as description
                    description = post.get("selftext", "")
                    
                    # Create RSS item
                    item = RSSItem(
                        id=post_id,
                        title=title,
                        link=link,
                        description=description,
                        pub_date=pub_date,
                        author=author,
                    )
                    items.append(item)
                
                if not items:
                    return {"success": False, "error": "No items found in JSON response"}
                
                # Create RSS feed
                feed = RSSFeed(
                    items=items,
                    title=f"r/{subreddit}",
                    description=f"Reddit feed for r/{subreddit}",
                    link=f"https://www.reddit.com/r/{subreddit}",
                )
                
                logger.debug(f"✅ Successfully parsed {len(items)} items from Reddit JSON API")
                return {"success": True, "feed": feed}
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"success": False, "error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"Error fetching Reddit JSON: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _fetch_old_rss(self, subreddit: str, rss_service) -> dict:
        """Try old.reddit.com RSS endpoint"""
        url = f"https://old.reddit.com/r/{subreddit}/.rss"
        return await rss_service._fetch_feed_from_url(url)


# Global instance
reddit_fallback = RedditFallbackChain()
