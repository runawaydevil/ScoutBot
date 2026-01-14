"""APScheduler setup for recurring jobs"""

import os
from pathlib import Path
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SchedulerService:
    """Scheduler service using APScheduler"""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.running = False

    def initialize(self):
        """Initialize scheduler"""
        try:
            # Determine job store based on configuration
            job_persistence_enabled = getattr(settings, 'job_persistence_enabled', True)
            
            if job_persistence_enabled:
                # Use SQLiteJobStore for persistence
                # Get database path from settings
                database_url = settings.database_url
                
                # Extract path from database URL
                if database_url.startswith("file:"):
                    db_path = database_url.replace("file:", "")
                elif database_url.startswith("sqlite:///"):
                    db_path = database_url.replace("sqlite:///", "")
                else:
                    db_path = "./data/jobs.db"
                
                # Normalize path
                if os.name == "nt" and db_path.startswith("/"):
                    if "/app/" in db_path:
                        db_path = "./" + db_path.split("/app/")[-1]
                    else:
                        db_path = "./data/jobs.db"
                
                # Create directory if needed
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                
                # Normalize for SQLite URL (always use forward slashes)
                normalized_path = db_path.replace("\\", "/")
                jobs_db_url = f"sqlite:///{normalized_path}"
                
                jobstores = {
                    "default": SQLAlchemyJobStore(url=jobs_db_url, tablename="apscheduler_jobs")
                }
                logger.info(f"Scheduler using SQLiteJobStore for persistence: {jobs_db_url}")
            else:
                # Use MemoryJobStore (no persistence)
                jobstores = {"default": MemoryJobStore()}
                logger.info("Scheduler using MemoryJobStore (no persistence)")
            
            executors = {"default": AsyncIOExecutor()}
            job_defaults = {
                "coalesce": True,  # Coalesce missed jobs to prevent accumulation
                "max_instances": 1,
                "misfire_grace_time": 300,  # 5 minutes grace time for missed jobs
            }

            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone="UTC"
            )

            logger.info("Scheduler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            raise

    def start(self):
        """Start scheduler"""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")

        try:
            self.scheduler.start()
            self.running = True
            logger.info("Scheduler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """Stop scheduler"""
        if self.scheduler:
            try:
                self.scheduler.shutdown(wait=True)
                self.running = False
                logger.info("Scheduler stopped")
            except Exception as e:
                logger.error(f"Failed to stop scheduler: {e}")

    def add_job(self, func, trigger, job_id: Optional[str] = None, **kwargs):
        """Add a job to the scheduler"""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")

        try:
            job = self.scheduler.add_job(
                func, trigger=trigger, id=job_id, replace_existing=True, **kwargs
            )
            if job and job.next_run_time:
                logger.info(
                    f"Job added: {job_id or func.__name__} - Next run: {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
            else:
                logger.info(f"Job added: {job_id or func.__name__}")
        except Exception as e:
            logger.error(f"Failed to add job: {e}")
            raise

    def add_interval_job(self, func, minutes: int, job_id: Optional[str] = None, **kwargs):
        """Add an interval job"""
        trigger = IntervalTrigger(minutes=minutes)
        self.add_job(func, trigger, job_id=job_id, **kwargs)

    def add_cron_job(
        self, func, hour: int = 0, minute: int = 0, job_id: Optional[str] = None, **kwargs
    ):
        """Add a cron job"""
        trigger = CronTrigger(hour=hour, minute=minute)
        self.add_job(func, trigger, job_id=job_id, **kwargs)

    def remove_job(self, job_id: str):
        """Remove a job from the scheduler"""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")

        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
        except Exception as e:
            logger.error(f"Failed to remove job: {job_id}: {e}")

    def get_jobs(self):
        """Get all scheduled jobs"""
        if not self.scheduler:
            return []
        return self.scheduler.get_jobs()


# Global scheduler instance
scheduler = SchedulerService()
