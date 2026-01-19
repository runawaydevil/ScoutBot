"""Pentaract file metadata model"""

from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class PentaractFile(SQLModel, table=True):
    """Metadata for files stored in Pentaract"""

    __tablename__ = "pentaract_files"

    id: str = Field(primary_key=True)
    user_id: str = Field(index=True, alias="userId")
    remote_path: str = Field(unique=True, index=True, alias="remotePath")
    filename: str
    file_size: int = Field(alias="fileSize")
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    folder: str = Field(default="downloads")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, alias="uploadedAt")
    last_accessed_at: Optional[datetime] = Field(default=None, alias="lastAccessedAt")
    download_count: int = Field(default=0, alias="downloadCount")
    file_metadata: Optional[str] = Field(default=None, alias="metadata")  # JSON string
