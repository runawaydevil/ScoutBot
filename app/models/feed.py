"""SQLModel models for feeds and chats"""

from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class ChatBase(SQLModel):
    """Base chat model"""

    type: str  # 'private', 'group', 'channel'
    title: Optional[str] = None


class Chat(ChatBase, table=True):
    """Chat model"""

    __tablename__ = "chat"

    id: str = Field(primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow, alias="updatedAt")

    settings: Optional["ChatSettings"] = Relationship(
        back_populates="chat", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    feeds: List["Feed"] = Relationship(
        back_populates="chat", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    statistics: List["Statistic"] = Relationship(
        back_populates="chat", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ChatSettings(SQLModel, table=True):
    """Chat settings model"""

    __tablename__ = "chatsettings"

    chat_id: str = Field(primary_key=True, foreign_key="chat.id", alias="chatId")
    language: str = "en"  # 'en' or 'pt'
    check_interval: int = Field(default=120, alias="checkInterval")  # seconds
    max_feeds: int = Field(default=50, alias="maxFeeds")
    enable_filters: bool = Field(default=True, alias="enableFilters")
    message_template: Optional[str] = Field(default=None, alias="messageTemplate")
    timezone: str = "America/Sao_Paulo"

    # Security settings
    rate_limit_enabled: bool = Field(default=True, alias="rateLimitEnabled")
    max_requests_per_minute: int = Field(default=3, alias="maxRequestsPerMinute")
    min_delay_ms: int = Field(default=200000, alias="minDelayMs")
    cache_enabled: bool = Field(default=True, alias="cacheEnabled")
    cache_ttl_minutes: int = Field(default=20, alias="cacheTTLMinutes")
    retry_enabled: bool = Field(default=True, alias="retryEnabled")
    max_retries: int = Field(default=3, alias="maxRetries")
    timeout_seconds: int = Field(default=10, alias="timeoutSeconds")

    chat: Chat = Relationship(back_populates="settings")


class FeedBase(SQLModel):
    """Base feed model"""

    chat_id: str = Field(foreign_key="chat.id", alias="chatId")
    name: str
    url: str  # Original URL
    rss_url: str = Field(alias="rssUrl")  # Converted RSS URL
    last_item_id: Optional[str] = Field(default=None, alias="lastItemId")
    last_notified_at: Optional[datetime] = Field(default=None, alias="lastNotifiedAt")
    last_seen_at: Optional[datetime] = Field(default=None, alias="lastSeenAt")
    check_interval_minutes: int = Field(default=10, alias="checkIntervalMinutes")
    max_age_minutes: int = Field(default=1440, alias="maxAgeMinutes")  # 24h default
    enabled: bool = True
    failures: int = 0
    last_check: Optional[datetime] = Field(default=None, alias="lastCheck")


class Feed(FeedBase, table=True):
    """Feed model"""

    __tablename__ = "feed"

    id: str = Field(primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow, alias="updatedAt")

    chat: Chat = Relationship(back_populates="feeds")
    filters: List["FeedFilter"] = Relationship(
        back_populates="feed", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class FeedFilter(SQLModel, table=True):
    """Feed filter model"""

    __tablename__ = "feedfilter"

    id: str = Field(primary_key=True)
    feed_id: str = Field(foreign_key="feed.id", alias="feedId")
    type: str  # 'include', 'exclude'
    pattern: str
    is_regex: bool = Field(default=False, alias="isRegex")

    feed: Feed = Relationship(back_populates="filters")


class Statistic(SQLModel, table=True):
    """Statistic model"""

    __tablename__ = "statistic"

    id: str = Field(primary_key=True)
    chat_id: str = Field(foreign_key="chat.id", alias="chatId")
    feed_id: Optional[str] = Field(default=None, foreign_key="feed.id", alias="feedId")
    action: str  # 'message_sent', 'feed_added', 'feed_checked'
    count: int = 1
    date: datetime = Field(default_factory=datetime.utcnow)

    chat: Chat = Relationship(back_populates="statistics")


class ItemDedupe(SQLModel, table=True):
    """Item deduplication model"""

    __tablename__ = "itemdedupe"

    id: str = Field(primary_key=True)
    item_id: str = Field(index=True, alias="itemId")
    feed_id: Optional[str] = Field(default=None, index=True, foreign_key="feed.id", alias="feedId")
    seen_at: datetime = Field(default_factory=datetime.utcnow, alias="seenAt")
    expires_at: datetime = Field(index=True, alias="expiresAt")


class AuthState(SQLModel, table=True):
    """Authentication state model"""

    __tablename__ = "authstate"

    id: str = Field(primary_key=True)
    provider: str = Field(unique=True)  # 'reddit', 'instagram', etc.
    access_token: Optional[str] = Field(default=None, alias="accessToken")
    refresh_token: Optional[str] = Field(default=None, alias="refreshToken")
    expires_at: Optional[datetime] = Field(default=None, alias="expiresAt")
    token_type: Optional[str] = Field(default=None, alias="tokenType")
    scope: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")


class ConnectionState(SQLModel, table=True):
    """Connection state model"""

    __tablename__ = "connectionstate"

    id: str = Field(primary_key=True)
    service: str = Field(unique=True)  # 'telegram', 'reddit', 'rss'
    status: str = "connected"  # 'connected', 'disconnected', 'recovering', 'circuit_open'
    last_successful_call: datetime = Field(
        default_factory=datetime.utcnow, alias="lastSuccessfulCall"
    )
    consecutive_failures: int = Field(default=0, alias="consecutiveFailures")
    current_retry_delay: int = Field(default=0, alias="currentRetryDelay")  # milliseconds
    next_retry_at: datetime = Field(default_factory=datetime.utcnow, alias="nextRetryAt")
    total_downtime: int = Field(default=0, alias="totalDowntime")  # milliseconds
    last_error_code: Optional[int] = Field(default=None, alias="lastErrorCode")
    last_error_description: Optional[str] = Field(default=None, alias="lastErrorDescription")
    last_error_type: Optional[str] = Field(default=None, alias="lastErrorType")
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")


class HealthMetric(SQLModel, table=True):
    """Health metric model"""

    __tablename__ = "healthmetric"

    id: str = Field(primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    service: str = Field(index=True)  # 'telegram', 'reddit', 'rss'
    metric_type: str = Field(
        index=True, alias="metricType"
    )  # 'connection_attempt', 'message_sent', 'error_occurred'
    success: bool
    response_time: Optional[int] = Field(default=None, alias="responseTime")  # milliseconds
    error_code: Optional[str] = Field(default=None, alias="errorCode")
    extra_data: Optional[str] = Field(
        default=None, alias="metadata"
    )  # JSON string for additional data (renamed from metadata to avoid SQLAlchemy conflict)
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")


class QueuedMessage(SQLModel, table=True):
    """Queued message model"""

    __tablename__ = "queuedmessage"

    id: str = Field(primary_key=True)
    chat_id: str = Field(index=True, foreign_key="chat.id", alias="chatId")
    message_data: str = Field(alias="messageData")  # JSON serialized
    priority: int = 2  # 1=LOW, 2=NORMAL, 3=HIGH, 4=CRITICAL
    enqueued_at: datetime = Field(default_factory=datetime.utcnow, index=True, alias="enqueuedAt")
    processed_at: Optional[datetime] = Field(default=None, alias="processedAt")
    retry_count: int = Field(default=0, alias="retryCount")
    max_retries: int = Field(default=3, alias="maxRetries")
    expires_at: datetime = Field(index=True, alias="expiresAt")
    last_error: Optional[str] = Field(default=None, alias="lastError")
    status: str = Field(
        default="pending", index=True
    )  # 'pending', 'processing', 'sent', 'failed', 'expired'
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")


class JobStatus(SQLModel, table=True):
    """Job execution status tracking"""
    
    __tablename__ = "job_status"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, alias="jobId")
    status: str = Field(default="pending")  # pending, running, completed, failed, cancelled
    progress: Optional[float] = Field(default=None)  # 0.0 to 1.0
    result: Optional[str] = Field(default=None)  # JSON string or text result
    error: Optional[str] = Field(default=None)  # Error message if failed
    started_at: Optional[datetime] = Field(default=None, alias="startedAt")
    completed_at: Optional[datetime] = Field(default=None, alias="completedAt")
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")


class BlockingStats(SQLModel, table=True):
    """Blocking statistics per domain for anti-blocking system"""

    __tablename__ = "blockingstats"

    id: str = Field(primary_key=True)
    domain: str = Field(index=True, unique=True)
    total_requests: int = 0
    successful_requests: int = 0
    blocked_requests: int = 0  # 403
    rate_limited_requests: int = 0  # 429
    last_success: Optional[datetime] = Field(default=None, alias="lastSuccess")
    last_failure: Optional[datetime] = Field(default=None, alias="lastFailure")
    current_delay: float = 5.0
    circuit_breaker_state: str = "closed"
    preferred_user_agent: Optional[str] = Field(default=None, alias="preferredUserAgent")
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")
