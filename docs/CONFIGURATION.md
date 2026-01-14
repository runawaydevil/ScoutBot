# Configuration Reference

Complete reference for all configuration options available in ScoutBot.

## Environment Variables

Configuration is managed through environment variables, typically set in a `.env` file. Copy `.env.example` to `.env` and modify as needed.

## Required Configuration

### BOT_TOKEN

Telegram bot token obtained from [@BotFather](https://t.me/botfather).

Format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz-123456789`

This is the only required variable. All other settings have defaults.

Example:
```bash
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz-123456789
```

## Server Configuration

### PORT

HTTP server port number. Default: `8916`

The FastAPI server listens on this port for health checks and metrics.

Example:
```bash
PORT=8916
```

### HOST

HTTP server bind address. Default: `0.0.0.0`

Set to `127.0.0.1` to restrict access to localhost only.

Example:
```bash
HOST=0.0.0.0
```

## Database Configuration

### DATABASE_URL

SQLite database connection URL.

Production (Docker):
```bash
DATABASE_URL=file:/app/data/production.db
```

Development (Local):
```bash
DATABASE_URL=sqlite:///./data/development.db
```

The database is automatically created if it doesn't exist. Paths are relative to the application working directory.

## Redis Configuration

### REDIS_HOST

Redis server hostname. Default: `redis` (Docker) or `localhost` (local)

For Docker Compose, use service name `redis`. For local installation, use `localhost`.

Example:
```bash
REDIS_HOST=redis
```

### REDIS_PORT

Redis server port. Default: `6379`

Example:
```bash
REDIS_PORT=6379
```

### REDIS_PASSWORD

Redis authentication password. Leave empty if no password required.

Example:
```bash
REDIS_PASSWORD=your_redis_password
```

### REDIS_DB

Redis database number. Default: `0`

Example:
```bash
REDIS_DB=0
```

### DISABLE_REDIS

Disable Redis caching entirely. Set to `true` to disable, `false` to enable. Default: `false`

When disabled, the application runs without caching. Recommended for local development.

Example:
```bash
DISABLE_REDIS=false
```

## Application Configuration

### ENVIRONMENT

Runtime environment. Options: `production`, `development`. Default: `production`

Affects logging verbosity and error handling.

Example:
```bash
ENVIRONMENT=production
```

### LOG_LEVEL

Logging verbosity level. Options: `debug`, `info`, `warning`, `error`. Default: `info`

- `debug`: Verbose logging for troubleshooting
- `info`: Standard production logging (recommended)
- `warning`: Warnings and errors only
- `error`: Errors only

Example:
```bash
LOG_LEVEL=info
```

## Access Control

### ALLOWED_USER_ID

Restrict bot to respond only to specific Telegram user ID. Leave empty to allow all users.

To find your user ID:
1. Start a chat with [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send any message
3. Copy your user ID from the response

Example:
```bash
ALLOWED_USER_ID=123456789
```

## Reddit Integration

### USE_REDDIT_API

Enable Reddit OAuth API. Default: `false`

When `false`, uses RSS feeds only. When `true`, requires Reddit API credentials.

Example:
```bash
USE_REDDIT_API=false
```

### USE_REDDIT_JSON_FALLBACK

Enable Reddit JSON fallback. Default: `false`

Uses JSON API as fallback when RSS fails.

Example:
```bash
USE_REDDIT_JSON_FALLBACK=false
```

### REDDIT_CLIENT_ID

Reddit OAuth client ID. Required if `USE_REDDIT_API=true`.

Obtain from https://www.reddit.com/prefs/apps:
1. Create a "script" application
2. Copy the client ID (under the app name)

Example:
```bash
REDDIT_CLIENT_ID=abc123def456ghi789jkl
```

### REDDIT_CLIENT_SECRET

Reddit OAuth client secret. Required if `USE_REDDIT_API=true`.

Obtain from https://www.reddit.com/prefs/apps:
1. Click "edit" on your application
2. Copy the secret

Example:
```bash
REDDIT_CLIENT_SECRET=xyz789uvw456rst123opq
```

### REDDIT_USERNAME

Reddit account username. Required if `USE_REDDIT_API=true`.

Example:
```bash
REDDIT_USERNAME=your_username_here
```

### REDDIT_PASSWORD

Reddit account password. Required if `USE_REDDIT_API=true`.

If using two-factor authentication, use an app-specific password.

Example:
```bash
REDDIT_PASSWORD=your_password_here
```

## Feature Flags

### FEATURE_INSTAGRAM

Enable Instagram integration. Default: `false`

Currently experimental. Set to `true` to enable.

Example:
```bash
FEATURE_INSTAGRAM=false
```

## Telegram Resilience System

### TELEGRAM_RESILIENCE_ENABLED

Enable Telegram API resilience system. Default: `true`

When enabled, implements retry logic, circuit breakers, and message queuing for Telegram API calls.

Example:
```bash
TELEGRAM_RESILIENCE_ENABLED=true
```

### TELEGRAM_MAX_RETRIES

Maximum retry attempts for failed Telegram API calls. Default: `10`

Example:
```bash
TELEGRAM_MAX_RETRIES=10
```

### TELEGRAM_BASE_DELAY

Base retry delay in milliseconds. Default: `1000`

Retry delays increase exponentially from this base value.

Example:
```bash
TELEGRAM_BASE_DELAY=1000
```

### TELEGRAM_MAX_DELAY

Maximum retry delay in milliseconds. Default: `60000`

Retry delays will not exceed this value.

Example:
```bash
TELEGRAM_MAX_DELAY=60000
```

### TELEGRAM_CIRCUIT_BREAKER_THRESHOLD

Number of consecutive failures before circuit breaker opens. Default: `5`

Example:
```bash
TELEGRAM_CIRCUIT_BREAKER_THRESHOLD=5
```

### TELEGRAM_CIRCUIT_BREAKER_TIMEOUT

Circuit breaker timeout in milliseconds. Default: `300000` (5 minutes)

Example:
```bash
TELEGRAM_CIRCUIT_BREAKER_TIMEOUT=300000
```

## Message Queue Configuration

### MESSAGE_QUEUE_ENABLED

Enable message queuing during Telegram API downtime. Default: `true`

When enabled, messages are queued if Telegram API is unavailable.

Example:
```bash
MESSAGE_QUEUE_ENABLED=true
```

### MESSAGE_QUEUE_MAX_SIZE

Maximum number of queued messages. Default: `1000`

When queue is full, new messages are dropped.

Example:
```bash
MESSAGE_QUEUE_MAX_SIZE=1000
```

### MESSAGE_QUEUE_BATCH_SIZE

Number of messages to process per batch. Default: `20`

Example:
```bash
MESSAGE_QUEUE_BATCH_SIZE=20
```

### MESSAGE_QUEUE_PROCESSING_INTERVAL

Interval between queue processing attempts in milliseconds. Default: `5000`

Example:
```bash
MESSAGE_QUEUE_PROCESSING_INTERVAL=5000
```

### MESSAGE_QUEUE_MESSAGE_TTL

Message time-to-live in milliseconds. Default: `3600000` (1 hour)

Messages older than this are discarded.

Example:
```bash
MESSAGE_QUEUE_MESSAGE_TTL=3600000
```

## Health Monitoring Configuration

### HEALTH_CHECK_INTERVAL

Health check interval in milliseconds. Default: `30000` (30 seconds)

Example:
```bash
HEALTH_CHECK_INTERVAL=30000
```

### ALERT_THRESHOLD_ERROR_RATE

Error rate threshold for alerts (0.0 to 1.0). Default: `0.1` (10%)

Example:
```bash
ALERT_THRESHOLD_ERROR_RATE=0.1
```

### ALERT_THRESHOLD_DOWNTIME_MINUTES

Downtime threshold in minutes before alert. Default: `15`

Example:
```bash
ALERT_THRESHOLD_DOWNTIME_MINUTES=15
```

### ALERT_THRESHOLD_QUEUE_SIZE

Queue size threshold for alerts. Default: `500`

Example:
```bash
ALERT_THRESHOLD_QUEUE_SIZE=500
```

## Job Cleanup Configuration

### JOB_CLEANUP_ENABLED

Enable automatic job cleanup. Default: `true`

Example:
```bash
JOB_CLEANUP_ENABLED=true
```

### JOB_CLEANUP_INTERVAL_MINUTES

Job cleanup interval in minutes. Default: `30`

Example:
```bash
JOB_CLEANUP_INTERVAL_MINUTES=30
```

### JOB_CLEANUP_THOROUGH_INTERVAL_HOURS

Thorough cleanup interval in hours. Default: `2`

Example:
```bash
JOB_CLEANUP_THOROUGH_INTERVAL_HOURS=2
```

### JOB_CLEANUP_ORPHANED_THRESHOLD

Threshold for orphaned job detection. Default: `10`

Example:
```bash
JOB_CLEANUP_ORPHANED_THRESHOLD=10
```

## Anti-Blocking System Configuration

### ANTI_BLOCK_ENABLED

Enable anti-blocking features. Default: `true`

When enabled, implements rate limiting, user-agent rotation, and circuit breakers.

Example:
```bash
ANTI_BLOCK_ENABLED=true
```

### ANTI_BLOCK_MIN_DELAY

Minimum delay between requests to same domain in seconds. Default: `5.0`

Example:
```bash
ANTI_BLOCK_MIN_DELAY=5.0
```

### ANTI_BLOCK_MAX_DELAY

Maximum delay between requests to same domain in seconds. Default: `300.0`

Example:
```bash
ANTI_BLOCK_MAX_DELAY=300.0
```

### ANTI_BLOCK_CIRCUIT_BREAKER_THRESHOLD

Number of consecutive failures before circuit breaker activates. Default: `5`

Example:
```bash
ANTI_BLOCK_CIRCUIT_BREAKER_THRESHOLD=5
```

## Configuration Examples

### Production Configuration

```bash
BOT_TOKEN=your_telegram_bot_token_here
ENVIRONMENT=production
LOG_LEVEL=info
DATABASE_URL=file:/app/data/production.db
REDIS_HOST=redis
REDIS_PORT=6379
DISABLE_REDIS=false
ANTI_BLOCK_ENABLED=true
ANTI_BLOCK_MIN_DELAY=10.0
ALLOWED_USER_ID=123456789
```

### Development Configuration

```bash
BOT_TOKEN=your_telegram_bot_token_here
ENVIRONMENT=development
LOG_LEVEL=debug
DATABASE_URL=sqlite:///./data/development.db
DISABLE_REDIS=true
ANTI_BLOCK_ENABLED=true
ANTI_BLOCK_MIN_DELAY=5.0
```

### Minimal Configuration

```bash
BOT_TOKEN=your_telegram_bot_token_here
```

All other settings use defaults.

## Security Considerations

1. Never commit `.env` file to version control
2. Use strong values for sensitive tokens
3. Restrict `ALLOWED_USER_ID` in production
4. Use Redis password in production
5. Set `ENVIRONMENT=production` in production
6. Use `LOG_LEVEL=info` or higher in production

## Performance Tuning

### Rate Limiting

Increase delays for aggressive rate limiting:
```bash
ANTI_BLOCK_MIN_DELAY=10.0
ANTI_BLOCK_MAX_DELAY=600.0
```

### Circuit Breaker

Make circuit breaker more sensitive:
```bash
ANTI_BLOCK_CIRCUIT_BREAKER_THRESHOLD=3
```

### Redis

Enable Redis for better performance:
```bash
DISABLE_REDIS=false
REDIS_HOST=redis
REDIS_PORT=6379
```

### Logging

Reduce logging overhead in production:
```bash
LOG_LEVEL=info
ENVIRONMENT=production
```

## Validation

Configuration is validated on startup. Invalid values will cause startup to fail with clear error messages. Check application logs for configuration errors.
