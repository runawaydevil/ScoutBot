"""Feed checker job using APScheduler"""

from datetime import datetime
from typing import Dict, Any, Optional

from app.models.feed import Feed
from app.services.rss_service import rss_service
from app.services.feed_service import feed_service
from app.bot import bot_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FeedChecker:
    """Feed checker that processes feeds and sends notifications"""

    def _should_check_feed(self, feed: Feed) -> bool:
        """Check if feed should be checked based on interval"""
        if not feed.last_check:
            return True

        time_since_last_check = (datetime.utcnow() - feed.last_check).total_seconds() / 60
        return time_since_last_check >= feed.check_interval_minutes

    def _log_summary(self, stats: dict):
        """Log summary of check cycle"""
        if stats["errors"] > 0:
            summary_parts = [
                f"Feed check: {stats['checked']} checked, {stats['notifications']} notifications, {stats['errors']} error(s)"
            ]
            logger.warning(" | ".join(summary_parts))
            if stats["error_feeds"]:
                logger.warning(f"Failed feeds: {', '.join(stats['error_feeds'])}")

    async def check_feed(self, feed: Feed) -> Dict[str, Any]:
        """Check a single feed for new items"""
        try:
            # Get last item ID and date
            last_item_id = feed.last_item_id
            # Use last_notified_at if available, otherwise use last_seen_at
            last_item_date = feed.last_notified_at
            if not last_item_date:
                last_item_date = feed.last_seen_at

            # Get new items from RSS service
            result = await rss_service.get_new_items(
                feed.rss_url or feed.url,
                last_item_id=last_item_id,
                last_item_date=last_item_date,
            )

            new_items = result.get("items", [])
            total_items_count = result.get("totalItemsCount", 0)
            first_item_id = result.get("firstItemId")

            # Determine new last item ID
            new_last_item_id: Optional[str] = None
            last_notified = None

            if result.get("lastItemIdToSave"):
                # First time processing
                new_last_item_id = result["lastItemIdToSave"]

                # Use feed.created_at as baseline to ensure we notify posts created AFTER the feed was added
                # This is critical: if a user adds a feed and then immediately posts, that post should be notified
                if feed.created_at:
                    last_notified = feed.created_at
                else:
                    # Fallback to current time if created_at is not set (shouldn't happen)
                    last_notified = datetime.utcnow()
            elif new_items:
                # Has new items - use the most recent new item (already sorted by date descending)
                most_recent_item = new_items[0]
                new_last_item_id = most_recent_item.id

                # Update last_notified_at with the most recent item's date
                # This ensures we only notify posts created after this point
                if most_recent_item.pub_date:
                    last_notified = most_recent_item.pub_date
                else:
                    # Fallback: use current time if item has no date (shouldn't happen)
                    logger.warning(
                        f"⚠️ New item {new_last_item_id} has no pub_date - using current time as lastNotifiedAt"
                    )
                    last_notified = datetime.utcnow()
            elif first_item_id:
                # No new items but feed has items - update to current first item
                new_last_item_id = first_item_id
            else:
                # Feed is empty or firstItemId is undefined - keep existing lastItemId
                new_last_item_id = last_item_id

            await feed_service.update_feed_last_check(
                feed.id,
                last_item_id=new_last_item_id,
                last_notified_at=last_notified,
            )

            # Send notifications for new items
            notifications_sent = 0
            if new_items:
                for item in new_items:
                    # Check max age
                    if feed.max_age_minutes:
                        if item.pub_date:
                            age_minutes = (datetime.utcnow() - item.pub_date).total_seconds() / 60
                            if age_minutes > feed.max_age_minutes:
                                continue

                    # Send notification
                    message_sent = False
                    try:
                        # Try with HTML first
                        message = self._format_message(item, feed.name, use_html=True)
                        result = await bot_service.send_message(
                            chat_id=int(feed.chat_id),
                            text=message,
                            parse_mode="HTML",
                        )

                        # Check if message was actually sent (result is not None)
                        if result is not None:
                            notifications_sent += 1
                            message_sent = True
                        else:
                            # send_message returned None, meaning it failed
                            logger.warning(
                                f"⚠️ Message to {feed.name} returned None (failed silently), trying fallback..."
                            )
                            raise Exception("Message returned None")

                    except Exception as e:
                        # If HTML fails, try plain text fallback
                        logger.warning(
                            f"⚠️ Failed to send HTML message for {feed.name}: {e}. Trying plain text fallback..."
                        )
                        try:
                            message = self._format_message(item, feed.name, use_html=False)
                            result = await bot_service.send_message(
                                chat_id=int(feed.chat_id),
                                text=message,
                                parse_mode=None,  # Plain text
                            )

                            if result is not None:
                                notifications_sent += 1
                                message_sent = True
                                logger.info(
                                    f"✅ Notification sent (plain text) for {feed.name}: {item.title}"
                                )
                            else:
                                logger.error(
                                    f"❌ Failed to send plain text message for {feed.name}: message returned None"
                                )
                        except Exception as e2:
                            logger.error(
                                f"❌ Failed to send notification (both HTML and plain text) for {feed.name}: {e2}"
                            )

                    if not message_sent:
                        logger.error(
                            f"❌ Notification NOT sent for {feed.name}: {item.title} (failed after all retries)"
                        )

            return {
                "success": True,
                "new_items_count": len(new_items),
                "notifications_sent": notifications_sent,
                "total_items_count": total_items_count,
            }

        except Exception as e:
            logger.error(f"❌ Failed to check feed {feed.name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def _format_message(self, item, feed_name: str, use_html: bool = True) -> str:
        """Format RSS item as Telegram message"""
        from app.utils.html_sanitizer import sanitize_html_for_telegram, strip_html_tags

        title = item.title or "No title"
        link = item.link or ""
        description = item.description or ""
        pub_date = ""

        if item.pub_date:
            pub_date = item.pub_date.strftime("%Y-%m-%d %H:%M:%S UTC")

        if use_html:
            # Sanitize HTML for Telegram
            title = sanitize_html_for_telegram(title)
            description = sanitize_html_for_telegram(description) if description else ""

            message = f"📰 <b>{sanitize_html_for_telegram(feed_name)}</b>\n\n"
            message += f"<b>{title}</b>\n\n"

            if description:
                # Limit description length
                max_desc_length = 500
                if len(description) > max_desc_length:
                    description = description[:max_desc_length] + "..."
                message += f"{description}\n\n"

            if pub_date:
                message += f"🕐 {pub_date}\n\n"

            if link:
                # Sanitize link URL
                sanitized_link = sanitize_html_for_telegram(link)
                message += f"🔗 <a href='{sanitized_link}'>Read more</a>"
        else:
            # Plain text fallback
            title = strip_html_tags(title)
            description = strip_html_tags(description) if description else ""
            feed_name = strip_html_tags(feed_name)

            message = f"📰 {feed_name}\n\n"
            message += f"{title}\n\n"

            if description:
                max_desc_length = 500
                if len(description) > max_desc_length:
                    description = description[:max_desc_length] + "..."
                message += f"{description}\n\n"

            if pub_date:
                message += f"🕐 {pub_date}\n\n"

            if link:
                message += f"🔗 {link}"

        return message

    async def check_all_feeds(self):
        """Check all enabled feeds with smart logging and bounded concurrency"""
        try:
            import asyncio
            feeds = await feed_service.get_all_enabled_feeds()

            if not feeds:
                return

            # Track statistics
            stats = {
                "total": len(feeds),
                "checked": 0,
                "skipped": 0,
                "errors": 0,
                "notifications": 0,
                "error_feeds": [],
            }

            # Filter feeds that should be checked
            feeds_to_check = [f for f in feeds if self._should_check_feed(f)]
            
            if not feeds_to_check:
                return

            # Process feeds with bounded concurrency (max 5 concurrent) and timeout
            semaphore = asyncio.Semaphore(5)  # Max 5 concurrent feed checks
            
            async def check_feed_with_semaphore(feed):
                """Check a single feed with semaphore and timeout"""
                async with semaphore:
                    try:
                        # Add timeout to feed check (30 seconds)
                        result = await asyncio.wait_for(
                            self.check_feed(feed),
                            timeout=30.0
                        )
                        return feed, result
                    except asyncio.TimeoutError:
                        logger.error(f"❌ Timeout checking feed {feed.name} (30s)")
                        return feed, {"success": False, "error": "Timeout after 30 seconds"}
                    except Exception as e:
                        logger.error(f"❌ Error checking feed {feed.name}: {e}")
                        return feed, {"success": False, "error": str(e)}

            # Process feeds in batches with bounded concurrency
            tasks = [check_feed_with_semaphore(feed) for feed in feeds_to_check]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, Exception):
                    stats["errors"] += 1
                    logger.error(f"❌ Exception in feed check: {result}")
                    continue
                
                feed, check_result = result
                stats["checked"] += 1
                
                if not check_result.get("success"):
                    stats["errors"] += 1
                    stats["error_feeds"].append(feed.name)
                    logger.error(f"❌ Failed to check {feed.name}: {check_result.get('error')}")
                else:
                    notifications = check_result.get("notifications_sent", 0)
                    stats["notifications"] += notifications

            # Log summary
            self._log_summary(stats)

        except Exception as e:
            logger.error(f"❌ Failed to check all feeds: {e}", exc_info=True)


# Global feed checker instance
feed_checker = FeedChecker()


async def check_feeds_job():
    """Check all feeds for new items - check bot state first"""
    # Check if bot is stopped
    from app.services.bot_state_service import bot_state_service
    is_stopped = await bot_state_service.is_stopped()
    if is_stopped:
        return
    await feed_checker.check_all_feeds()
