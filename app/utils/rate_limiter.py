"""Rate limiter with adaptive delays"""

import asyncio
import random
import time
from typing import Dict


class RateLimiter:
    """Manages per-domain rate limiting with adaptive delays"""

    def __init__(self, min_delay: float = 5.0, max_delay: float = 300.0):
        self.domain_delays: Dict[str, float] = {}  # domain -> delay_seconds
        self.last_request_time: Dict[str, float] = {}  # domain -> timestamp
        self.failure_counts: Dict[str, int] = {}  # domain -> count
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def wait_if_needed(self, domain: str):
        """Wait if rate limit requires delay"""
        current_delay = self.domain_delays.get(domain, self.min_delay)
        last_time = self.last_request_time.get(domain, 0)

        elapsed = time.time() - last_time
        if elapsed < current_delay:
            wait_time = current_delay - elapsed
            # Add random jitter (±20%)
            jitter = wait_time * random.uniform(-0.2, 0.2)
            wait_time = max(0, wait_time + jitter)
            await asyncio.sleep(wait_time)

        self.last_request_time[domain] = time.time()

    def record_success(self, domain: str):
        """Record successful request - gradually reduce delay"""
        current_delay = self.domain_delays.get(domain, self.min_delay)
        new_delay = max(self.min_delay, current_delay * 0.9)
        self.domain_delays[domain] = new_delay
        self.failure_counts[domain] = 0

    def record_failure(self, domain: str, status_code: int):
        """Record failed request - increase delay"""
        failures = self.failure_counts.get(domain, 0) + 1
        self.failure_counts[domain] = failures

        current_delay = self.domain_delays.get(domain, self.min_delay)

        if status_code == 429:  # Too Many Requests
            new_delay = min(self.max_delay, current_delay * 2)
        elif status_code == 403 and failures >= 3:  # Blocked
            new_delay = min(self.max_delay, current_delay * 3)
        else:
            new_delay = min(self.max_delay, current_delay * 1.5)

        self.domain_delays[domain] = new_delay

    def get_current_delay(self, domain: str) -> float:
        """Get current delay for domain"""
        return self.domain_delays.get(domain, self.min_delay)


# Global instance
rate_limiter = RateLimiter()
