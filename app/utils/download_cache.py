"""Download cache service for video downloads"""

import hashlib
import json
from typing import Optional, Dict, Any, List

from app.utils.cache import cache_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DownloadCache:
    """Cache service for video downloads"""

    def _calc_video_key(self, url: str, quality: str, format: str) -> str:
        """Calculate cache key for video"""
        h = hashlib.md5()
        h.update((url + quality + format).encode())
        return f"download:{h.hexdigest()}"

    async def get_cache(self, url: str, quality: str, format: str) -> Optional[Dict[str, Any]]:
        """Get cached download data"""
        key = self._calc_video_key(url, quality, format)
        cached = await cache_service.get(key)
        if cached:
            logger.debug(f"Cache hit for download: {url}")
            return cached
        return None

    async def set_cache(
        self, url: str, quality: str, format: str, file_id: List[str], meta: Dict[str, Any]
    ):
        """Set cache for download"""
        key = self._calc_video_key(url, quality, format)
        cache_data = {
            "file_id": json.dumps(file_id),
            "meta": json.dumps(meta, ensure_ascii=False),
        }
        # Cache for 7 days
        await cache_service.set(key, cache_data, ttl=604800)
        logger.debug(f"Cached download: {url}")

    async def delete_cache(self, url: str, quality: str, format: str):
        """Delete cache for download"""
        key = self._calc_video_key(url, quality, format)
        await cache_service.delete(key)


# Global download cache instance
download_cache = DownloadCache()
