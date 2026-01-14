# System Architecture

## Overview

ScoutBot is a Python-based Telegram bot with modular service-oriented architecture, built for RSS monitoring, video/music downloads, and media processing.

## Technology Stack

- **Python 3.11+** - Core language
- **FastAPI** - HTTP endpoints and health checks
- **aiogram** - Telegram Bot API framework
- **SQLModel** - Database ORM (SQLite)
- **APScheduler** - Job scheduling
- **aiohttp** - Async HTTP client
- **feedparser** - RSS/Atom/JSON Feed parsing
- **yt-dlp** - Video downloads
- **FFmpeg** - Media processing
- **Redis** - Caching (optional)

## Core Components

### Application Entry (`run.py`)
- Configures logging
- Starts FastAPI server
- Initializes services

### Main Application (`app/main.py`)
- FastAPI endpoints: `/health`, `/metrics`, `/stats`
- Service initialization and lifecycle management
- Job scheduling

### Bot Service (`app/bot.py`)
- Telegram bot lifecycle
- Command handlers
- Message processing

### Database (`app/database.py`)
- SQLite with WAL mode
- Connection pooling
- Models: Feed, Chat, BlockingStats, etc.

### Scheduler (`app/scheduler.py`)
- Background job management
- Feed checking (every 10 minutes)
- Statistics monitoring (every 120 minutes)
- Temp file cleanup (every 120 minutes)

### Services

**RSS Service** (`app/services/rss_service.py`)
- Feed fetching and parsing
- Platform detection (Reddit, YouTube, etc.)
- Cache management

**Download Services** (`app/downloaders/`)
- YouTube/Spotify downloads
- Direct file downloads
- Special platforms (Instagram, Pixeldrain, etc.)

**Anti-Blocking** (`app/utils/rate_limiter.py`, `app/resilience/`)
- Rate limiting per domain
- Circuit breakers
- User-agent rotation
- Session management

## Data Flow

1. **Feed Monitoring:**
   - Scheduler triggers feed checker
   - RSS service fetches and parses feeds
   - New items detected and sent to Telegram

2. **Downloads:**
   - User sends download command
   - Downloader service processes URL
   - File downloaded and uploaded to Telegram

3. **Media Processing:**
   - User sends media command
   - FFmpeg processes file
   - Result compressed to ZIP and sent

## Key Features

- **Modular Design** - Services are independent and testable
- **Async/Await** - Non-blocking I/O operations
- **Anti-Blocking** - Adaptive rate limiting and circuit breakers
- **Caching** - Redis for feed responses
- **Error Handling** - Comprehensive retry logic and resilience
- **Resource Optimization** - Memory limits, connection pooling, log rotation
