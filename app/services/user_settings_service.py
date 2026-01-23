"""User settings service for managing download preferences"""

from datetime import datetime
from typing import Optional, Dict
from uuid import uuid4
from sqlmodel import select
import asyncio
import time

from app.database import database
from app.models.user_settings import UserSettings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Valid values for quality and format
VALID_QUALITIES = ["high", "medium", "low", "audio", "custom"]
VALID_FORMATS = ["video", "audio", "document"]
VALID_STORAGE_PREFERENCES = ["auto", "pentaract", "local"]


class UserSettingsService:
    """Service for managing user download settings with in-memory cache"""

    def __init__(self):
        # In-memory cache: user_id -> (settings, timestamp)
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_lock = asyncio.Lock()

    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if cache entry is still valid"""
        return (time.time() - timestamp) < self._cache_ttl

    async def _get_from_cache(self, user_id: str) -> Optional[UserSettings]:
        """Get settings from cache if valid"""
        async with self._cache_lock:
            if user_id in self._cache:
                settings, timestamp = self._cache[user_id]
                if self._is_cache_valid(timestamp):
                    return settings
                else:
                    # Remove expired entry
                    del self._cache[user_id]
        return None

    async def _set_cache(self, user_id: str, settings: UserSettings):
        """Store settings in cache"""
        async with self._cache_lock:
            self._cache[user_id] = (settings, time.time())

    async def _invalidate_cache(self, user_id: str):
        """Invalidate cache for a user"""
        async with self._cache_lock:
            if user_id in self._cache:
                del self._cache[user_id]

    async def get_settings(self, user_id: str) -> UserSettings:
        """Get or create user settings (with cache)"""
        # Check cache first
        cached = await self._get_from_cache(user_id)
        if cached:
            logger.debug(f"Cache hit for user settings: {user_id}")
            return cached

        with database.get_session() as session:
            statement = select(UserSettings).where(UserSettings.user_id == user_id)
            settings = session.exec(statement).first()

            if not settings:
                # Create default settings
                settings = UserSettings(
                    id=str(uuid4()),
                    user_id=user_id,
                    quality="high",
                    format="video",
                )
                session.add(settings)
                session.commit()
                session.refresh(settings)
                logger.info(f"Created default settings for user {user_id}")

            # Store in cache
            await self._set_cache(user_id, settings)
            return settings

    async def get_quality(self, user_id: str) -> str:
        """Get user quality setting"""
        settings = await self.get_settings(user_id)
        return settings.quality

    async def get_format(self, user_id: str) -> str:
        """Get user format setting"""
        settings = await self.get_settings(user_id)
        return settings.format

    async def set_quality(self, user_id: str, quality: str):
        """Set user quality setting"""
        if quality not in VALID_QUALITIES:
            raise ValueError(f"Invalid quality: {quality}. Valid values: {VALID_QUALITIES}")

        from datetime import datetime

        with database.get_session() as session:
            settings = await self.get_settings(user_id)
            settings.quality = quality
            settings.updated_at = datetime.utcnow()
            session.add(settings)
            session.commit()
            # Invalidate cache
            await self._invalidate_cache(user_id)
            logger.info(f"Updated quality for user {user_id}: {quality}")

    async def set_format(self, user_id: str, format: str):
        """Set user format setting"""
        if format not in VALID_FORMATS:
            raise ValueError(f"Invalid format: {format}. Valid values: {VALID_FORMATS}")

        from datetime import datetime

        with database.get_session() as session:
            settings = await self.get_settings(user_id)
            settings.format = format
            settings.updated_at = datetime.utcnow()
            session.add(settings)
            session.commit()
            # Invalidate cache
            await self._invalidate_cache(user_id)
            logger.info(f"Updated format for user {user_id}: {format}")

    async def get_storage_preference(self, user_id: str) -> str:
        """Get user storage preference (auto, pentaract, local)"""
        settings = await self.get_settings(user_id)
        return settings.storage_preference

    async def set_storage_preference(self, user_id: str, preference: str):
        """Set user storage preference"""
        if preference not in VALID_STORAGE_PREFERENCES:
            raise ValueError(
                f"Invalid storage preference: {preference}. "
                f"Valid values: {VALID_STORAGE_PREFERENCES}"
            )

        from datetime import datetime

        with database.get_session() as session:
            settings = await self.get_settings(user_id)
            settings.storage_preference = preference
            settings.updated_at = datetime.utcnow()
            session.add(settings)
            session.commit()
            # Invalidate cache
            await self._invalidate_cache(user_id)
            logger.info(f"Updated storage preference for user {user_id}: {preference}")


# Global user settings service instance
user_settings_service = UserSettingsService()
