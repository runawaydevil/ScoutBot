# System Architecture

This document describes the architecture, design patterns, and component interactions of ScoutBot.

## Overview

ScoutBot is a Python-based Telegram bot that monitors RSS feeds and delivers notifications. The system is built with asynchronous programming patterns, implements comprehensive anti-blocking mechanisms, and uses a modular service-oriented architecture.

## Technology Stack

### Core Framework
- Python 3.11: Modern Python with async/await support
- FastAPI 0.115.0: High-performance web framework for HTTP endpoints
- aiogram 3.15.0: Modern Telegram Bot API framework
- SQLModel 0.0.23: Type-safe database ORM with Pydantic integration

### Data Storage
- SQLite: Embedded database with automatic migrations
- Redis 5.0+: Optional caching layer for HTTP responses

### HTTP Client
- aiohttp 3.9.0+: Async HTTP client with session management
- feedparser 6.0.11: RSS/Atom feed parsing library

### Job Processing
- APScheduler 3.10.4: Advanced Python scheduler for background jobs

### Monitoring
- structlog 24.4.0: Structured logging with context
- psutil 5.9.8: System resource monitoring

## Application Structure

### Entry Point

The application starts from `run.py`, which:
1. Configures logging based on environment
2. Starts FastAPI server with uvicorn
3. Initializes all services on startup

### Main Application (`app/main.py`)

FastAPI application that provides:
- Health check endpoint (`/health`)
- Metrics endpoint (`/metrics`)
- Statistics endpoint (`/stats`)
- Root endpoint (`/`)

Startup sequence:
1. Initialize database
2. Initialize Redis cache
3. Initialize scheduler
4. Register background jobs
5. Initialize Telegram bot
6. Start bot polling
7. Start keep-alive service

Shutdown sequence:
1. Stop keep-alive service
2. Close bot connections
3. Stop scheduler
4. Close cache connections
5. Close database connections

### Bot Service (`app/bot.py`)

Manages Telegram bot lifecycle using aiogram:
- Bot initialization and configuration
- Command handler registration
- Message handling
- Polling management
- Health status tracking

Commands are registered in two ways:
1. Built-in commands in `_setup_handlers()`: `/start`, `/help`, `/ping`
2. External commands in `app/commands/`: `/add`, `/remove`, `/list`, etc.

### Database Layer (`app/database.py`)

SQLModel-based database service:
- Connection management
- Session handling
- Health checks
- Metrics collection

Database models are defined in `app/models/feed.py`:
- Chat: Telegram chat information
- Feed: RSS feed configuration and state
- BlockingStats: Anti-blocking statistics per domain
- QueuedMessage: Message queue entries
- ConnectionState: Service connection states
- HealthMetric: Health monitoring data

### Scheduler (`app/scheduler.py`)

APScheduler-based job management:
- Interval jobs: Feed checker (every 5 minutes)
- Interval jobs: Blocking monitor (every 60 minutes)
- Cron jobs: Stats cleanup (daily at 3 AM UTC)

Jobs are defined in `app/jobs/`:
- `feed_checker.py`: Checks all enabled feeds for new items
- `blocking_monitor.py`: Monitors anti-blocking statistics

### Feed Processing Flow

1. Scheduler triggers feed checker job every 5 minutes
2. Feed checker retrieves all enabled feeds from database
3. For each feed:
   - Check if feed interval has elapsed
   - Fetch feed via RSS service
   - Parse feed content
   - Compare items with last known item
   - Identify new items
   - Format and send notifications
   - Update feed state in database

### RSS Service (`app/services/rss_service.py`)

Core RSS fetching and parsing service:
- URL detection (RSS, Reddit, YouTube)
- HTTP request handling with anti-blocking
- Feed parsing with feedparser
- Cache management
- New item detection

Process:
1. Check if URL is Reddit/YouTube (delegate to specialized services)
2. Check circuit breaker state
3. Check cache (ETag/Last-Modified)
4. Apply rate limiting
5. Select user-agent
6. Build headers
7. Fetch feed via HTTP
8. Parse feed content
9. Convert to internal format
10. Cache results
11. Update statistics

### Anti-Blocking System

Multi-layered anti-blocking system:

#### Rate Limiter (`app/utils/rate_limiter.py`)
- Per-domain delay management
- Adaptive delays based on response codes
- Jitter application (±20%)
- Success-based delay reduction
- Failure-based delay increase (2x for 429, 3x for 403)

#### Circuit Breaker (`app/utils/circuit_breaker.py`)
- Three states: closed, open, half-open
- Failure threshold: 5 consecutive failures
- Timeout: 1 hour (increases to 24 hours max)
- Automatic recovery testing

#### User-Agent Pool (`app/utils/user_agents.py`)
- Pool of 10+ realistic browser user-agents
- Domain-aware selection
- Success rate learning per domain
- Weighted random selection (70% top performers, 30% random)

#### Session Manager (`app/utils/session_manager.py`)
- Per-domain HTTP sessions
- Automatic rotation (1 hour TTL)
- Cookie handling
- Connection pooling

#### Header Builder (`app/utils/header_builder.py`)
- Realistic browser headers
- Random Accept-Language
- Domain-specific headers (e.g., Referer for Reddit)
- Security headers (Sec-Fetch-*)

#### Blocking Stats Service (`app/services/blocking_stats_service.py`)
- Persists statistics per domain
- Tracks success rates, failures, delays
- Stores preferred user-agents
- Circuit breaker state tracking

### Reddit Integration

#### Reddit Service (`app/services/reddit_service.py`)
- URL detection and validation
- RSS URL conversion
- Feed fetching delegation

#### Reddit Fallback (`app/services/reddit_fallback.py`)
- Fallback chain implementation:
  1. Standard RSS endpoint
  2. JSON API endpoint
  3. Old Reddit RSS endpoint
- Caches successful method per subreddit
- Automatic method switching on failure

### YouTube Integration

#### YouTube Service (`app/services/youtube_service.py`)
- URL pattern detection
- Channel ID extraction
- Username/handle extraction
- RSS URL conversion
- Feed fetching delegation

### Feed Service (`app/services/feed_service.py`)

Feed management operations:
- CRUD operations
- URL validation
- Service detection (Reddit/YouTube)
- Feed state management
- Database persistence

### Content Processing

#### HTML Sanitizer (`app/utils/html_sanitizer.py`)
- Removes HTML comments
- Converts equivalent tags (`<strong>` to `<b>`)
- Removes unsupported tags
- Balances HTML tags
- Escapes HTML entities
- Plain text fallback

#### Message Formatting (`app/jobs/feed_checker.py`)
- Formats RSS items as Telegram messages
- HTML sanitization
- Description truncation (500 chars)
- Date formatting
- Link sanitization

### Caching System

#### Cache Service (`app/utils/cache.py`)
- Redis-based caching
- JSON serialization
- TTL management
- Feed caching (5 minutes)
- Metadata caching (1 hour)
- ETag/Last-Modified support

### Resilience System

#### Keep-Alive Service (`app/resilience/keep_alive.py`)
- Process health monitoring
- Heartbeat logging
- Memory monitoring
- Signal handling

#### Retry Logic (`app/resilience/retry.py`)
- Exponential backoff
- Configurable retries
- Jitter application
- Callback support

#### Telegram Circuit Breaker (`app/resilience/circuit_breaker.py`)
- Telegram-specific circuit breaker
- Connection state tracking
- Automatic recovery

## Data Flow

### Feed Check Cycle

1. Scheduler triggers feed checker job
2. Feed checker queries database for enabled feeds
3. For each feed:
   - Check last check time vs interval
   - If interval elapsed:
     - Extract domain from URL
     - Apply rate limiting (wait if needed)
     - Check circuit breaker
     - Get user-agent for domain
     - Build headers
     - Get HTTP session for domain
     - Fetch feed from URL
     - Parse feed content
     - Compare with last item ID and date
     - Identify new items
     - For each new item:
       - Format message
       - Sanitize HTML
       - Send to Telegram
     - Update feed state (last_item_id, last_notified_at, last_check)
   - Record statistics
4. Log summary

### Request Flow

1. RSS Service receives URL
2. Detect service type (RSS/Reddit/YouTube)
3. Check cache
4. Apply rate limiting
5. Check circuit breaker
6. Select user-agent
7. Build headers
8. Get HTTP session
9. Make HTTP request
10. Handle response:
    - 200: Parse and cache
    - 304: Return cached
    - 403/429: Record failure, increase delay
    - Other: Retry with backoff
11. Update statistics
12. Return parsed feed

### Notification Flow

1. New item detected
2. Format message with HTML
3. Sanitize HTML for Telegram
4. Send via bot service
5. If HTML fails, retry with plain text
6. Update feed last_notified_at
7. Log result

## Design Patterns

### Service-Oriented Architecture
- Modular services with clear responsibilities
- Dependency injection through imports
- Service interfaces through classes

### Circuit Breaker Pattern
- Prevents cascading failures
- Automatic recovery
- State management

### Repository Pattern
- Database access through service layer
- Model abstraction
- Session management

### Factory Pattern
- Service instantiation
- Configuration-based creation

### Strategy Pattern
- Multiple feed fetching strategies (RSS, Reddit, YouTube)
- Fallback chain implementation

## Database Schema

### Core Tables

- `chat`: Telegram chat information
- `feed`: RSS feed configuration and state
- `chatsettings`: Chat-specific settings
- `feedfilter`: Feed filtering rules
- `statistic`: Usage statistics
- `itemdedupe`: Item deduplication tracking

### Anti-Blocking Tables

- `blockingstats`: Per-domain blocking statistics
- `connectionstate`: Service connection states
- `healthmetric`: Health monitoring metrics

### Resilience Tables

- `queuedmessage`: Message queue entries
- `authstate`: OAuth token storage

## Error Handling

- Graceful degradation: Continue operation on non-critical errors
- Retry logic: Automatic retries with exponential backoff
- Circuit breakers: Prevent repeated failures
- Logging: Comprehensive error logging with context
- Fallbacks: Multiple strategies for feed access

## Performance Considerations

- Async/await throughout for non-blocking I/O
- Connection pooling for HTTP requests
- Caching to reduce HTTP requests
- Batch processing where possible
- Resource limits in Docker configuration
- Memory management and cleanup

## Security

- Environment variable configuration
- No hardcoded secrets
- User access control via ALLOWED_USER_ID
- Input validation and sanitization
- SQL injection prevention via ORM
- HTML sanitization for Telegram messages

## Scalability

- Stateless service design
- Database-backed state management
- Horizontal scaling possible with shared database
- Resource limits prevent resource exhaustion
- Efficient caching reduces load
