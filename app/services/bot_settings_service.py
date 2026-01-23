"""Bot settings service for managing editable configurations"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4
from sqlmodel import select

from app.database import database
from app.models.bot_settings import BotSettings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BotSettingsService:
    """Service for managing bot settings stored in database"""

    def serialize_value(self, value: Any, value_type: str) -> str:
        """Serialize value to JSON string"""
        # Handle None values - serialize as JSON null
        return json.dumps(value)

    def deserialize_value(self, value: str, value_type: str) -> Any:
        """Deserialize value from JSON string"""
        parsed = json.loads(value)
        # Convert to appropriate type
        if value_type == "int":
            # Handle None/null for optional int values
            if parsed is None:
                return None
            return int(parsed)
        elif value_type == "bool":
            return bool(parsed)
        elif value_type == "float":
            return float(parsed)
        else:
            # Handle None/null for optional str values
            if parsed is None:
                return None
            return str(parsed)

    async def get_setting(self, key: str) -> Optional[BotSettings]:
        """Get a setting by key"""
        try:
            with database.get_session() as session:
                statement = select(BotSettings).where(BotSettings.key == key)
                return session.exec(statement).first()
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            return None

    async def get_setting_value(self, key: str, default: Any = None) -> Any:
        """Get setting value (deserialized)"""
        setting = await self.get_setting(key)
        if setting:
            return self.deserialize_value(setting.value, setting.value_type)
        return default

    async def set_setting(
        self,
        key: str,
        value: Any,
        value_type: str,
        category: str,
        description: str,
        requires_restart: bool = False,
    ):
        """Set or update a setting"""
        try:
            with database.get_session() as session:
                # Get setting within the same session
                statement = select(BotSettings).where(BotSettings.key == key)
                setting = session.exec(statement).first()
                
                serialized_value = self.serialize_value(value, value_type)

                if setting:
                    # Update existing
                    setting.value = serialized_value
                    setting.value_type = value_type
                    setting.category = category
                    setting.description = description
                    setting.requires_restart = requires_restart
                    setting.updated_at = datetime.utcnow()
                else:
                    # Create new
                    setting = BotSettings(
                        id=str(uuid4()),
                        key=key,
                        value=serialized_value,
                        value_type=value_type,
                        category=category,
                        description=description,
                        requires_restart=requires_restart,
                    )
                    session.add(setting)

                session.commit()
                session.refresh(setting)
                # Removed INFO log for setting updates (only log errors)
                logger.debug(f"Updated setting {key} = {value} ({value_type})")
                return setting
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise

    async def get_settings_by_category(self, category: str) -> List[BotSettings]:
        """Get all settings in a category"""
        try:
            with database.get_session() as session:
                statement = select(BotSettings).where(BotSettings.category == category)
                return list(session.exec(statement).all())
        except Exception as e:
            logger.error(f"Failed to get settings for category {category}: {e}")
            return []

    async def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary"""
        try:
            with database.get_session() as session:
                settings = session.exec(select(BotSettings)).all()
                result = {}
                for setting in settings:
                    result[setting.key] = self.deserialize_value(
                        setting.value, setting.value_type
                    )
                return result
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            return {}

    async def initialize_default_settings(self):
        """Initialize default settings from config if they don't exist"""
        from app.config import settings as app_settings

        default_settings = [
            # Download settings
            ("audio_format", app_settings.audio_format, "str", "download", "Audio format (mp3, m4a, etc.)", False),
            ("enable_ffmpeg", app_settings.enable_ffmpeg, "bool", "download", "Enable FFmpeg for video processing", True),
            ("enable_aria2", app_settings.enable_aria2, "bool", "download", "Enable Aria2 for downloads", True),
            # Security settings
            ("allowed_user_id", app_settings.allowed_user_id, "str" if app_settings.allowed_user_id is None else "int", "security", "Allowed user ID (None = all users)", True),
            ("anti_block_enabled", app_settings.anti_block_enabled, "bool", "security", "Enable anti-blocking system", False),
            # Features
            ("spotify_enabled", app_settings.spotify_enabled, "bool", "features", "Enable Spotify downloads", False),
            ("enable_imagemagick", app_settings.enable_imagemagick, "bool", "features", "Enable ImageMagick", True),
            ("enable_ocr", app_settings.enable_ocr, "bool", "features", "Enable OCR functionality", False),
            ("enable_stickers", app_settings.enable_stickers, "bool", "features", "Enable sticker commands", True),
            ("enable_memes", app_settings.enable_memes, "bool", "features", "Enable meme generator", True),
            # Advanced
            ("log_level", app_settings.log_level, "str", "advanced", "Log level (debug, info, warning, error)", True),
            ("max_feeds_per_chat", app_settings.max_feeds_per_chat, "int", "advanced", "Maximum feeds per chat", False),
            ("cache_ttl_minutes", app_settings.cache_ttl_minutes, "int", "advanced", "Cache TTL in minutes", False),
        ]

        for key, value, value_type, category, description, requires_restart in default_settings:
            existing = await self.get_setting(key)
            if not existing:
                # Handle None values for allowed_user_id - store as None (JSON null)
                if key == "allowed_user_id" and value is None:
                    value = None  # Store as JSON null
                    value_type = "int"  # Keep as int type, but value is None
                elif value is None:
                    # Skip None values for other settings
                    continue
                await self.set_setting(
                    key, value, value_type, category, description, requires_restart
                )


# Global bot settings service instance
bot_settings_service = BotSettingsService()
