"""Bot state model for controlling bot operations"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class BotState(SQLModel, table=True):
    """Global bot state"""

    __tablename__ = "botstate"

    id: str = Field(primary_key=True, default="global")
    is_stopped: bool = Field(default=False, description="Whether bot operations are stopped")
    stopped_at: Optional[datetime] = Field(default=None, description="When bot was stopped")
    stopped_by: Optional[str] = Field(default=None, description="User ID who stopped the bot")
    reason: Optional[str] = Field(default=None, description="Reason for stopping")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
