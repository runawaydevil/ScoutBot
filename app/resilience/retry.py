"""Retry logic with exponential backoff"""

from typing import Callable, Optional, Any
import asyncio
import random

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    on_retry: Optional[Callable] = None,
) -> Any:
    """
    Retry a function with exponential backoff

    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Add random jitter to delay
        on_retry: Optional callback function called on each retry
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e

            if attempt < max_retries:
                # Calculate delay with exponential backoff
                delay = min(base_delay * (2**attempt), max_delay)

                # Add jitter if enabled
                if jitter:
                    jitter_amount = delay * 0.1 * random.random()
                    delay += jitter_amount

                logger.warn(f"Retry attempt {attempt + 1}/{max_retries} after {delay:.2f}s: {e}")

                if on_retry:
                    try:
                        on_retry(attempt, delay, e)
                    except Exception:
                        pass

                await asyncio.sleep(delay)
            else:
                logger.error(f"Max retries ({max_retries}) exceeded: {e}")
                raise last_exception

    if last_exception:
        raise last_exception

    raise Exception("Unexpected error in retry logic")
