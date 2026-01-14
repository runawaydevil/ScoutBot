"""Circuit breaker pattern for failed feeds"""

import time
from typing import Dict


class CircuitBreaker:
    """Implements circuit breaker pattern for failed feeds"""

    STATE_CLOSED = "closed"  # Normal operation
    STATE_OPEN = "open"  # Blocking requests
    STATE_HALF_OPEN = "half_open"  # Testing recovery

    def __init__(self, failure_threshold: int = 5, initial_timeout: int = 3600):
        self.states: Dict[str, str] = {}  # feed_id -> state
        self.failure_counts: Dict[str, int] = {}  # feed_id -> count
        self.open_until: Dict[str, float] = {}  # feed_id -> timestamp
        self.failure_threshold = failure_threshold
        self.initial_timeout = initial_timeout  # 1 hour
        self.max_timeout = 86400  # 24 hours

    def should_allow_request(self, feed_id: str) -> bool:
        """Check if request should be allowed"""
        state = self.states.get(feed_id, self.STATE_CLOSED)

        if state == self.STATE_CLOSED:
            return True

        if state == self.STATE_OPEN:
            # Check if timeout expired
            if time.time() >= self.open_until.get(feed_id, 0):
                self.states[feed_id] = self.STATE_HALF_OPEN
                return True
            return False

        if state == self.STATE_HALF_OPEN:
            return True

        return False

    def record_success(self, feed_id: str):
        """Record successful request"""
        self.states[feed_id] = self.STATE_CLOSED
        self.failure_counts[feed_id] = 0
        if feed_id in self.open_until:
            del self.open_until[feed_id]

    def record_failure(self, feed_id: str):
        """Record failed request"""
        failures = self.failure_counts.get(feed_id, 0) + 1
        self.failure_counts[feed_id] = failures

        state = self.states.get(feed_id, self.STATE_CLOSED)

        if state == self.STATE_HALF_OPEN:
            # Test failed, extend timeout
            current_timeout = self.open_until.get(feed_id, time.time()) - time.time()
            if current_timeout > 0:
                new_timeout = min(self.max_timeout, current_timeout * 2)
            else:
                new_timeout = self.initial_timeout
            self.open_until[feed_id] = time.time() + new_timeout
            self.states[feed_id] = self.STATE_OPEN

        elif failures >= self.failure_threshold:
            # Activate circuit breaker
            self.states[feed_id] = self.STATE_OPEN
            self.open_until[feed_id] = time.time() + self.initial_timeout

            # Trigger alert for circuit breaker opening
            try:
                from app.services.blocking_alert_service import blocking_alert_service
                from app.bot import bot_service
                from app.config import settings
                from urllib.parse import urlparse
                import asyncio

                # Extract domain from feed_id (which is a URL)
                try:
                    parsed = urlparse(feed_id)
                    domain = parsed.netloc or parsed.path.split("/")[0]
                except Exception:
                    domain = feed_id

                # Create async task to send alert
                admin_chat_id = settings.allowed_user_id
                if bot_service.bot and admin_chat_id:
                    asyncio.create_task(
                        blocking_alert_service.check_circuit_breaker_state(
                            domain=domain,
                            state=self.STATE_OPEN,
                            bot_service=bot_service,
                            admin_chat_id=admin_chat_id,
                        )
                    )
            except Exception as e:
                # Don't let alerting failures break the circuit breaker
                from app.utils.logger import get_logger

                logger = get_logger(__name__)
                logger.error(f"Failed to send circuit breaker alert: {e}")

    def get_state(self, feed_id: str) -> str:
        """Get current state of circuit breaker"""
        return self.states.get(feed_id, self.STATE_CLOSED)

    def get_time_until_retry(self, feed_id: str) -> float:
        """Get seconds until next retry attempt"""
        if feed_id not in self.open_until:
            return 0
        remaining = self.open_until[feed_id] - time.time()
        return max(0, remaining)


# Global instance
circuit_breaker = CircuitBreaker()
