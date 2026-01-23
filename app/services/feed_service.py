"""Feed service for managing feeds"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4
from sqlmodel import select

from app.database import database
from app.models.feed import Feed, Chat
from app.services.rss_service import rss_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FeedService:
    """Service for managing feeds"""

    async def list_feeds(self, chat_id: str) -> List[Feed]:
        """List all feeds for a chat"""
        with database.get_session() as session:
            statement = select(Feed).where(Feed.chat_id == chat_id)
            feeds = session.exec(statement).all()
            return list(feeds)

    async def get_feed(self, chat_id: str, name: str) -> Optional[Feed]:
        """Get a specific feed"""
        with database.get_session() as session:
            statement = select(Feed).where(Feed.chat_id == chat_id, Feed.name == name)
            return session.exec(statement).first()

    async def add_feed(self, chat_id: str, name: str, url: str) -> Dict[str, Any]:
        """Add a new feed"""
        try:
            feed_url = url

            # Convert YouTube URLs to RSS format BEFORE validation
            from app.services.youtube_service import youtube_service

            if youtube_service.is_youtube_url(url):
                rss_url = youtube_service.convert_to_rss_url(url)
                if rss_url:
                    feed_url = rss_url
                    logger.info(f"Converting YouTube URL to RSS: {url} -> {feed_url}")
                else:
                    return {
                        "success": False,
                        "error": "Could not convert YouTube URL to RSS feed",
                    }

            # Convert Reddit URLs to RSS format BEFORE validation
            if feed_url == url:  # Only check Reddit if not already converted
                from app.services.reddit_service import reddit_service

                if reddit_service.is_reddit_url(url):
                    # Convert to RSS URL if not already in RSS format
                    if not url.endswith(".rss") and not url.endswith(".xml"):
                        if "/r/" in url:
                            subreddit = url.split("/r/")[1].split("/")[0]
                            feed_url = f"https://www.reddit.com/r/{subreddit}/.rss"
                            logger.info(f"Converting Reddit URL to RSS: {url} -> {feed_url}")
                        else:
                            feed_url = f"{url}.rss"

            # Try automatic feed detection if URL doesn't look like a feed
            if not feed_url.endswith((".rss", ".xml", ".json", "/feed", "/rss", "/atom")):
                from app.services.feed_detector import feed_detector

                detected_feeds = await feed_detector.detect_from_page(feed_url)
                if detected_feeds:
                    # Use first detected feed (preferred: RSS > Atom > JSON)
                    feed_url = detected_feeds[0].url

            # Validate feed URL (use converted URL for YouTube/Reddit)
            is_valid = await rss_service.validate_feed_url(feed_url)
            if not is_valid:
                return {
                    "success": False,
                    "error": "Invalid feed URL or feed is not accessible. Try providing the direct RSS feed URL.",
                }

            with database.get_session() as session:
                # Check if feed already exists (optimized: query directly in same session)
                existing = session.exec(
                    select(Feed).where(Feed.chat_id == chat_id, Feed.name == name)
                ).first()
                if existing:
                    return {
                        "success": False,
                        "error": f"Feed '{name}' already exists",
                    }

                # Ensure chat exists
                chat = session.exec(select(Chat).where(Chat.id == chat_id)).first()
                if not chat:
                    chat = Chat(
                        id=chat_id,
                        type="private",  # Default, will be updated if needed
                        title=None,
                    )
                    session.add(chat)
                    session.commit()
                    session.refresh(chat)

                # Use the feed_url (already converted for Reddit if needed)
                rss_url = feed_url

                # Create feed
                feed = Feed(
                    id=str(uuid4()),
                    chat_id=chat_id,
                    name=name,
                    url=url,  # Keep original URL for display
                    rss_url=rss_url,  # Use converted RSS URL for fetching
                    check_interval_minutes=10,
                    max_age_minutes=1440,  # 24 hours
                    enabled=True,
                    failures=0,
                )
                session.add(feed)
                session.commit()
                session.refresh(feed)

                logger.info(f"Feed added: {chat_id}/{name}")
                return {"success": True, "feed": feed}

        except Exception as e:
            logger.error(f"Failed to add feed: {e}")
            return {"success": False, "error": str(e)}

    async def remove_feed(self, chat_id: str, name: str) -> Dict[str, Any]:
        """Remove a feed"""
        try:
            with database.get_session() as session:
                # Optimized: query directly in same session instead of calling get_feed()
                feed = session.exec(
                    select(Feed).where(Feed.chat_id == chat_id, Feed.name == name)
                ).first()
                if not feed:
                    return {"success": False, "error": "Feed not found"}

                session.delete(feed)
                session.commit()

                logger.info(f"Feed removed: {chat_id}/{name}")
                return {"success": True}

        except Exception as e:
            logger.error(f"Failed to remove feed: {e}")
            return {"success": False, "error": str(e)}

    async def enable_feed(self, chat_id: str, name: str) -> Dict[str, Any]:
        """Enable a feed"""
        try:
            with database.get_session() as session:
                # Optimized: query directly in same session instead of calling get_feed()
                feed = session.exec(
                    select(Feed).where(Feed.chat_id == chat_id, Feed.name == name)
                ).first()
                if not feed:
                    return {"success": False, "error": "Feed not found"}

                feed.enabled = True
                session.add(feed)
                session.commit()

                logger.info(f"Feed enabled: {chat_id}/{name}")
                return {"success": True}

        except Exception as e:
            logger.error(f"Failed to enable feed: {e}")
            return {"success": False, "error": str(e)}

    async def disable_feed(self, chat_id: str, name: str) -> Dict[str, Any]:
        """Disable a feed"""
        try:
            with database.get_session() as session:
                # Optimized: query directly in same session instead of calling get_feed()
                feed = session.exec(
                    select(Feed).where(Feed.chat_id == chat_id, Feed.name == name)
                ).first()
                if not feed:
                    return {"success": False, "error": "Feed not found"}

                feed.enabled = False
                session.add(feed)
                session.commit()

                logger.info(f"Feed disabled: {chat_id}/{name}")
                return {"success": True}

        except Exception as e:
            logger.error(f"Failed to disable feed: {e}")
            return {"success": False, "error": str(e)}

    async def get_all_enabled_feeds(self) -> List[Feed]:
        """Get all enabled feeds"""
        try:
            with database.get_session() as session:
                # Get enabled feeds
                statement = select(Feed).where(Feed.enabled)
                feeds = session.exec(statement).all()
                return list(feeds)
        except Exception as e:
            logger.error(f"❌ Failed to get enabled feeds from database: {e}", exc_info=True)
            return []

    async def update_feed_last_check(
        self,
        feed_id: str,
        last_item_id: Optional[str] = None,
        last_notified_at: Optional[datetime] = None,
    ):
        """Update feed's last check time and last item ID"""
        try:
            with database.get_session() as session:
                feed = session.get(Feed, feed_id)
                if feed:
                    feed.last_check = datetime.utcnow()
                    if last_item_id:
                        feed.last_item_id = last_item_id
                    if last_notified_at:
                        feed.last_notified_at = last_notified_at
                    session.add(feed)
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update feed last check: {e}")


# Global feed service instance
feed_service = FeedService()
