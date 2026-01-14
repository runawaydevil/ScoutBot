"""Bot settings model for editable configurations"""

from datetime import datetime
from sqlmodel import SQLModel, Field


class BotSettings(SQLModel, table=True):
    """Editable bot settings stored in database"""

    __tablename__ = "botsettings"

    id: str = Field(primary_key=True)
    key: str = Field(unique=True, index=True, description="Setting key (e.g., 'audio_format')")
    value: str = Field(description="Setting value as JSON string")
    value_type: str = Field(description="Python type: 'str', 'int', 'bool', 'float'")
    category: str = Field(index=True, description="Category: 'download', 'security', 'features', 'advanced'")
    description: str = Field(description="Human-readable description")
    requires_restart: bool = Field(default=False, description="Whether change requires bot restart")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
