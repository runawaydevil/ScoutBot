# Configuration Reference

## Required

**BOT_TOKEN** - Telegram bot token from [@BotFather](https://t.me/botfather)
```bash
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz-123456789
```

## Server

- `PORT` - HTTP server port (default: `8916`)
- `HOST` - Bind address (default: `0.0.0.0`)

## Database

- `DATABASE_URL` - SQLite connection URL
  - Docker: `file:/app/data/production.db`
  - Local: `sqlite:///./data/development.db`

## Redis

- `REDIS_HOST` - Redis hostname (default: `redis` for Docker, `localhost` for local)
- `REDIS_PORT` - Redis port (default: `6379`)
- `REDIS_PASSWORD` - Redis password (optional)
- `DISABLE_REDIS` - Disable Redis (default: `false`)

## Application

- `ENVIRONMENT` - Runtime environment: `production` or `development` (default: `production`)
- `LOG_LEVEL` - Logging level: `debug`, `info`, `warning`, `error` (default: `info`)

## Access Control

- `ALLOWED_USER_ID` - Restrict bot to specific user ID (optional, leave empty for all users)

## Video Downloads

- `ENABLE_FFMPEG` - Enable FFmpeg for video processing (default: `false`)
- `ENABLE_ARIA2` - Enable aria2 for faster downloads (default: `false`)
- `AUDIO_FORMAT` - Audio format: `mp3`, `m4a`, `opus`, `wav` (default: `mp3`)
- `M3U8_SUPPORT` - Enable HLS stream support (default: `false`)
- `TG_NORMAL_MAX_SIZE` - Max file size in MB (default: `2000`)

## YouTube Authentication

- `YTDLP_AUTH_MODE` - Auth mode: `none`, `cookiefile`, `browser`, `both` (default: `none`)
- `YTDLP_COOKIES_FILE` - Path to cookies file (default: `/secrets/youtube-cookies.txt`)
- `YTDLP_COOKIES_FROM_BROWSER` - Browser for cookies: `firefox`, `chrome`, `edge` (default: `firefox`)
- `BROWSERS` - Browser selection (optional)

## Reddit

- `USE_REDDIT_API` - Enable Reddit OAuth API (default: `false`)
- `USE_REDDIT_JSON_FALLBACK` - Enable JSON fallback (default: `false`)
- `REDDIT_CLIENT_ID` - Reddit OAuth client ID (required if `USE_REDDIT_API=true`)
- `REDDIT_CLIENT_SECRET` - Reddit OAuth client secret (required if `USE_REDDIT_API=true`)
- `REDDIT_USERNAME` - Reddit username (required if `USE_REDDIT_API=true`)
- `REDDIT_PASSWORD` - Reddit password (required if `USE_REDDIT_API=true`)

## Anti-Blocking

- `ANTI_BLOCK_ENABLED` - Enable anti-blocking system (default: `true`)
- `ANTI_BLOCK_MIN_DELAY` - Minimum delay in seconds (default: `5.0`)
- `ANTI_BLOCK_MAX_DELAY` - Maximum delay in seconds (default: `300.0`)
- `ANTI_BLOCK_CIRCUIT_BREAKER_THRESHOLD` - Failures before circuit opens (default: `5`)

## Telegram Resilience

- `TELEGRAM_RESILIENCE_ENABLED` - Enable resilience system (default: `true`)
- `TELEGRAM_MAX_RETRIES` - Max retry attempts (default: `10`)
- `TELEGRAM_BASE_DELAY` - Base retry delay in ms (default: `1000`)
- `TELEGRAM_MAX_DELAY` - Max retry delay in ms (default: `60000`)
- `TELEGRAM_CIRCUIT_BREAKER_THRESHOLD` - Circuit breaker threshold (default: `5`)
- `TELEGRAM_CIRCUIT_BREAKER_TIMEOUT` - Circuit breaker timeout in ms (default: `300000`)

## Message Queue

- `MESSAGE_QUEUE_ENABLED` - Enable message queuing (default: `true`)
- `MESSAGE_QUEUE_MAX_SIZE` - Max queue size (default: `1000`)
- `MESSAGE_QUEUE_BATCH_SIZE` - Batch size (default: `20`)
- `MESSAGE_QUEUE_PROCESSING_INTERVAL` - Processing interval in ms (default: `5000`)
- `MESSAGE_QUEUE_MESSAGE_TTL` - Message TTL in ms (default: `3600000`)

## Features

- `FEATURE_INSTAGRAM` - Enable Instagram integration (default: `false`)

## Pentaract Storage

Pentaract is a storage system that splits files into chunks and stores them in Telegram, providing unlimited storage without local disk usage.

**Required when enabled:**
- `PENTARACT_ENABLED` - Enable Pentaract integration (default: `false`)
- `PENTARACT_API_URL` - Pentaract API base URL (default: `http://localhost:8000/api`)
- `PENTARACT_EMAIL` - Pentaract account email (required when enabled)
- `PENTARACT_PASSWORD` - Pentaract account password (required when enabled)

**Optional:**
- `PENTARACT_UPLOAD_THRESHOLD` - Minimum file size in MB for auto-upload (default: `50`)
- `PENTARACT_AUTO_CLEANUP` - Auto-delete temp files after upload (default: `true`)
- `PENTARACT_CLEANUP_INTERVAL` - Cleanup interval in minutes (default: `30`)
- `PENTARACT_MAX_CONCURRENT_UPLOADS` - Max simultaneous uploads (default: `3`)
- `PENTARACT_TIMEOUT` - API request timeout in seconds (default: `30`)
- `PENTARACT_RETRY_ATTEMPTS` - Retry attempts for failed uploads (default: `3`)

**Example configuration:**
```bash
PENTARACT_ENABLED=true
PENTARACT_API_URL=http://pentaract:8000/api
PENTARACT_EMAIL=admin@example.com
PENTARACT_PASSWORD=secure_password
PENTARACT_UPLOAD_THRESHOLD=50
```

See [Pentaract Setup Guide](PENTARACT_SETUP.md) for detailed configuration instructions.
