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
    """Clean up old temporary files"""
    try:
        logger.debug("🧹 Starting temporary file cleanup...")

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

        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} temporary file(s)/directory(ies)")
        else:
            logger.debug("✅ No old temporary files to clean up")

    except Exception as e:
        logger.error(f"❌ Failed to cleanup temporary files: {e}", exc_info=True)
