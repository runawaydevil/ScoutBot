"""Keep-alive mechanism to prevent process from exiting"""

import asyncio
import signal
import os
from typing import Optional
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)


class KeepAliveService:
    """Service to keep the process alive and monitor health"""

    def __init__(self):
        self.running = False
        self.heartbeat_interval = self._get_heartbeat_interval()
        self.keep_alive_interval = 5  # seconds
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._keep_alive_task: Optional[asyncio.Task] = None
        self.start_time = datetime.utcnow()

    def _get_heartbeat_interval(self) -> int:
        """Get heartbeat interval based on environment"""
        from app.config import settings

        # Production: 5 minutes, Development: 30 seconds
        if settings.environment == "production":
            return 300  # 5 minutes
        return 30  # 30 seconds

    def start(self):
        """Start keep-alive service"""
        if self.running:
            return

        self.running = True
        logger.debug("🔒 Starting keep-alive service...")

        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Start keep-alive task
        self._keep_alive_task = asyncio.create_task(self._keep_alive_loop())

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.debug("✅ Keep-alive service started")

    def stop(self):
        """Stop keep-alive service"""
        if not self.running:
            return

        self.running = False
        logger.info("🛑 Stopping keep-alive service...")

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._keep_alive_task:
            self._keep_alive_task.cancel()

        logger.debug("✅ Keep-alive service stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()

    async def _heartbeat_loop(self):
        """Heartbeat logging loop with reduced verbosity"""
        try:
            while self.running:
                await asyncio.sleep(self.heartbeat_interval)

                uptime = (datetime.utcnow() - self.start_time).total_seconds()
                uptime_minutes = int(uptime / 60)

                try:
                    import psutil

                    process = psutil.Process()
                    memory_info = process.memory_info()
                    memory_mb = round(memory_info.rss / 1024 / 1024)
                except ImportError:
                    try:
                        import resource

                        memory_info = resource.getrusage(resource.RUSAGE_SELF)
                        memory_mb = round(getattr(memory_info, "rss", 0) / 1024 / 1024)
                    except (ImportError, AttributeError):
                        # Fallback: use os to get minimal info (Windows doesn't have resource)
                        memory_mb = 0

                # Check for anomalies
                if memory_mb > 500:  # More than 500MB
                    logger.warning(
                        "⚠️ High memory usage detected",
                        extra={
                            "uptime_minutes": uptime_minutes,
                            "memory_mb": memory_mb,
                            "pid": os.getpid(),
                        },
                    )
                else:
                    # Normal heartbeat - DEBUG level, no duplicate console output
                    logger.debug(
                        "💓 Heartbeat",
                        extra={
                            "uptime_minutes": uptime_minutes,
                            "memory_mb": memory_mb,
                            "pid": os.getpid(),
                        },
                    )

        except asyncio.CancelledError:
            logger.debug("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")

    async def _keep_alive_loop(self):
        """Keep-alive loop to prevent event loop from emptying"""
        try:
            while self.running:
                await asyncio.sleep(self.keep_alive_interval)

                # Simple check to keep event loop active
                try:
                    import psutil

                    process = psutil.Process()
                    memory_info = process.memory_info()
                    if memory_info.rss == 0:
                        logger.error("CRITICAL: Process memory is 0 - this should never happen!")
                except Exception:
                    pass

        except asyncio.CancelledError:
            logger.debug("Keep-alive loop cancelled")
        except Exception as e:
            logger.error(f"Error in keep-alive loop: {e}")


# Global keep-alive instance
keep_alive_service = KeepAliveService()
