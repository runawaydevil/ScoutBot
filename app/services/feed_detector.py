"""Feed detector service for automatic feed discovery in HTML pages"""

from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
import asyncio
import aiohttp
from bs4 import BeautifulSoup

from app.utils.logger import get_logger
from app.utils.session_manager import session_manager
from app.utils.header_builder import header_builder
from app.utils.user_agents import user_agent_pool
from app.utils.rate_limiter import rate_limiter
from app.utils.circuit_breaker import circuit_breaker

logger = get_logger(__name__)


class DetectedFeed:
    """Represents a detected feed"""

    def __init__(self, url: str, feed_type: str, title: Optional[str] = None):
        self.url = url
        self.feed_type = feed_type  # 'rss', 'atom', 'json'
        self.title = title

    def __repr__(self):
        return f"DetectedFeed(url={self.url}, type={self.feed_type}, title={self.title})"


class FeedDetector:
    """Service for detecting feeds in HTML pages"""

    def __init__(self):
        self.timeout = 10  # seconds
        self.common_feed_paths = [
            "/feed",
            "/rss",
            "/atom.xml",
            "/feed.xml",
            "/feed.json",
            "/rss.xml",
            "/atom",
            "/feeds/all.rss",
            "/feeds/all.atom",
        ]

    async def detect_from_page(self, url: str) -> List[DetectedFeed]:
        """
        Detect feeds from an HTML page
        
        Args:
            url: URL of the page to analyze
            
        Returns:
            List of detected feeds, ordered by preference (RSS > Atom > JSON)
        """
        try:
            # Extract domain for rate limiting
            domain = urlparse(url).netloc
            if not domain:
                logger.warning(f"Invalid URL for feed detection: {url}")
                return []

            # Check circuit breaker
            if not circuit_breaker.should_allow_request(url):
                logger.debug(f"Circuit breaker open for {url}, skipping feed detection")
                return []

            # Apply rate limiting
            await rate_limiter.wait_if_needed(domain)

            # Get session and headers
            session = await session_manager.get_session(domain)
            user_agent = user_agent_pool.get_for_domain(domain)
            headers = header_builder.build_headers(url, user_agent)

            # Fetch HTML page
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                if response.status != 200:
                    logger.debug(f"Failed to fetch page for feed detection: {url} (status: {response.status})")
                    return []

                content = await response.text()
                base_url = str(response.url)

            # Parse HTML (suppress XMLParsedAsHTMLWarning for XML documents)
            from bs4 import XMLParsedAsHTMLWarning
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
                soup = BeautifulSoup(content, "html.parser")

            # Find feeds via <link rel="alternate"> tags
            detected_feeds = self._find_link_tags(soup, base_url)

            # If no feeds found via link tags, try common paths
            if not detected_feeds:
                detected_feeds = await self._try_common_paths(base_url, domain, session, headers)

            # Sort by preference: RSS > Atom > JSON
            type_priority = {"rss": 1, "atom": 2, "json": 3}
            detected_feeds.sort(key=lambda f: type_priority.get(f.feed_type, 99))

            if detected_feeds:
                logger.debug(f"Detected {len(detected_feeds)} feed(s) from {url}")
                for feed in detected_feeds:
                    logger.debug(f"  - {feed.feed_type.upper()}: {feed.url} ({feed.title or 'No title'})")

            return detected_feeds

        except asyncio.TimeoutError:
            logger.debug(f"Timeout while detecting feeds from {url}")
            return []
        except Exception as e:
            logger.debug(f"Error detecting feeds from {url}: {e}")
            return []

    def _find_link_tags(self, soup: BeautifulSoup, base_url: str) -> List[DetectedFeed]:
        """Find feeds via <link rel="alternate"> tags"""
        feeds = []

        # Find all link tags with rel="alternate"
        link_tags = soup.find_all("link", rel="alternate")

        for link in link_tags:
            feed_type = link.get("type", "").lower()
            href = link.get("href")
            title = link.get("title")

            if not href:
                continue

            # Determine feed type from MIME type
            detected_type = None
            if "application/rss+xml" in feed_type or "text/xml" in feed_type:
                detected_type = "rss"
            elif "application/atom+xml" in feed_type:
                detected_type = "atom"
            elif "application/json" in feed_type or "application/feed+json" in feed_type:
                detected_type = "json"

            if detected_type:
                # Resolve relative URLs
                feed_url = urljoin(base_url, href)
                feeds.append(DetectedFeed(url=feed_url, feed_type=detected_type, title=title))

        return feeds

    async def _try_common_paths(
        self, base_url: str, domain: str, session: aiohttp.ClientSession, headers: Dict[str, str]
    ) -> List[DetectedFeed]:
        """Try common feed paths if no link tags found"""
        feeds = []
        parsed_base = urlparse(base_url)
        base_scheme = parsed_base.scheme
        base_netloc = parsed_base.netloc

        for path in self.common_feed_paths:
            feed_url = f"{base_scheme}://{base_netloc}{path}"

            try:
                # Quick HEAD request to check if feed exists
                async with session.head(feed_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "").lower()

                        # Determine feed type from content type
                        detected_type = None
                        if "application/rss+xml" in content_type or "text/xml" in content_type or path.endswith(".rss") or path.endswith("/rss"):
                            detected_type = "rss"
                        elif "application/atom+xml" in content_type or path.endswith(".atom") or "atom" in path:
                            detected_type = "atom"
                        elif "application/json" in content_type or path.endswith(".json"):
                            detected_type = "json"

                        if detected_type:
                            feeds.append(DetectedFeed(url=feed_url, feed_type=detected_type))
                            # Stop after finding first valid feed
                            break

            except Exception:
                # Continue trying other paths
                continue

        return feeds


# Global instance
feed_detector = FeedDetector()
