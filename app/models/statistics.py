"""Statistics models for tracking bot activity"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class MessageStatistic(SQLModel, table=True):
    """Statistics for messages sent/received"""

    __tablename__ = "messagestatistic"

    id: str = Field(primary_key=True)
    chat_id: Optional[str] = Field(default=None, index=True)
    message_type: str = Field(index=True)  # 'sent', 'received', 'error'
    command: Optional[str] = Field(default=None, index=True)  # Command name if applicable
    count: int = Field(default=1)
    date: datetime = Field(default_factory=datetime.utcnow, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DownloadStatistic(SQLModel, table=True):
    """Statistics for downloads"""

    __tablename__ = "downloadstatistic"

    id: str = Field(primary_key=True)
    chat_id: Optional[str] = Field(default=None, index=True)
    downloader_type: str = Field(index=True)  # 'youtube', 'spotify', 'instagram', etc.
    status: str = Field(index=True)  # 'success', 'failed', 'cancelled'
    file_size: Optional[int] = Field(default=None)  # Size in bytes
    duration_seconds: Optional[int] = Field(default=None)  # Download duration
    error_message: Optional[str] = Field(default=None)
    date: datetime = Field(default_factory=datetime.utcnow, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConversionStatistic(SQLModel, table=True):
    """Statistics for media conversions"""

    __tablename__ = "conversionstatistic"

    id: str = Field(primary_key=True)
    chat_id: Optional[str] = Field(default=None, index=True)
    conversion_type: str = Field(index=True)  # 'convert', 'gif', 'clip', 'audio', 'compress', 'frames', 'meme', 'sticker', 'subs'
    status: str = Field(index=True)  # 'success', 'failed'
    input_format: Optional[str] = Field(default=None)
    output_format: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None)  # Output size in bytes
    error_message: Optional[str] = Field(default=None)
    date: datetime = Field(default_factory=datetime.utcnow, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
