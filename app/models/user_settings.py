"""User settings model for download preferences"""

from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


class UserSettings(SQLModel, table=True):
    """User settings for download quality and format"""

    __tablename__ = "usersettings"

    id: str = Field(primary_key=True)
    user_id: str = Field(index=True, unique=True)  # Telegram user ID
    # Valid values: "high", "medium", "low", "audio", "custom"
    quality: str = Field(default="high")
    # Valid values: "video", "audio", "document"
    format: str = Field(default="video")
    # Storage preference: "auto", "pentaract", "local"
    storage_preference: str = Field(default="auto", alias="storagePreference")
    pentaract_auto_upload: bool = Field(default=True, alias="pentaractAutoUpload")
    pentaract_notify_uploads: bool = Field(default=True, alias="pentaractNotifyUploads")
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")
