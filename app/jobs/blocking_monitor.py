"""Blocking monitor job for periodic success rate checks"""

from app.database import database
from app.services.blocking_stats_service import BlockingStatsService
from app.services.blocking_alert_service import blocking_alert_service
from app.bot import bot_service
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlockingMonitor:
    """Monitor blocking statistics and send alerts"""

    async def check_success_rates(self):
        """Check success rates for all domains and alert if needed"""
        try:
            logger.debug("🔍 Checking domain success rates...")

            with database.get_session() as session:
                stats_service = BlockingStatsService(session)

                # Get domains with low success rate (below 50%)
                low_success_domains = stats_service.get_domains_with_low_success_rate(
                    threshold=50.0
                )

                if not low_success_domains:
                    logger.debug("✅ All domains have acceptable success rates")
                    return

                logger.info(f"⚠️ Found {len(low_success_domains)} domain(s) with low success rates")

                # Send alerts for each low success rate domain
                admin_chat_id = settings.allowed_user_id
                if bot_service.bot and admin_chat_id:
                    for stats in low_success_domains:
                        success_rate = (
                            (stats.successful_requests / stats.total_requests * 100)
                            if stats.total_requests > 0
                            else 0.0
                        )

                        await blocking_alert_service.check_and_alert_low_success_rate(
                            domain=stats.domain,
                            success_rate=success_rate,
                            total_requests=stats.total_requests,
                            bot_service=bot_service,
                            admin_chat_id=admin_chat_id,
                        )

        except Exception as e:
            logger.error(f"❌ Failed to check success rates: {e}", exc_info=True)

    async def cleanup_old_stats(self):
        """Clean up old statistics (older than 7 days)"""
        try:
            logger.debug("🧹 Cleaning up old blocking statistics...")

            with database.get_session() as session:
                stats_service = BlockingStatsService(session)
                reset_count = stats_service.reset_old_stats(days=7)

                if reset_count > 0:
                    logger.info(f"🧹 Reset {reset_count} old blocking statistics")
                else:
                    logger.debug("✅ No old statistics to clean up")

        except Exception as e:
            logger.error(f"❌ Failed to cleanup old stats: {e}", exc_info=True)


# Global blocking monitor instance
blocking_monitor = BlockingMonitor()


async def check_blocking_stats_job():
    """APScheduler job function to check blocking statistics"""
    logger.debug("🔄 Blocking monitor job started")
    await blocking_monitor.check_success_rates()
    logger.debug("✅ Blocking monitor job completed")


async def cleanup_blocking_stats_job():
    """APScheduler job function to cleanup old blocking statistics"""
    logger.debug("🔄 Blocking stats cleanup job started")
    await blocking_monitor.cleanup_old_stats()
    logger.debug("✅ Blocking stats cleanup job completed")
