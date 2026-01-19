"""Cleanup Service for managing temporary files"""

import asyncio
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CleanupService:
    """Service for automatic cleanup of temporary files"""
    
    def __init__(self):
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._temp_dirs = [
            Path("/tmp"),  # Unix/Linux temp
            Path("C:/Windows/Temp"),  # Windows temp
            Path("./temp"),  # Local temp directory
            Path("./downloads"),  # Local downloads directory
        ]
    
    async def start(self):
        """Start the cleanup service with periodic execution"""
        if self._running:
            logger.warning("Cleanup service is already running")
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info(
            f"Cleanup service started (interval: {settings.pentaract_cleanup_interval} minutes)"
        )
    
    async def stop(self):
        """Stop the cleanup service"""
        if not self._running:
            return
        
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cleanup service stopped")
    
    async def _periodic_cleanup(self):
        """Periodically clean up old temporary files"""
        interval_seconds = settings.pentaract_cleanup_interval * 60
        
        while self._running:
            try:
                # Wait for the interval
                await asyncio.sleep(interval_seconds)
                
                # Check resources before cleanup
                from app.services.resource_monitor_service import resource_monitor
                await resource_monitor.wait_if_throttled("cleanup")
                
                # Execute cleanup
                await self.cleanup_old_files(max_age_hours=1)
                
                # Check disk usage and force cleanup if needed
                temp_size = await self.get_temp_dir_size()
                max_size = 2 * 1024 * 1024 * 1024  # 2GB
                
                if temp_size > max_size:
                    logger.warning(
                        f"Temporary directory size ({temp_size / 1024 / 1024:.2f} MB) "
                        f"exceeds limit, forcing cleanup"
                    )
                    await self.force_cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}", exc_info=True)
    
    async def cleanup_temp_files(self) -> int:
        """
        Clean up temporary files immediately
        
        Returns:
            Number of files cleaned up
        """
        cleaned_count = 0
        
        for temp_dir in self._temp_dirs:
            if not temp_dir.exists():
                continue
            
            try:
                # Look for ScoutBot temporary directories
                pattern = "scoutbot-*"
                for temp_path in temp_dir.glob(pattern):
                    if temp_path.is_dir():
                        try:
                            shutil.rmtree(temp_path)
                            cleaned_count += 1
                            logger.debug(f"Cleaned up temporary directory: {temp_path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up {temp_path}: {e}")
            
            except Exception as e:
                logger.warning(f"Error scanning {temp_dir}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary directories")
        
        return cleaned_count
    
    async def cleanup_old_files(self, max_age_hours: int = 1) -> int:
        """
        Clean up temporary files older than specified age
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
            
        Returns:
            Number of files cleaned up
        """
        cleaned_count = 0
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for temp_dir in self._temp_dirs:
            if not temp_dir.exists():
                continue
            
            try:
                # Look for ScoutBot temporary directories
                pattern = "scoutbot-*"
                for temp_path in temp_dir.glob(pattern):
                    if not temp_path.is_dir():
                        continue
                    
                    try:
                        # Check modification time
                        mtime = datetime.fromtimestamp(temp_path.stat().st_mtime)
                        
                        if mtime < cutoff_time:
                            shutil.rmtree(temp_path)
                            cleaned_count += 1
                            logger.debug(
                                f"Cleaned up old temporary directory: {temp_path} "
                                f"(age: {datetime.now() - mtime})"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to clean up {temp_path}: {e}")
            
            except Exception as e:
                logger.warning(f"Error scanning {temp_dir}: {e}")
        
        if cleaned_count > 0:
            logger.info(
                f"Cleaned up {cleaned_count} temporary directories "
                f"older than {max_age_hours} hour(s)"
            )
        
        return cleaned_count
    
    async def force_cleanup(self) -> int:
        """
        Force cleanup of all temporary files regardless of age
        
        Returns:
            Number of files cleaned up
        """
        logger.warning("Forcing cleanup of all temporary files")
        return await self.cleanup_temp_files()
    
    async def get_temp_dir_size(self) -> int:
        """
        Get total size of temporary directories
        
        Returns:
            Total size in bytes
        """
        total_size = 0
        
        for temp_dir in self._temp_dirs:
            if not temp_dir.exists():
                continue
            
            try:
                # Look for ScoutBot temporary directories
                pattern = "scoutbot-*"
                for temp_path in temp_dir.glob(pattern):
                    if not temp_path.is_dir():
                        continue
                    
                    try:
                        # Calculate directory size
                        for file_path in temp_path.rglob("*"):
                            if file_path.is_file():
                                total_size += file_path.stat().st_size
                    except Exception as e:
                        logger.warning(f"Failed to calculate size of {temp_path}: {e}")
            
            except Exception as e:
                logger.warning(f"Error scanning {temp_dir}: {e}")
        
        return total_size


# Global cleanup service instance
cleanup_service = CleanupService()
