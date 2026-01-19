"""Configuration management using pydantic-settings"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator, field_validator
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Bot Configuration
    bot_token: str

    # Server Configuration
    port: int = 8916
    host: str = "0.0.0.0"

    # Database Configuration
    database_url: str = "sqlite:///./data/development.db"  # Default for development

    # Redis Configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    disable_redis: bool = False

    # Application Configuration
    environment: str = Field(default="production", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="error", description="Log level: debug, info, warning, error (default: error for production)")

    @model_validator(mode="before")
    @classmethod
    def map_node_env(cls, data: dict) -> dict:
        """Map NODE_ENV to ENVIRONMENT if ENVIRONMENT is not set"""
        if isinstance(data, dict):
            # If NODE_ENV is set but ENVIRONMENT is not, use NODE_ENV value
            if "NODE_ENV" in data and "ENVIRONMENT" not in data:
                data["ENVIRONMENT"] = data["NODE_ENV"]
            
            # Convert empty strings to None for Optional[int] fields
            # This handles cases where env vars are set but empty (e.g., ALLOWED_USER_ID=)
            # Check both uppercase (env var names) and lowercase (field names)
            optional_int_fields = [
                ("ALLOWED_USER_ID", "allowed_user_id"),
                ("TELEGRAM_API_ID", "telegram_api_id")
            ]
            for env_name, field_name in optional_int_fields:
                # Check uppercase first (from environment)
                if env_name in data:
                    value = data.get(env_name)
                    if not value or value == "" or value is None:
                        data[env_name] = None
                        # Also set lowercase version
                        data[field_name] = None
                    else:
                        # Try to convert to int, if fails set to None
                        try:
                            int_value = int(str(value).strip()) if str(value).strip() else None
                            data[env_name] = int_value
                            data[field_name] = int_value
                        except (ValueError, TypeError):
                            data[env_name] = None
                            data[field_name] = None
                # Also check lowercase (in case it's already converted)
                elif field_name in data:
                    value = data.get(field_name)
                    if not value or value == "" or value is None:
                        data[field_name] = None
                    else:
                        try:
                            data[field_name] = int(str(value).strip()) if str(value).strip() else None
                        except (ValueError, TypeError):
                            data[field_name] = None
        return data

    @model_validator(mode="after")
    def set_environment_defaults(self) -> "Settings":
        """Set environment-specific defaults for log level"""
        if self.environment == "production":
            # Production defaults - ERROR only unless explicitly set
            if self.log_level == "debug" or self.log_level == "info":
                # Keep debug/info if explicitly set via env var
                if os.getenv("LOG_LEVEL"):
                    pass  # User explicitly set it
                else:
                    # Default to error in production
                    self.log_level = "error"
            elif not os.getenv("LOG_LEVEL"):
                # Default to error in production if not explicitly set
                self.log_level = "error"

        return self

    # Access Control
    @field_validator("allowed_user_id", mode="before")
    @classmethod
    def validate_allowed_user_id(cls, v):
        """Convert empty string to None for allowed_user_id"""
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return int(v.strip()) if v.strip() else None
            except (ValueError, TypeError):
                return None
        return v
    
    allowed_user_id: Optional[int] = None

    # Reddit API Configuration
    use_reddit_api: bool = False
    use_reddit_json_fallback: bool = False
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_username: Optional[str] = None
    reddit_password: Optional[str] = None

    # Feature Flags
    feature_instagram: bool = False

    # Resilience System Configuration
    telegram_resilience_enabled: bool = True
    telegram_max_retries: int = 10
    telegram_base_delay: int = 1000
    telegram_max_delay: int = 60000
    telegram_circuit_breaker_threshold: int = 5
    telegram_circuit_breaker_timeout: int = 300000

    # Message Queue Configuration
    message_queue_enabled: bool = True
    message_queue_max_size: int = 1000
    message_queue_batch_size: int = 20
    message_queue_processing_interval: int = 5000
    message_queue_message_ttl: int = 3600000

    # Health Monitoring Configuration
    health_check_interval: int = 30000
    alert_threshold_error_rate: float = 0.1
    alert_threshold_downtime_minutes: int = 15
    alert_threshold_queue_size: int = 500

    # Job Cleanup Configuration
    job_cleanup_enabled: bool = True
    job_cleanup_interval_minutes: int = 30
    job_cleanup_thorough_interval_hours: int = 2
    job_cleanup_orphaned_threshold: int = 10

    # Advanced Settings
    max_feeds_per_chat: int = 50
    cache_ttl_minutes: int = 20
    circuit_breaker_threshold: int = 3
    min_delay_ms: int = 200000

    # Anti-blocking Configuration
    anti_block_enabled: bool = True
    anti_block_min_delay: float = 5.0
    anti_block_max_delay: float = 300.0
    anti_block_circuit_breaker_threshold: int = 5

    # Video Download Configuration
    enable_ffmpeg: bool = Field(default=False, description="Enable FFMPEG for video processing")
    enable_aria2: bool = Field(default=False, description="Enable Aria2 for downloads")
    audio_format: str = Field(default="mp3", description="Desired audio format (mp3, m4a, wav, etc.)")
    m3u8_support: bool = Field(default=False, description="Enable m3u8 link support")
    browsers: Optional[str] = Field(default=None, description="Browser for cookies (firefox, chrome, etc.)")
    tg_normal_max_size: int = Field(default=2000, description="Maximum size for Telegram uploads in MB")
    caption_url_length_limit: int = Field(default=150, description="Maximum URL length in captions")
    tmpfile_path: Optional[str] = Field(default=None, description="Path for temporary/download files")
    
    # YouTube Authentication Configuration (yt-dlp unified)
    ytdlp_auth_mode: str = Field(default="both", description="YouTube auth mode: browser, cookiefile, both, none")
    ytdlp_cookies_file: Optional[str] = Field(default=None, description="Path to YouTube cookies file")
    ytdlp_cookies_from_browser: Optional[str] = Field(default=None, description="Browser for cookies (firefox, chrome, chromium, edge, brave)")
    ytdlp_browser_profile: str = Field(default="default", description="Browser profile name (default: 'default')")
    ytdlp_firefox_container: str = Field(default="none", description="Firefox container (default: 'none')")
    ytdlp_po_token: Optional[str] = Field(default=None, description="Manual PO Token (fallback, rarely needed)")
    ytdlp_chromium_path: str = Field(default="/usr/bin/chromium", description="Path to Chromium binary for PO Token Provider")
    ytdlp_enable_po_provider: bool = Field(default=False, description="Enable automatic PO Token Provider")
    ytdlp_player_clients: str = Field(default="default,mweb", description="YouTube player clients (default: 'default,mweb')")
    ytdlp_sleep_interval: int = Field(default=6, description="Minimum sleep interval between downloads (seconds)")
    ytdlp_max_sleep_interval: int = Field(default=10, description="Maximum sleep interval between downloads (seconds)")
    ytdlp_retries: int = Field(default=5, description="Number of retries for yt-dlp")
    
    # Media Toolbox Configuration
    enable_clip: bool = Field(default=True, description="Enable /clip command")
    enable_gif: bool = Field(default=True, description="Enable /gif command")
    max_gif_size: int = Field(default=10, description="Maximum GIF size in MB")
    gif_duration_limit: int = Field(default=15, description="Maximum GIF duration in seconds")
    gif_max_video_duration: int = Field(default=900, description="Maximum source video duration in seconds for GIF generation (default: 900 = 15 minutes)")
    
    # Job System Configuration
    job_queue_backend: str = Field(default="apscheduler", description="Job queue backend (apscheduler or celery)")
    job_persistence_enabled: bool = Field(default=True, description="Enable job persistence across restarts")
    job_status_tracking: bool = Field(default=True, description="Enable job status tracking")
    
    # ImageMagick Configuration
    enable_imagemagick: bool = Field(default=True, description="Enable ImageMagick for image processing")
    enable_stickers: bool = Field(default=True, description="Enable sticker factory commands")
    enable_memes: bool = Field(default=True, description="Enable meme generator commands")
    
    # OCR Configuration
    enable_ocr: bool = Field(default=False, description="Enable OCR functionality")
    tesseract_lang: str = Field(default="por+eng", description="Tesseract language codes (e.g., por+eng)")
    
    # Webhook Configuration
    use_webhook: bool = Field(default=False, description="Enable webhook mode instead of polling")
    webhook_url: Optional[str] = Field(default=None, description="Public HTTPS URL for webhook (required if USE_WEBHOOK=true)")
    webhook_secret: Optional[str] = Field(default=None, description="Secret token for webhook verification (optional)")
    webhook_port: int = Field(default=8916, description="Port for webhook endpoint")

    # YouTube Anti-blocking Configuration
    youtube_sleep_interval: int = Field(default=3, description="Minimum sleep interval between downloads (seconds)")
    youtube_max_sleep_interval: int = Field(default=8, description="Maximum sleep interval between downloads (seconds)")
    youtube_limit_rate: str = Field(default="2M", description="Limit download rate (e.g., 2M for 2MB/s)")
    youtube_concurrent_fragments: int = Field(default=4, description="Number of concurrent fragments (lower = less aggressive)")
    youtube_player_clients: str = Field(default="web,ios,android", description="Comma-separated list of YouTube player clients to rotate")
    youtube_rotate_clients: bool = Field(default=True, description="Enable player client rotation")
    youtube_user_agent: Optional[str] = Field(default=None, description="Custom user agent string (None = use yt-dlp default)")

    # Telegram Bot API Server Configuration
    @field_validator("telegram_api_id", mode="before")
    @classmethod
    def validate_telegram_api_id(cls, v):
        """Convert empty string to None for telegram_api_id"""
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return int(v.strip()) if v.strip() else None
            except (ValueError, TypeError):
                return None
        return v
    
    telegram_api_id: Optional[int] = Field(default=None, description="Telegram API ID for Local Bot API Server")
    telegram_api_hash: Optional[str] = Field(default=None, description="Telegram API Hash for Local Bot API Server")
    telegram_bot_api_server_url: Optional[str] = Field(default=None, description="URL of local Telegram Bot API Server")
    telegram_use_local_api: bool = Field(default=False, description="Enable use of local Bot API Server (allows 2GB uploads)")
    telegram_bot_api_data_path: Optional[str] = Field(default=None, description="Path to Bot API data directory (for local mode file access)")

    # Spotify Configuration
    spotify_client_id: Optional[str] = Field(default=None, description="Spotify Client ID for API access")
    spotify_client_secret: Optional[str] = Field(default=None, description="Spotify Client Secret for API access")
    spotify_audio_format: str = Field(default="mp3", description="Audio format for Spotify downloads (mp3, m4a, opus, flac, ogg, wav)")
    spotify_bitrate: str = Field(default="128k", description="Bitrate for Spotify downloads (128k, 256k, auto, disable)")
    spotify_audio_providers: str = Field(default="youtube-music,youtube", description="Comma-separated list of audio providers (youtube-music, youtube, soundcloud, etc.)")
    spotify_lyrics_providers: str = Field(default="genius,musixmatch,azlyrics", description="Comma-separated list of lyrics providers (genius, musixmatch, azlyrics, synced)")
    spotify_enabled: bool = Field(default=True, description="Enable Spotify download functionality")


# Global settings instance
settings = Settings()


