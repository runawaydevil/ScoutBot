"""Statistics service for tracking bot activity"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4
from sqlmodel import select, func, and_

from app.database import database
from app.models.statistics import MessageStatistic, DownloadStatistic, ConversionStatistic
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StatisticsService:
    """Service for managing bot statistics"""

    async def record_message(
        self,
        message_type: str,
        chat_id: Optional[str] = None,
        command: Optional[str] = None,
    ):
        """Record a message statistic"""
        try:
            with database.get_session() as session:
                stat = MessageStatistic(
                    id=str(uuid4()),
                    chat_id=chat_id,
                    message_type=message_type,
                    command=command,
                    count=1,
                    date=datetime.utcnow(),
                )
                session.add(stat)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to record message statistic: {e}")

    async def record_download(
        self,
        downloader_type: str,
        status: str,
        chat_id: Optional[str] = None,
        file_size: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Record a download statistic"""
        try:
            with database.get_session() as session:
                stat = DownloadStatistic(
                    id=str(uuid4()),
                    chat_id=chat_id,
                    downloader_type=downloader_type,
                    status=status,
                    file_size=file_size,
                    duration_seconds=duration_seconds,
                    error_message=error_message,
                    date=datetime.utcnow(),
                )
                session.add(stat)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to record download statistic: {e}")

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
        """Record a conversion statistic"""
        try:
            with database.get_session() as session:
                stat = ConversionStatistic(
                    id=str(uuid4()),
                    chat_id=chat_id,
                    conversion_type=conversion_type,
                    status=status,
                    input_format=input_format,
                    output_format=output_format,
                    file_size=file_size,
                    error_message=error_message,
                    date=datetime.utcnow(),
                )
                session.add(stat)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to record conversion statistic: {e}")

    async def get_message_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get message statistics for the last N days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            with database.get_session() as session:
                # Total messages
                total_sent = session.exec(
                    select(func.sum(MessageStatistic.count)).where(
                        and_(
                            MessageStatistic.message_type == "sent",
                            MessageStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                total_received = session.exec(
                    select(func.sum(MessageStatistic.count)).where(
                        and_(
                            MessageStatistic.message_type == "received",
                            MessageStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                total_errors = session.exec(
                    select(func.sum(MessageStatistic.count)).where(
                        and_(
                            MessageStatistic.message_type == "error",
                            MessageStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                # By command
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

                return {
                    "total_sent": total_sent or 0,
                    "total_received": total_received or 0,
                    "total_errors": total_errors or 0,
                    "error_rate": (
                        (total_errors / (total_sent + total_received) * 100)
                        if (total_sent + total_received) > 0
                        else 0.0
                    ),
                    "by_command": command_stats,
                }
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
        """Get download statistics for the last N days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            with database.get_session() as session:
                # Total downloads
                total = session.exec(
                    select(func.count(DownloadStatistic.id)).where(
                        DownloadStatistic.date >= cutoff_date
                    )
                ).first() or 0

                # By status
                success = session.exec(
                    select(func.count(DownloadStatistic.id)).where(
                        and_(
                            DownloadStatistic.status == "success",
                            DownloadStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                failed = session.exec(
                    select(func.count(DownloadStatistic.id)).where(
                        and_(
                            DownloadStatistic.status == "failed",
                            DownloadStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                # By type
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

                # Average file size
                avg_size = session.exec(
                    select(func.avg(DownloadStatistic.file_size)).where(
                        and_(
                            DownloadStatistic.file_size.isnot(None),
                            DownloadStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                return {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "success_rate": (success / total * 100) if total > 0 else 0.0,
                    "by_type": type_stats,
                    "avg_file_size_mb": (avg_size / (1024 * 1024)) if avg_size else 0.0,
                }
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
        """Get conversion statistics for the last N days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            with database.get_session() as session:
                # Total conversions
                total = session.exec(
                    select(func.count(ConversionStatistic.id)).where(
                        ConversionStatistic.date >= cutoff_date
                    )
                ).first() or 0

                # By status
                success = session.exec(
                    select(func.count(ConversionStatistic.id)).where(
                        and_(
                            ConversionStatistic.status == "success",
                            ConversionStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                failed = session.exec(
                    select(func.count(ConversionStatistic.id)).where(
                        and_(
                            ConversionStatistic.status == "failed",
                            ConversionStatistic.date >= cutoff_date,
                        )
                    )
                ).first() or 0

                # By type
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

                return {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "success_rate": (success / total * 100) if total > 0 else 0.0,
                    "by_type": type_stats,
                }
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
