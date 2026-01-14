"""Job management and status tracking service"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlmodel import select
from app.database import database
from app.models.feed import JobStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)


class JobStatusEnum(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobService:
    """Service for managing job status and tracking"""
    
    def __init__(self):
        self.enabled = True
    
    def create_job_status(
        self,
        job_id: str,
        status: str = JobStatusEnum.PENDING,
        progress: Optional[float] = None,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> JobStatus:
        """Create a new job status record"""
        try:
            with database.get_session() as session:
                job_status = JobStatus(
                    job_id=job_id,
                    status=status,
                    progress=progress,
                    result=result,
                    error=error,
                    started_at=datetime.utcnow() if status == JobStatusEnum.RUNNING else None,
                )
                session.add(job_status)
                session.commit()
                session.refresh(job_status)
                logger.debug(f"Created job status: {job_id} - {status}")
                return job_status
        except Exception as e:
            logger.error(f"Failed to create job status: {e}", exc_info=True)
            raise
    
    def update_job_status(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> Optional[JobStatus]:
        """Update job status"""
        try:
            with database.get_session() as session:
                statement = select(JobStatus).where(JobStatus.job_id == job_id)
                job_status = session.exec(statement).first()
                
                if not job_status:
                    # Create if doesn't exist
                    return self.create_job_status(job_id, status or JobStatusEnum.PENDING, progress, result, error)
                
                if status:
                    job_status.status = status
                    if status == JobStatusEnum.RUNNING and not job_status.started_at:
                        job_status.started_at = datetime.utcnow()
                    elif status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED, JobStatusEnum.CANCELLED]:
                        job_status.completed_at = datetime.utcnow()
                
                if progress is not None:
                    job_status.progress = progress
                
                if result is not None:
                    job_status.result = result
                
                if error is not None:
                    job_status.error = error
                
                job_status.updated_at = datetime.utcnow()
                
                session.add(job_status)
                session.commit()
                session.refresh(job_status)
                logger.debug(f"Updated job status: {job_id} - {job_status.status}")
                return job_status
        except Exception as e:
            logger.error(f"Failed to update job status: {e}", exc_info=True)
            return None
    
    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get job status by job ID"""
        try:
            with database.get_session() as session:
                statement = select(JobStatus).where(JobStatus.job_id == job_id)
                return session.exec(statement).first()
        except Exception as e:
            logger.error(f"Failed to get job status: {e}", exc_info=True)
            return None
    
    def get_all_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[JobStatus]:
        """Get all job statuses, optionally filtered by status"""
        try:
            with database.get_session() as session:
                statement = select(JobStatus)
                if status:
                    statement = statement.where(JobStatus.status == status)
                statement = statement.order_by(JobStatus.created_at.desc()).limit(limit)
                return list(session.exec(statement).all())
        except Exception as e:
            logger.error(f"Failed to get all jobs: {e}", exc_info=True)
            return []
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job (mark as cancelled)"""
        try:
            job_status = self.get_job_status(job_id)
            if not job_status:
                return False
            
            if job_status.status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED, JobStatusEnum.CANCELLED]:
                return False  # Already finished
            
            self.update_job_status(job_id, status=JobStatusEnum.CANCELLED)
            logger.info(f"Cancelled job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job: {e}", exc_info=True)
            return False
    
    def cleanup_old_jobs(self, days: int = 7) -> int:
        """Clean up old job status records"""
        try:
            cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
            
            with database.get_session() as session:
                statement = select(JobStatus).where(
                    JobStatus.created_at < cutoff_date,
                    JobStatus.status.in_([JobStatusEnum.COMPLETED, JobStatusEnum.FAILED, JobStatusEnum.CANCELLED])
                )
                old_jobs = session.exec(statement).all()
                
                count = 0
                for job in old_jobs:
                    session.delete(job)
                    count += 1
                
                session.commit()
                logger.info(f"Cleaned up {count} old job status records")
                return count
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}", exc_info=True)
            return 0


# Global job service instance
job_service = JobService()
