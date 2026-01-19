"""Pentaract upload tracking model"""

from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime
import secrets
import string


def generate_file_code(length: int = 6) -> str:
    """Generate a unique file code (e.g., ABC123)"""
    # Use uppercase letters and digits
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


class PentaractUpload(SQLModel, table=True):
    """Track uploads to Pentaract storage"""

    __tablename__ = "pentaract_uploads"

    id: str = Field(primary_key=True)
    user_id: str = Field(index=True, alias="userId")
    file_code: str = Field(index=True, unique=True, alias="fileCode")  # Unique code for download (e.g., ABC123)
    original_filename: str = Field(alias="originalFilename")  # Original filename
    file_path: str = Field(alias="filePath")  # Local temp path
    remote_path: str = Field(alias="remotePath")  # Remote path in Pentaract (uses file_code)
    file_size: int = Field(alias="fileSize")
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    status: str  # pending, uploading, completed, failed
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    upload_started_at: Optional[datetime] = Field(default=None, alias="uploadStartedAt")
    upload_completed_at: Optional[datetime] = Field(default=None, alias="uploadCompletedAt")
    retry_count: int = Field(default=0, alias="retryCount")
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")
