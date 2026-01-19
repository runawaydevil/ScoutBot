"""Resource Monitoring Service for tracking CPU and memory usage"""

import asyncio
import psutil
from typing import Optional, Dict, Any
from datetime import datetime

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResourceMonitorService:
    """Service for monitoring system resource usage"""
    
    def __init__(self):
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._current_cpu_usage: float = 0.0
        self._current_memory_usage: float = 0.0
        self._throttled: bool = False
        self._last_log_time: Optional[datetime] = None
    
    async def start(self):
        """Start the resource monitoring service"""
        if not settings.resource_monitoring_enabled:
            logger.info("Resource monitoring is disabled")
            return
        
        if self._running:
            logger.warning("Resource monitoring service is already running")
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._periodic_monitoring())
        logger.info(
            f"Resource monitoring service started "
            f"(interval: {settings.resource_monitoring_interval} minutes, "
            f"CPU threshold: {settings.resource_cpu_threshold}%, "
            f"Memory threshold: {settings.resource_memory_threshold}%)"
        )
    
    async def stop(self):
        """Stop the resource monitoring service"""
        if not self._running:
            return
        
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Resource monitoring service stopped")
    
    async def _periodic_monitoring(self):
        """Periodically monitor resource usage"""
        interval_seconds = settings.resource_monitoring_interval * 60
        
        while self._running:
            try:
                # Wait for the interval
                await asyncio.sleep(interval_seconds)
                
                # Update resource usage
                await self._update_resource_usage()
                
                # Log metrics
                await self._log_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic monitoring: {e}", exc_info=True)
    
    async def _update_resource_usage(self):
        """Update current resource usage metrics"""
        try:
            # Get CPU usage (average over 1 second)
            self._current_cpu_usage = psutil.cpu_percent(interval=1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            self._current_memory_usage = memory.percent
            
            # Check if we should throttle
            should_throttle = (
                self._current_cpu_usage > settings.resource_cpu_threshold or
                self._current_memory_usage > settings.resource_memory_threshold
            )
            
            if should_throttle and not self._throttled:
                logger.warning(
                    f"Resource usage exceeded thresholds - throttling enabled "
                    f"(CPU: {self._current_cpu_usage:.1f}%, Memory: {self._current_memory_usage:.1f}%)"
                )
                self._throttled = True
            elif not should_throttle and self._throttled:
                logger.info(
                    f"Resource usage back to normal - throttling disabled "
                    f"(CPU: {self._current_cpu_usage:.1f}%, Memory: {self._current_memory_usage:.1f}%)"
                )
                self._throttled = False
        
        except Exception as e:
            logger.error(f"Failed to update resource usage: {e}")
    
    async def _log_metrics(self):
        """Log resource usage metrics"""
        try:
            now = datetime.utcnow()
            
            # Log every monitoring interval
            if self._last_log_time is None or (now - self._last_log_time).total_seconds() >= settings.resource_monitoring_interval * 60:
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                logger.info(
                    f"Resource metrics - "
                    f"CPU: {self._current_cpu_usage:.1f}%, "
                    f"Memory: {self._current_memory_usage:.1f}% "
                    f"({memory.used / 1024 / 1024 / 1024:.2f}GB / {memory.total / 1024 / 1024 / 1024:.2f}GB), "
                    f"Disk: {disk.percent:.1f}% "
                    f"({disk.used / 1024 / 1024 / 1024:.2f}GB / {disk.total / 1024 / 1024 / 1024:.2f}GB)"
                )
                
                self._last_log_time = now
        
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")
    
    def get_cpu_usage(self) -> float:
        """
        Get current CPU usage percentage
        
        Returns:
            CPU usage percentage (0-100)
        """
        return self._current_cpu_usage
    
    def get_memory_usage(self) -> float:
        """
        Get current memory usage percentage
        
        Returns:
            Memory usage percentage (0-100)
        """
        return self._current_memory_usage
    
    def is_throttled(self) -> bool:
        """
        Check if system should be throttled due to high resource usage
        
        Returns:
            True if resources exceed thresholds
        """
        return self._throttled
    
    async def check_resources(self) -> Dict[str, Any]:
        """
        Check current resource usage and return status
        
        Returns:
            Dict with resource status
        """
        # Update metrics
        await self._update_resource_usage()
        
        return {
            "cpu_usage": self._current_cpu_usage,
            "memory_usage": self._current_memory_usage,
            "throttled": self._throttled,
            "cpu_threshold": settings.resource_cpu_threshold,
            "memory_threshold": settings.resource_memory_threshold,
        }
    
    async def wait_if_throttled(self, operation_name: str = "operation"):
        """
        Wait if system is throttled due to high resource usage
        
        Args:
            operation_name: Name of operation for logging
        """
        if not settings.resource_monitoring_enabled:
            return
        
        # Check current resources
        await self._update_resource_usage()
        
        if self._throttled:
            logger.warning(
                f"Throttling {operation_name} due to high resource usage "
                f"(CPU: {self._current_cpu_usage:.1f}%, Memory: {self._current_memory_usage:.1f}%)"
            )
            
            # Wait until resources are back to normal
            max_wait_time = 300  # 5 minutes max
            wait_interval = 5  # Check every 5 seconds
            total_waited = 0
            
            while self._throttled and total_waited < max_wait_time:
                await asyncio.sleep(wait_interval)
                await self._update_resource_usage()
                total_waited += wait_interval
            
            if self._throttled:
                logger.warning(
                    f"Resource usage still high after {max_wait_time}s, "
                    f"proceeding with {operation_name} anyway"
                )
            else:
                logger.info(f"Resources back to normal, resuming {operation_name}")


# Global resource monitor service instance
resource_monitor = ResourceMonitorService()
