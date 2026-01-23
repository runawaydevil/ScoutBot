"""Statistics service for tracking bot activity"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4
from sqlmodel import select, func, and_
from sqlalchemy import case
import asyncio
import time

from app.database import database
from app.models.statistics import MessageStatistic, DownloadStatistic, ConversionStatistic
from app.utils.logger import get_logger
from app.utils.cache import cache_service

logger = get_logger(__name__)


class StatisticsBuffer:
    """Buffer for bulk inserting statistics to reduce database commits"""
    
    def __init__(self, max_size: int = 100, flush_interval: float = 30.0):
        self.max_size = max_size
        self.flush_interval = flush_interval
        self.message_buffer: List[Dict[str, Any]] = []
        self.download_buffer: List[Dict[str, Any]] = []
        self.conversion_buffer: List[Dict[str, Any]] = []
        self.last_flush = time.time()
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
    
    async def add_message(self, message_type: str, chat_id: Optional[str] = None, command: Optional[str] = None):
        """Add message statistic to buffer"""
        async with self._lock:
            self.message_buffer.append({
                "id": str(uuid4()),
                "chat_id": chat_id,
                "message_type": message_type,
                "command": command,
                "count": 1,
                "date": datetime.utcnow(),
            })
            await self._check_flush()
    
    async def add_download(
        self,
        downloader_type: str,
        status: str,
        chat_id: Optional[str] = None,
        file_size: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Add download statistic to buffer"""
        async with self._lock:
            self.download_buffer.append({
                "id": str(uuid4()),
                "chat_id": chat_id,
                "downloader_type": downloader_type,
                "status": status,
                "file_size": file_size,
                "duration_seconds": duration_seconds,
                "error_message": error_message,
                "date": datetime.utcnow(),
            })
            await self._check_flush()
    
    async def add_conversion(
        self,
        conversion_type: str,
        status: str,
        chat_id: Optional[str] = None,
        input_format: Optional[str] = None,
        output_format: Optional[str] = None,
        file_size: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Add conversion statistic to buffer"""
        async with self._lock:
            self.conversion_buffer.append({
                "id": str(uuid4()),
                "chat_id": chat_id,
                "conversion_type": conversion_type,
                "status": status,
                "input_format": input_format,
                "output_format": output_format,
                "file_size": file_size,
                "error_message": error_message,
                "date": datetime.utcnow(),
            })
            await self._check_flush()
    
    async def _check_flush(self):
        """Check if buffer should be flushed"""
        total_size = len(self.message_buffer) + len(self.download_buffer) + len(self.conversion_buffer)
        time_since_flush = time.time() - self.last_flush
        
        if total_size >= self.max_size or time_since_flush >= self.flush_interval:
            await self.flush()
    
    async def flush(self):
        """Flush all buffers to database"""
        async with self._lock:
            if not (self.message_buffer or self.download_buffer or self.conversion_buffer):
                return
            
            try:
                with database.get_session() as session:
                    # Bulk insert messages
                    if self.message_buffer:
                        session.bulk_insert_mappings(MessageStatistic, self.message_buffer)
                        count = len(self.message_buffer)
                        self.message_buffer.clear()
                        logger.debug(f"Bulk inserted {count} message statistics")
                    
                    # Bulk insert downloads
                    if self.download_buffer:
                        session.bulk_insert_mappings(DownloadStatistic, self.download_buffer)
                        count = len(self.download_buffer)
                        self.download_buffer.clear()
                        logger.debug(f"Bulk inserted {count} download statistics")
                    
                    # Bulk insert conversions
                    if self.conversion_buffer:
                        session.bulk_insert_mappings(ConversionStatistic, self.conversion_buffer)
                        count = len(self.conversion_buffer)
                        self.conversion_buffer.clear()
                        logger.debug(f"Bulk inserted {count} conversion statistics")
                    
                    session.commit()
                    self.last_flush = time.time()
            except Exception as e:
                logger.error(f"Failed to flush statistics buffer: {e}", exc_info=True)
                # Clear buffers on error to prevent memory buildup
                self.message_buffer.clear()
                self.download_buffer.clear()
                self.conversion_buffer.clear()


class StatisticsService:
    """Service for managing bot statistics"""

    def __init__(self):
        self.buffer = StatisticsBuffer(max_size=100, flush_interval=30.0)

    async def record_message(
        self,
        message_type: str,
        chat_id: Optional[str] = None,
        command: Optional[str] = None,
    ):
        """Record a message statistic (buffered for bulk insert)"""
        await self.buffer.add_message(message_type, chat_id, command)

    async def record_download(
        self,
        downloader_type: str,
        status: str,
        chat_id: Optional[str] = None,
        file_size: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Record a download statistic (buffered for bulk insert)"""
        await self.buffer.add_download(
            downloader_type, status, chat_id, file_size, duration_seconds, error_message
        )

    async def record_conversion(
        self,
        conversion_type: str,
        status: str,
        chat_id: Optional[str] = None,
        input_format: Optional[str] = None,
        output_format: Optional[str] = None,
        file_size: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Record a conversion statistic (buffered for bulk insert)"""
        await self.buffer.add_conversion(
            conversion_type, status, chat_id, input_format, output_format, file_size, error_message
        )

    async def get_message_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get message statistics for the last N days (optimized with combined query and cache)"""
        # Check cache first (5 minute TTL)
        cache_key = f"message_stats:{days}"
        cached = await cache_service.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for message stats (days={days})")
            return cached
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            with database.get_session() as session:
                # Combined query: get all totals in one query using CASE WHEN
                totals_result = session.exec(
                    select(
                        func.sum(
                            case(
                                (MessageStatistic.message_type == "sent", MessageStatistic.count),
                                else_=0
                            )
                        ).label("sent"),
                        func.sum(
                            case(
                                (MessageStatistic.message_type == "received", MessageStatistic.count),
                                else_=0
                            )
                        ).label("received"),
                        func.sum(
                            case(
                                (MessageStatistic.message_type == "error", MessageStatistic.count),
                                else_=0
                            )
                        ).label("errors")
                    ).where(MessageStatistic.date >= cutoff_date)
                ).first()
                
                total_sent = totals_result[0] or 0 if totals_result else 0
                total_received = totals_result[1] or 0 if totals_result else 0
                total_errors = totals_result[2] or 0 if totals_result else 0

                # By command (separate query as it needs grouping)
                command_stats = {}
                commands = session.exec(
                    select(MessageStatistic.command, func.sum(MessageStatistic.count))
                    .where(
                        and_(
                            MessageStatistic.command.isnot(None),
                            MessageStatistic.date >= cutoff_date,
                        )
                    )
                    .group_by(MessageStatistic.command)
                ).all()

                for command, count in commands:
                    if command:
                        command_stats[command] = count

                result = {
                    "total_sent": total_sent,
                    "total_received": total_received,
                    "total_errors": total_errors,
                    "error_rate": (
                        (total_errors / (total_sent + total_received) * 100)
                        if (total_sent + total_received) > 0
                        else 0.0
                    ),
                    "by_command": command_stats,
                }
                
                # Cache result for 5 minutes
                await cache_service.set(cache_key, result, ttl=300)
                return result
        except Exception as e:
            logger.error(f"Failed to get message stats: {e}")
            return {
                "total_sent": 0,
                "total_received": 0,
                "total_errors": 0,
                "error_rate": 0.0,
                "by_command": {},
            }

    async def get_download_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get download statistics for the last N days (optimized with combined query and cache)"""
        # Check cache first (5 minute TTL)
        cache_key = f"download_stats:{days}"
        cached = await cache_service.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for download stats (days={days})")
            return cached
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            with database.get_session() as session:
                # Combined query: get total, success, and failed in one query
                totals_result = session.exec(
                    select(
                        func.count(DownloadStatistic.id).label("total"),
                        func.sum(
                            case(
                                (DownloadStatistic.status == "success", 1),
                                else_=0
                            )
                        ).label("success"),
                        func.sum(
                            case(
                                (DownloadStatistic.status == "failed", 1),
                                else_=0
                            )
                        ).label("failed"),
                        func.avg(DownloadStatistic.file_size).label("avg_size")
                    ).where(
                        and_(
                            DownloadStatistic.date >= cutoff_date,
                            DownloadStatistic.file_size.isnot(None)
                        )
                    )
                ).first()
                
                # Also get total count (including records without file_size)
                total_all = session.exec(
                    select(func.count(DownloadStatistic.id)).where(
                        DownloadStatistic.date >= cutoff_date
                    )
                ).first() or 0
                
                total = total_all
                success = int(totals_result[1] or 0) if totals_result else 0
                failed = int(totals_result[2] or 0) if totals_result else 0
                avg_size = totals_result[3] or 0 if totals_result else 0

                # By type (separate query as it needs grouping)
                type_stats = {}
                types = session.exec(
                    select(
                        DownloadStatistic.downloader_type,
                        func.count(DownloadStatistic.id),
                    )
                    .where(DownloadStatistic.date >= cutoff_date)
                    .group_by(DownloadStatistic.downloader_type)
                ).all()

                for downloader_type, count in types:
                    type_stats[downloader_type] = count

                result = {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "success_rate": (success / total * 100) if total > 0 else 0.0,
                    "by_type": type_stats,
                    "avg_file_size_mb": (avg_size / (1024 * 1024)) if avg_size else 0.0,
                }
                
                # Cache result for 5 minutes
                await cache_service.set(cache_key, result, ttl=300)
                return result
        except Exception as e:
            logger.error(f"Failed to get download stats: {e}")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0.0,
                "by_type": {},
                "avg_file_size_mb": 0.0,
            }

    async def get_conversion_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get conversion statistics for the last N days (optimized with combined query and cache)"""
        # Check cache first (5 minute TTL)
        cache_key = f"conversion_stats:{days}"
        cached = await cache_service.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for conversion stats (days={days})")
            return cached
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            with database.get_session() as session:
                # Combined query: get total, success, and failed in one query
                totals_result = session.exec(
                    select(
                        func.count(ConversionStatistic.id).label("total"),
                        func.sum(
                            case(
                                (ConversionStatistic.status == "success", 1),
                                else_=0
                            )
                        ).label("success"),
                        func.sum(
                            case(
                                (ConversionStatistic.status == "failed", 1),
                                else_=0
                            )
                        ).label("failed")
                    ).where(ConversionStatistic.date >= cutoff_date)
                ).first()
                
                total = totals_result[0] or 0 if totals_result else 0
                success = int(totals_result[1] or 0) if totals_result else 0
                failed = int(totals_result[2] or 0) if totals_result else 0

                # By type (separate query as it needs grouping)
                type_stats = {}
                types = session.exec(
                    select(
                        ConversionStatistic.conversion_type,
                        func.count(ConversionStatistic.id),
                    )
                    .where(ConversionStatistic.date >= cutoff_date)
                    .group_by(ConversionStatistic.conversion_type)
                ).all()

                for conversion_type, count in types:
                    type_stats[conversion_type] = count

                result = {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "success_rate": (success / total * 100) if total > 0 else 0.0,
                    "by_type": type_stats,
                }
                
                # Cache result for 5 minutes
                await cache_service.set(cache_key, result, ttl=300)
                return result
        except Exception as e:
            logger.error(f"Failed to get conversion stats: {e}")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0.0,
                "by_type": {},
            }


# Global statistics service instance
statistics_service = StatisticsService()
