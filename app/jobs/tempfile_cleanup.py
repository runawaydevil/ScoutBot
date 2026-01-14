"""Temporary file cleanup job"""

import os
import shutil
import time
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger
from app.utils.download_utils import get_tmpfile_path

logger = get_logger(__name__)


async def cleanup_tempfiles_job():
    """Clean up old temporary files, old cache entries, and database maintenance"""
    try:
        logger.debug("🧹 Starting temporary file cleanup...")
        
        # Also cleanup old cache entries for memory optimization
        from app.utils.cache import cache_service
        try:
            deleted = await cache_service.cleanup_old_keys(pattern="feed:*", max_keys=500)
            if deleted > 0:
                logger.debug(f"Cleaned up {deleted} old feed cache entries")
        except Exception as e:
            logger.warning(f"Failed to cleanup old cache entries: {e}")
        
        # Run database maintenance (VACUUM and ANALYZE) weekly
        # Check if it's been 7 days since last maintenance
        from app.database import database
        from datetime import datetime, timedelta
        import os
        from pathlib import Path
        
        # Get database path
        db_path = settings.database_url
        if db_path.startswith("file:"):
            db_path = db_path.replace("file:", "")
        elif db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "")
        
        # Normalize path
        if os.name == "nt" and db_path.startswith("/"):
            if "/app/" in db_path:
                db_path = "./" + db_path.split("/app/")[-1]
            else:
                db_path = "./data/" + os.path.basename(db_path)
            db_path = db_path.replace("/", os.sep)
        
        db_file = Path(db_path)
        if db_file.exists():
            # Check if maintenance file exists and is older than 7 days
            maintenance_file = db_file.parent / ".db_maintenance"
            run_maintenance = False
            
            if not maintenance_file.exists():
                run_maintenance = True
            else:
                maintenance_time = datetime.fromtimestamp(maintenance_file.stat().st_mtime)
                if datetime.now() - maintenance_time > timedelta(days=7):
                    run_maintenance = True
            
            if run_maintenance:
                try:
                    await database.vacuum_and_analyze()
                    # Update maintenance timestamp
                    maintenance_file.touch()
                    logger.debug("Database maintenance (VACUUM/ANALYZE) completed")
                except Exception as e:
                    logger.error(f"Failed to run database maintenance: {e}")

        temp_path = get_tmpfile_path()
        patterns = ["scoutbot-*", "ytdl-*", "spdl-*", "direct-*"]

        cleaned_count = 0
        for pattern in patterns:
            for item in temp_path.glob(pattern):
                try:
                    if item.is_dir():
                        # Check age (1 hour)
                        age_seconds = time.time() - item.stat().st_ctime
                        if age_seconds > 3600:
                            shutil.rmtree(item, ignore_errors=True)
                            cleaned_count += 1
                            logger.debug(f"Cleaned up old temp directory: {item}")
                    elif item.is_file():
                        # Check age (1 hour)
                        age_seconds = time.time() - item.stat().st_ctime
                        if age_seconds > 3600:
                            item.unlink(missing_ok=True)
                            cleaned_count += 1
                            logger.debug(f"Cleaned up old temp file: {item}")
                except Exception as e:
                    logger.warning(f"Failed to clean {item}: {e}")

        # Memory cleanup: limit number of active sessions
        from app.utils.session_manager import session_manager
        try:
            # Close sessions that are close to expiration (within 5 minutes)
            current_time = time.time()
            sessions_to_close = [
                d for d, (s, created_at) in session_manager.sessions.items()
                if current_time - created_at >= (session_manager.session_ttl - 300)  # 5 min before expiration
            ]
            for domain in sessions_to_close:
                await session_manager.close_session(domain)
            if sessions_to_close:
                logger.debug(f"Cleaned up {len(sessions_to_close)} near-expired HTTP sessions")
        except Exception as e:
            logger.warning(f"Failed to cleanup HTTP sessions: {e}")

        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} temporary file(s)/directory(ies)")
        else:
            logger.debug("✅ No old temporary files to clean up")

    except Exception as e:
        logger.error(f"❌ Failed to cleanup temporary files: {e}", exc_info=True)
