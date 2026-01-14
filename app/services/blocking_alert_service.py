"""Blocking alert service for monitoring and alerting on anti-blocking events"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlockingAlertService:
    """Service for monitoring blocking events and sending alerts"""

    def __init__(self):
        # Track first 403 blocks per domain (to avoid duplicate alerts)
        self.first_block_alerted: Dict[str, datetime] = {}
        # Track consecutive blocks per domain
        self.consecutive_blocks: Dict[str, int] = {}
        # Track when we last alerted for consecutive blocks
        self.consecutive_block_alerted: Dict[str, datetime] = {}
        # Track low success rate alerts
        self.low_success_rate_alerted: Dict[str, datetime] = {}
        # Alert cooldown period (avoid spamming)
        self.alert_cooldown = timedelta(hours=1)
        # Longer cooldown for low success rate alerts (24 hours)
        self.low_success_rate_cooldown = timedelta(hours=24)

    async def check_and_alert_on_block(
        self, domain: str, status_code: int, bot_service=None, admin_chat_id: Optional[int] = None
    ):
        """
        Check if we should alert on a blocking event

        Args:
            domain: The domain that was blocked
            status_code: HTTP status code (403, 429, etc.)
            bot_service: Bot service instance for sending alerts
            admin_chat_id: Admin chat ID to send alerts to
        """
        if status_code == 403:
            await self._handle_403_block(domain, bot_service, admin_chat_id)
        elif status_code == 429:
            logger.warning(f"Rate limited (429) for domain: {domain}")

    async def _handle_403_block(
        self, domain: str, bot_service=None, admin_chat_id: Optional[int] = None
    ):
        """Handle 403 blocking event"""
        now = datetime.utcnow()

        # Track consecutive blocks
        self.consecutive_blocks[domain] = self.consecutive_blocks.get(domain, 0) + 1
        consecutive_count = self.consecutive_blocks[domain]

        # First block alert (warning log)
        if domain not in self.first_block_alerted:
            self.first_block_alerted[domain] = now
            logger.warning(f"⚠️ First 403 block detected for domain: {domain}")

            # Send Telegram alert if bot service is available
            if bot_service and admin_chat_id:
                try:
                    message = (
                        f"⚠️ <b>First Block Detected</b>\n\n"
                        f"Domain: <code>{domain}</code>\n"
                        f"Status: 403 Forbidden\n"
                        f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                        f"The anti-blocking system will attempt to adapt."
                    )
                    await bot_service.send_message(admin_chat_id, message)
                    logger.info(f"Sent first block alert to admin for domain: {domain}")
                except Exception as e:
                    logger.error(f"Failed to send first block alert: {e}")

        # Consecutive blocks alert (after 3 consecutive blocks)
        if consecutive_count >= 3:
            # Check if we should send alert (cooldown period)
            last_alerted = self.consecutive_block_alerted.get(domain)
            should_alert = last_alerted is None or (now - last_alerted) > self.alert_cooldown

            if should_alert:
                self.consecutive_block_alerted[domain] = now
                logger.error(f"🚨 {consecutive_count} consecutive 403 blocks for domain: {domain}")

                # Send Telegram alert if bot service is available
                if bot_service and admin_chat_id:
                    try:
                        message = (
                            f"🚨 <b>Multiple Blocks Detected</b>\n\n"
                            f"Domain: <code>{domain}</code>\n"
                            f"Consecutive Blocks: {consecutive_count}\n"
                            f"Status: 403 Forbidden\n"
                            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                            f"The domain may be actively blocking the bot. "
                            f"Consider manual intervention or checking /blockstats."
                        )
                        await bot_service.send_message(admin_chat_id, message)
                        logger.info(f"Sent consecutive block alert to admin for domain: {domain}")
                    except Exception as e:
                        logger.error(f"Failed to send consecutive block alert: {e}")

    def reset_consecutive_blocks(self, domain: str):
        """Reset consecutive block counter for domain (called on success)"""
        if domain in self.consecutive_blocks:
            self.consecutive_blocks[domain] = 0

    async def check_and_alert_low_success_rate(
        self,
        domain: str,
        success_rate: float,
        total_requests: int,
        bot_service=None,
        admin_chat_id: Optional[int] = None,
    ):
        """
        Check if domain has low success rate and alert if needed

        Args:
            domain: The domain to check
            success_rate: Success rate percentage (0-100)
            total_requests: Total number of requests made
            bot_service: Bot service instance for sending alerts
            admin_chat_id: Admin chat ID to send alerts to
        """
        # Only alert if we have enough data (at least 10 requests)
        if total_requests < 10:
            return

        # Check if success rate is below threshold (50%)
        if success_rate < 50.0:
            now = datetime.utcnow()

            # Check if we should send alert (cooldown period)
            # Use a longer cooldown for low success rate (24 hours instead of 1 hour)
            last_alerted = self.low_success_rate_alerted.get(domain)
            should_alert = (
                last_alerted is None or (now - last_alerted) > self.low_success_rate_cooldown
            )

            if should_alert:
                self.low_success_rate_alerted[domain] = now
                logger.warning(
                    f"⚠️ Low success rate for domain {domain}: {success_rate:.1f}% "
                    f"({total_requests} requests)"
                )

                # Send Telegram alert if bot service is available
                if bot_service and admin_chat_id:
                    try:
                        message = (
                            f"⚠️ <b>Low Success Rate Alert</b>\n\n"
                            f"Domain: <code>{domain}</code>\n"
                            f"Success Rate: {success_rate:.1f}%\n"
                            f"Total Requests: {total_requests}\n"
                            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                            f"The domain has a success rate below 50% over the last 24 hours. "
                            f"Check /blockstats for more details."
                        )
                        await bot_service.send_message(admin_chat_id, message)
                        logger.info(f"Sent low success rate alert to admin for domain: {domain}")
                    except Exception as e:
                        logger.error(f"Failed to send low success rate alert: {e}")

    async def check_circuit_breaker_state(
        self,
        domain: str,
        state: str,
        bot_service=None,
        admin_chat_id: Optional[int] = None,
    ):
        """
        Alert when circuit breaker opens for a domain

        Args:
            domain: The domain
            state: Circuit breaker state (open, half_open, closed)
            bot_service: Bot service instance for sending alerts
            admin_chat_id: Admin chat ID to send alerts to
        """
        if state == "open":
            logger.warning(f"⚡ Circuit breaker OPEN for domain: {domain}")

            # Send Telegram alert if bot service is available
            if bot_service and admin_chat_id:
                try:
                    message = (
                        f"⚡ <b>Circuit Breaker Opened</b>\n\n"
                        f"Domain: <code>{domain}</code>\n"
                        f"Status: Circuit breaker activated\n"
                        f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                        f"The domain has failed multiple times consecutively. "
                        f"Requests will be temporarily suspended."
                    )
                    await bot_service.send_message(admin_chat_id, message)
                    logger.info(f"Sent circuit breaker alert to admin for domain: {domain}")
                except Exception as e:
                    logger.error(f"Failed to send circuit breaker alert: {e}")


# Global instance
blocking_alert_service = BlockingAlertService()
