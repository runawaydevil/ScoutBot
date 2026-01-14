"""RSS service using aiohttp and feedparser"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import asyncio
import aiohttp
import feedparser
from urllib.parse import urlparse

from app.utils.logger import get_logger
from app.utils.cache import cache_service
from app.utils.user_agents import user_agent_pool
from app.utils.header_builder import header_builder
from app.utils.rate_limiter import rate_limiter
from app.utils.circuit_breaker import circuit_breaker
from app.utils.session_manager import session_manager
from app.services.reddit_fallback import reddit_fallback
from app.services.blocking_alert_service import blocking_alert_service
from app.database import database
from app.services.blocking_stats_service import BlockingStatsService
from app.config import settings

logger = get_logger(__name__)


# Import reddit_fallback here to avoid circular dependency
def get_reddit_fallback():
    """Get Reddit fallback instance"""
    from app.services.reddit_fallback import reddit_fallback

    return reddit_fallback


# Import reddit_service here to avoid circular dependency
def get_reddit_service():
    """Get Reddit service instance"""
    from app.services.reddit_service import reddit_service

    return reddit_service


# Import youtube_service here to avoid circular dependency
def get_youtube_service():
    """Get YouTube service instance"""
    from app.services.youtube_service import youtube_service

    return youtube_service


class RSSItem:
    """RSS item model"""

    def __init__(
        self,
        id: str,
        title: str,
        link: str,
        description: Optional[str] = None,
        pub_date: Optional[datetime] = None,
        author: Optional[str] = None,
        categories: Optional[List[str]] = None,
        guid: Optional[str] = None,
        **kwargs,  # Allow additional fields for cached items
    ):
        self.id = id
        self.title = title
        self.link = link
        self.description = description
        # Handle both pub_date and pubDate (for cached items)
        self.pub_date = pub_date or (
            kwargs.get("pubDate") if isinstance(kwargs.get("pubDate"), datetime) else None
        )
        self.author = author
        self.categories = categories or []
        self.guid = guid

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "description": self.description,
            "pubDate": self.pub_date.isoformat() if self.pub_date else None,
            "author": self.author,
            "categories": self.categories,
            "guid": self.guid,
        }


class RSSFeed:
    """RSS feed model"""

    def __init__(
        self,
        items: List[RSSItem],
        title: Optional[str] = None,
        description: Optional[str] = None,
        link: Optional[str] = None,
    ):
        self.items = items
        self.title = title
        self.description = description
        self.link = link


class RSSService:
    """RSS service for fetching and parsing RSS feeds"""

    def __init__(self):
        self.max_retries = 3
        self.base_delay = 1000  # milliseconds
        self.max_delay = 30000  # milliseconds
        self.timeout = 30  # seconds
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """Initialize HTTP session"""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        """Close HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            return url

    def _is_rss_url(self, url: str) -> bool:
        """
        Check if URL is already in RSS/XML format
        URLs ending with .rss, .xml, .atom, .json or containing feeds/videos.xml are considered RSS
        """
        if not url:
            return False

        url_lower = url.lower()
        # Check for common RSS/XML/Atom/JSON extensions
        if url_lower.endswith((".rss", ".xml", ".atom", ".json")):
            return True

        # Check for YouTube RSS feed pattern
        if "feeds/videos.xml" in url_lower:
            return True

        # Check for Atom feed patterns
        if "atom.xml" in url_lower or "/atom" in url_lower:
            return True

        # Check for JSON Feed patterns
        if "feed.json" in url_lower or "/feed.json" in url_lower:
            return True

        return False

    async def fetch_feed(self, url: str) -> Dict[str, Any]:
        """
        Fetch and parse an RSS feed with retry logic and caching
        Returns: {
            'success': bool,
            'feed': Optional[RSSFeed],
            'error': Optional[str]
        }
        """
        # Check if this is a Reddit URL and use fallback chain
        if "reddit.com" in url and "/r/" in url:
            # Extract subreddit name
            parts = url.split("/r/")
            if len(parts) > 1:
                subreddit = parts[1].split("/")[0].split(".")[0]
                logger.debug(f"Using Reddit fallback chain for r/{subreddit}")
                return await reddit_fallback.fetch_reddit_feed(subreddit, self)

        # If URL is already in RSS format, fetch directly without service detection
        # This prevents infinite recursion when services call this method with converted URLs
        if self._is_rss_url(url):
            logger.debug(f"📡 URL already in RSS format, fetching directly: {url}")
            return await self._fetch_feed_from_url(url)

        # Try automatic feed detection if URL looks like a regular webpage
        from app.services.feed_detector import feed_detector

        detected_feeds = await feed_detector.detect_from_page(url)
        if detected_feeds:
            # Use first detected feed (preferred: RSS > Atom > JSON)
            feed_url = detected_feeds[0].url
            logger.debug(f"🔍 Auto-detected feed from {url}: {feed_url} ({detected_feeds[0].feed_type})")
            return await self._fetch_feed_from_url(feed_url)

        # Check if this is a YouTube URL - if so, use YouTube service
        youtube_service = get_youtube_service()
        if youtube_service.is_youtube_url(url):
            logger.info(f"🔄 Detected YouTube URL (not RSS): {url}, using YouTube service")
            result = await youtube_service.fetch_feed(url)

            if result.get("success") and result.get("feed"):
                logger.info(f"✅ YouTube service provided feed for {url}")
                return result

            logger.error(f"YouTube service failed for {url}")
            return {
                "success": False,
                "error": result.get("error") or "Failed to fetch YouTube feed",
            }

        # Check if this is a Reddit URL - if so, use Reddit service
        reddit_service = get_reddit_service()
        if reddit_service.is_reddit_url(url):
            logger.info(f"🔄 Detected Reddit URL (not RSS): {url}, using Reddit service")
            result = await reddit_service.fetch_feed(url)

            if result.get("success") and result.get("feed"):
                logger.info(f"✅ Reddit service provided feed for {url}")
                return result

            logger.error(f"Reddit service failed for {url}")
            return {
                "success": False,
                "error": result.get("error") or "Failed to fetch Reddit feed",
            }

        # Check content platform services
        from app.services.content_feeds.medium import medium_service
        if medium_service.is_medium_url(url):
            logger.debug(f"🔄 Detected Medium URL: {url}")
            result = await medium_service.fetch_feed(url)
            if result.get("success"):
                return result

        from app.services.content_feeds.substack import substack_service
        if substack_service.is_substack_url(url):
            logger.debug(f"🔄 Detected Substack URL: {url}")
            result = await substack_service.fetch_feed(url)
            if result.get("success"):
                return result

        from app.services.content_feeds.devto import devto_service
        if devto_service.is_devto_url(url):
            logger.debug(f"🔄 Detected Dev.to URL: {url}")
            result = await devto_service.fetch_feed(url)
            if result.get("success"):
                return result

        from app.services.content_feeds.wordpress import wordpress_service
        if wordpress_service.is_wordpress_url(url):
            logger.debug(f"🔄 Detected WordPress URL: {url}")
            result = await wordpress_service.fetch_feed(url)
            if result.get("success"):
                return result

        # Check video platform services
        from app.services.video_feeds.vimeo import vimeo_service
        if vimeo_service.is_vimeo_url(url):
            logger.debug(f"🔄 Detected Vimeo URL: {url}")
            result = await vimeo_service.fetch_feed(url)
            if result.get("success"):
                return result

        from app.services.video_feeds.twitch import twitch_service
        if twitch_service.is_twitch_url(url):
            logger.debug(f"🔄 Detected Twitch URL: {url}")
            result = await twitch_service.fetch_feed(url)
            if result.get("success"):
                return result

        # Check code platform services
        from app.services.code_feeds.github import github_service
        if github_service.is_github_url(url):
            logger.debug(f"🔄 Detected GitHub URL: {url}")
            result = await github_service.fetch_feed(url)
            if result.get("success"):
                return result

        from app.services.code_feeds.gitlab import gitlab_service
        if gitlab_service.is_gitlab_url(url):
            logger.debug(f"🔄 Detected GitLab URL: {url}")
            result = await gitlab_service.fetch_feed(url)
            if result.get("success"):
                return result

        # Check social platform services
        from app.services.social_feeds.mastodon import mastodon_service
        if mastodon_service.is_mastodon_url(url):
            logger.debug(f"🔄 Detected Mastodon URL: {url}")
            result = await mastodon_service.fetch_feed(url)
            if result.get("success"):
                return result

        # Try to fetch from URL (fallback)
        return await self._fetch_feed_from_url(url)

    async def _fetch_feed_from_url(self, url: str) -> Dict[str, Any]:
        """Fetch feed from a specific URL"""

        # Check circuit breaker
        if not circuit_breaker.should_allow_request(url):
            time_until_retry = circuit_breaker.get_time_until_retry(url)
            logger.warning(f"Circuit breaker OPEN for {url} - retry in {time_until_retry:.0f}s")
            return {"success": False, "error": "Circuit breaker open"}

        # Check cache first
        cached_dict = await cache_service.get(f"feed:{url}")
        if cached_dict:
            # Convert cached dict back to RSSFeed
            items = []
            for item_dict in cached_dict.get("items", []):
                # Convert pubDate string back to datetime if present
                pub_date = None
                if item_dict.get("pubDate"):
                    try:
                        from dateutil import parser as date_parser

                        pub_date = date_parser.parse(item_dict["pubDate"])
                    except Exception:
                        pass
                item_dict["pub_date"] = pub_date
                items.append(RSSItem(**item_dict))

            # DEBUG: Log cache results
            logger.debug(f"🔍 Using cached feed for {url}: {len(items)} items from cache")
            if items:
                logger.debug(
                    f"🔍 Cached first item: id={items[0].id}, title={items[0].title[:50]}, pub_date={items[0].pub_date.isoformat() if items[0].pub_date else 'N/A'}"
                )
                # Cache has items - use it
                feed = RSSFeed(
                    items=items,
                    title=cached_dict.get("title"),
                    description=cached_dict.get("description"),
                    link=cached_dict.get("link"),
                )
                logger.debug(f"Using cached feed: {url}")
                return {"success": True, "feed": feed}
            else:
                # Cache returned empty - clear it and force refetch
                logger.warning(
                    f"⚠️ Cache returned empty feed for {url} - clearing cache and will refetch"
                )
                await cache_service.delete(f"feed:{url}")
                await cache_service.delete(f"feed_meta:{url}")
                # Fall through to fetch fresh data below

        if not self._session:
            await self.initialize()

        last_error: Optional[Exception] = None

        # Extract domain for rate limiting
        domain = self.extract_domain(url)

        # Apply rate limiting
        await rate_limiter.wait_if_needed(domain)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Get User-Agent from pool (domain-aware)
                user_agent = user_agent_pool.get_for_domain(domain)

                # Build headers with randomization
                headers = header_builder.build_headers(url, user_agent)

                # Add conditional headers if cached
                cached_entry = await cache_service.get(f"feed_meta:{url}")
                if cached_entry:
                    if cached_entry.get("etag"):
                        headers["If-None-Match"] = cached_entry["etag"]
                    if cached_entry.get("last_modified"):
                        headers["If-Modified-Since"] = cached_entry["last_modified"]

                # Get session from session manager (domain-aware with rotation)
                session = await session_manager.get_session(domain)
                async with session.get(url, headers=headers) as response:
                    # Check if we got a 304 Not Modified response
                    if response.status == 304:
                        # Get cached feed for 304 response
                        cached_for_304 = await cache_service.get(f"feed:{url}")
                        if cached_for_304:
                            # Convert cached dict back to RSSFeed
                            items = []
                            for item_dict in cached_for_304.get("items", []):
                                # Convert pubDate string back to datetime if present
                                pub_date = None
                                if item_dict.get("pubDate"):
                                    try:
                                        from dateutil import parser as date_parser

                                        pub_date = date_parser.parse(item_dict["pubDate"])
                                    except Exception:
                                        pass
                                item_dict["pub_date"] = pub_date
                                items.append(RSSItem(**item_dict))

                            # DEBUG: Log 304 cache results
                            logger.debug(
                                f"🔍 Received 304 Not Modified for {url}: {len(items)} items from cache"
                            )
                            if not items:
                                logger.warning(
                                    "⚠️ 304 cache returned empty feed - clearing cache and refetching"
                                )
                                await cache_service.delete(f"feed:{url}")
                                await cache_service.delete(f"feed_meta:{url}")
                                # Fall through to refetch
                            else:
                                feed = RSSFeed(
                                    items=items,
                                    title=cached_for_304.get("title"),
                                    description=cached_for_304.get("description"),
                                    link=cached_for_304.get("link"),
                                )
                                logger.debug(f"Received 304 Not Modified, using cached feed: {url}")
                                return {"success": True, "feed": feed}
                        else:
                            logger.warning(
                                f"⚠️ Received 304 but no cache found for {url} - refetching"
                            )
                            # Fall through to refetch

                    if not response.ok:
                        error_msg = f"HTTP {response.status}: {response.reason}"
                        logger.error(f"{url} - {error_msg}")
                        # Record failure with status code for rate limiting
                        rate_limiter.record_failure(domain, response.status)
                        user_agent_pool.record_failure(domain, user_agent)

                        # Record failure in database and trigger alerts
                        try:
                            with database.get_session() as session:
                                stats_service = BlockingStatsService(session)
                                stats = stats_service.record_request_failure(
                                    domain=domain,
                                    status_code=response.status,
                                    delay=rate_limiter.get_current_delay(domain),
                                    circuit_breaker_state=circuit_breaker.get_state(url),
                                )

                                # Trigger alerts
                                from app.bot import bot_service

                                admin_chat_id = settings.allowed_user_id
                                await blocking_alert_service.check_and_alert_on_block(
                                    domain=domain,
                                    status_code=response.status,
                                    bot_service=bot_service if bot_service.bot else None,
                                    admin_chat_id=admin_chat_id,
                                )

                                # Check for low success rate
                                success_rate = stats_service.get_success_rate(domain)
                                await blocking_alert_service.check_and_alert_low_success_rate(
                                    domain=domain,
                                    success_rate=success_rate,
                                    total_requests=stats.total_requests,
                                    bot_service=bot_service if bot_service.bot else None,
                                    admin_chat_id=admin_chat_id,
                                )
                        except Exception as e:
                            logger.error(f"Failed to record failure stats: {e}")

                        raise Exception(error_msg)

                    # Extract response headers for caching
                    etag = response.headers.get("ETag")
                    last_modified = response.headers.get("Last-Modified")

                    # Read content
                    content = await response.text()

                    # Parse feed
                    parsed = feedparser.parse(content)

                    if parsed.bozo:
                        error_msg = f"Feed parsing error: {parsed.bozo_exception}"
                        logger.error(f"{url} - {error_msg}")
                        raise Exception(error_msg)

                    # DEBUG: Log feed parsing results
                    logger.debug(
                        f"🔍 Feed parser result for {url}: {len(parsed.entries)} entries found"
                    )
                    if parsed.entries:
                        logger.debug(
                            f"🔍 First entry: id={parsed.entries[0].get('id', 'N/A')}, title={parsed.entries[0].get('title', 'N/A')[:50]}"
                        )

                    # Convert to RSSFeed
                    items = []
                    entries_skipped = 0
                    for entry in parsed.entries:
                        # Extract pub_date
                        pub_date = None
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                # published_parsed is a time.struct_time tuple
                                pub_date = datetime(*entry.published_parsed[:6])
                            except Exception:
                                pass
                        elif hasattr(entry, "published"):
                            try:
                                # Try to parse published string
                                from email.utils import parsedate_tz

                                parsed_date = parsedate_tz(entry.published)
                                if parsed_date:
                                    pub_date = datetime(*parsed_date[:6])
                            except Exception:
                                pass

                        # Extract ID (prioritize id, guid, then link)
                        item_id = (
                            entry.get("id")
                            or entry.get("guid")
                            or entry.get("link")
                            or entry.get("title", "")
                        )
                        if not item_id:
                            entries_skipped += 1
                            logger.warning(
                                f"⚠️ Skipping entry without ID: title={entry.get('title', 'N/A')[:50]}"
                            )
                            continue  # Skip entries without ID

                        item = RSSItem(
                            id=item_id,
                            title=entry.get("title", ""),
                            link=entry.get("link", ""),
                            description=entry.get("description") or entry.get("summary"),
                            pub_date=pub_date,
                            author=entry.get("author"),
                            categories=[
                                tag.get("term")
                                for tag in entry.get("tags", [])
                                if isinstance(tag, dict)
                            ],
                            guid=entry.get("guid"),
                        )
                        items.append(item)

                    # DEBUG: Log conversion results
                    logger.debug(
                        f"🔍 Feed conversion result for {url}: {len(items)} items created from {len(parsed.entries)} entries (skipped: {entries_skipped})"
                    )
                    if items:
                        logger.debug(
                            f"🔍 First item: id={items[0].id}, title={items[0].title[:50]}, pub_date={items[0].pub_date.isoformat() if items[0].pub_date else 'N/A'}"
                        )

                    feed = RSSFeed(
                        items=items,
                        title=parsed.feed.get("title"),
                        description=parsed.feed.get("description"),
                        link=parsed.feed.get("link"),
                    )

                    # Cache feed and metadata (convert to dict for JSON serialization)
                    # Cache even if empty to avoid refetching on 304
                    feed_dict = {
                        "items": [item.to_dict() for item in items],
                        "title": feed.title,
                        "description": feed.description,
                        "link": feed.link,
                    }
                    await cache_service.set(f"feed:{url}", feed_dict, ttl=900)  # 15 minutes (optimized)

                    if items:
                        logger.debug(f"Cached feed with {len(items)} items: {url}")
                    else:
                        logger.debug(f"Cached empty feed (to avoid 304 refetch): {url}")

                    if etag or last_modified:
                        await cache_service.set(
                            f"feed_meta:{url}",
                            {"etag": etag, "last_modified": last_modified},
                            ttl=7200,  # 2 hours (optimized)
                        )

                    # Record success for rate limiter, UA pool, and circuit breaker
                    rate_limiter.record_success(domain)
                    user_agent_pool.record_success(domain, user_agent)
                    circuit_breaker.record_success(url)

                    # Record success in database
                    try:
                        with database.get_session() as session:
                            stats_service = BlockingStatsService(session)
                            stats_service.record_request_success(
                                domain=domain,
                                user_agent=user_agent,
                                delay=rate_limiter.get_current_delay(domain),
                            )
                            # Reset consecutive blocks on success
                            blocking_alert_service.reset_consecutive_blocks(domain)
                    except Exception as e:
                        logger.error(f"Failed to record success stats: {e}")

                    return {"success": True, "feed": feed}

            except asyncio.TimeoutError:
                last_error = Exception(f"Timeout after {self.timeout}s")
                logger.warning(f"{url} - Timeout (attempt {attempt}/{self.max_retries})")
                # Record failure (timeout treated as soft failure)
                rate_limiter.record_failure(domain, 0)
                user_agent_pool.record_failure(domain, user_agent)
                circuit_breaker.record_failure(url)

                # Record timeout in database
                try:
                    with database.get_session() as session:
                        stats_service = BlockingStatsService(session)
                        stats_service.record_request_failure(
                            domain=domain,
                            status_code=0,  # 0 for timeout
                            delay=rate_limiter.get_current_delay(domain),
                            circuit_breaker_state=circuit_breaker.get_state(url),
                        )
                except Exception as db_error:
                    logger.error(f"Failed to record timeout stats: {db_error}")
            except Exception as e:
                last_error = e
                logger.warning(f"{url} - Error (attempt {attempt}/{self.max_retries}): {e}")
                # Try to extract status code from error
                status_code = getattr(e, "status", 0) if hasattr(e, "status") else 0
                rate_limiter.record_failure(domain, status_code)
                user_agent_pool.record_failure(domain, user_agent)
                circuit_breaker.record_failure(url)

                # Record failure in database (but don't trigger alerts on retries)
                try:
                    with database.get_session() as session:
                        stats_service = BlockingStatsService(session)
                        stats_service.record_request_failure(
                            domain=domain,
                            status_code=status_code,
                            delay=rate_limiter.get_current_delay(domain),
                            circuit_breaker_state=circuit_breaker.get_state(url),
                        )
                except Exception as db_error:
                    logger.error(f"Failed to record failure stats: {db_error}")

            # Exponential backoff
            if attempt < self.max_retries:
                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                await asyncio.sleep(delay / 1000)

        return {
            "success": False,
            "error": str(last_error) if last_error else "Unknown error",
        }

    async def get_new_items(
        self,
        url: str,
        last_item_id: Optional[str] = None,
        last_item_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get new items from a feed - SIMPLIFIED VERSION
        Simply checks if the first item (most recent) has a date newer than lastNotifiedAt
        Returns: {
            'items': List[RSSItem],
            'totalItemsCount': int,
            'lastItemIdToSave': Optional[str],
            'firstItemId': Optional[str],
        }
        """
        result = await self.fetch_feed(url)

        if not result.get("success") or not result.get("feed"):
            return {"items": [], "totalItemsCount": 0}

        feed = result["feed"]
        items = feed.items
        total_items_count = len(items)

        if not items:
            return {"items": [], "totalItemsCount": 0}

        first_item = items[0]
        first_item_id = first_item.id

        # If no last item ID, this is the first time processing this feed
        if not last_item_id:
            logger.info(
                f"No lastItemId for {url} - First time processing, returning empty (will not process old items)"
            )
            return {
                "items": [],
                "totalItemsCount": total_items_count,
                "lastItemIdToSave": first_item_id,
                "firstItemId": first_item_id,
            }

        # SIMPLIFIED: Check ALL items in the feed for posts newer than lastNotifiedAt
        # Reddit feeds are sorted by popularity, not by date, so we need to check all items
        if not last_item_date:
            # No last_notified_at - treat first item as new (shouldn't happen in normal flow)
            logger.warning(f"No lastNotifiedAt for {url} - treating first item as new")
            return {
                "items": [first_item],
                "totalItemsCount": total_items_count,
                "lastItemIdToSave": None,
                "firstItemId": first_item_id,
            }

        # Check ALL items for posts newer than lastNotifiedAt
        # This is necessary because Reddit feeds are sorted by popularity, not by date
        logger.debug(
            f"🔍 Checking ALL {len(items)} items for posts newer than lastNotifiedAt {last_item_date.isoformat()}"
        )

        # Log all items with their dates for debugging
        items_with_dates = [item for item in items if item.pub_date]
        items_without_dates = [item for item in items if not item.pub_date]

        if items_with_dates:
            all_dates = [item.pub_date.isoformat() for item in items_with_dates]
            all_ids = [item.id for item in items_with_dates]
            logger.debug(
                f"🔍 Items with dates ({len(items_with_dates)}): IDs={', '.join(all_ids[:5])}, Dates={', '.join(all_dates[:5])}"
            )

        if items_without_dates:
            logger.warning(
                f"⚠️ Found {len(items_without_dates)} items without dates: {', '.join([item.id for item in items_without_dates[:5]])}"
            )

        new_items = []
        for item in items:
            if item.pub_date:
                is_newer = item.pub_date > last_item_date
                logger.debug(
                    f"🔍 Checking item {item.id}: date={item.pub_date.isoformat()}, "
                    f"lastNotifiedAt={last_item_date.isoformat()}, is_newer={is_newer}"
                )
                if is_newer:
                    new_items.append(item)
                    logger.info(
                        f"✅ Found new post: {item.id} (title: {item.title[:50]}) - date {item.pub_date.isoformat()} is newer than "
                        f"lastNotifiedAt {last_item_date.isoformat()}"
                    )
            else:
                logger.debug(f"🔍 Skipping item {item.id} - no pub_date")

        # Sort new items by date (most recent first)
        if new_items:
            new_items.sort(key=lambda x: x.pub_date or datetime.min, reverse=True)
            # Format new posts list (avoid backslash in f-string)
            new_posts_str = ", ".join(
                [
                    f'{item.id} ({item.pub_date.isoformat() if item.pub_date else "no date"})'
                    for item in new_items[:5]
                ]
            )
            logger.info(
                f"✅ Found {len(new_items)} new post(s) out of {total_items_count} total items. "
                f"New posts: {new_posts_str}"
            )
            return {
                "items": new_items,
                "totalItemsCount": total_items_count,
                "lastItemIdToSave": None,
                "firstItemId": first_item_id,
            }
        else:
            # Log why no items were found with detailed comparison
            if items:
                if items_with_dates:
                    newest_date = max(item.pub_date for item in items_with_dates)
                    oldest_date = min(item.pub_date for item in items_with_dates)
                    logger.debug(
                        f"ℹ️ No new posts found. Feed date range: {oldest_date.isoformat()} to {newest_date.isoformat()}, "
                        f"lastNotifiedAt: {last_item_date.isoformat()}. "
                        f"Newest item ({newest_date.isoformat()}) {'IS newer' if newest_date > last_item_date else 'is NOT newer'} than baseline."
                    )
                    # Show detailed comparison for each item
                    logger.debug("🔍 Detailed comparison:")
                    for item in items_with_dates[:5]:
                        logger.debug(
                            f"  - {item.id}: {item.pub_date.isoformat()} vs {last_item_date.isoformat()} = "
                            f"{'✅ NEWER' if item.pub_date > last_item_date else '❌ older'}"
                        )
                else:
                    logger.warning(
                        f"⚠️ No new posts: Feed has {len(items)} items but none have dates"
                    )
            else:
                logger.warning("⚠️ No new posts: Feed is empty")

            return {
                "items": [],
                "totalItemsCount": total_items_count,
                "lastItemIdToSave": None,
                "firstItemId": first_item_id,
            }

    async def validate_feed_url(self, url: str) -> bool:
        """Validate if a URL is a valid RSS feed"""
        try:
            result = await self.fetch_feed(url)
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Failed to validate feed URL {url}: {e}")
            return False


# Global RSS service instance
rss_service = RSSService()
