> **Note (Music downloads on VPS):** When using the music download feature, many VPS/cloud providers are **natively blocked by YouTube/YouTube Music** (datacenter IP ranges). If you run into failures, prefer **less-known VPS providers** or run ScoutBot on a **local computer / residential connection**. We’re actively working on ways to mitigate and bypass these restrictions, but reliability may vary depending on your provider/IP reputation.

# ScoutBot v0.4 (Lispector)

<p align="center">
    <img src="https://skillicons.dev/icons?i=ts,js,py,redis" />
</p>

<p align="center">
    <img src="https://shot.1208.pro/uploads/JOj7l1k6JfTDIAyil19cZpHQbQoc6y95ykHHaVGB.png" alt="ScoutBot" width="200" height="200" />
</p>

ScoutBot - It rocks Telegram. A Swiss Army knife Telegram bot with RSS monitoring, video downloads, music downloads, and much more.

## Overview

ScoutBot is a production-ready Telegram bot built with Python that does it all - monitors RSS feeds, downloads videos from YouTube and other platforms, downloads music from Spotify, and delivers content notifications to Telegram channels. The system includes comprehensive anti-blocking mechanisms, Reddit integration, circuit breakers, video download capabilities, music download capabilities, and Docker-first deployment architecture.

Key features:
- **Universal Feed Support**: Automatic feed detection from any webpage
- **RSS Monitoring**: Multi-format support (RSS 2.0, Atom, JSON Feed 1.1)
- **Platform Support**: YouTube, Reddit, Medium, Substack, Dev.to, WordPress, Vimeo, GitHub, GitLab, Mastodon, and more
- **Real-time Notifications**: Automatic feed updates to Telegram channels
- **Video Downloads**: YouTube and other platforms via yt-dlp
- **Music Downloads**: Download music from Spotify (tracks, playlists, albums, artists)
- **MP3 Conversion**: Extract and convert video audio to MP3 format
- **Direct Downloads**: Support for direct file URLs (aria2/requests)
- **Special Downloaders**: Instagram, Pixeldrain, KrakenFiles
- **Anti-Blocking System**: Adaptive rate limiting and circuit breakers
- **Health Monitoring**: Built-in metrics and health endpoints
- **Docker-First**: Production-ready containerized deployment
- **Database Persistence**: SQLite with optional Redis caching
- **Webhook Support**: Optional webhook mode for horizontal scaling
- **Job System**: Persistent job scheduling with status tracking
- **ImageMagick Integration**: Sticker factory and meme generator
- **OCR Support**: Text extraction from images using Tesseract

## Prerequisites

- Docker and Docker Compose (recommended for production)
- Python 3.11+ (for local development)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- Redis (optional, can be disabled)

## Quick Installation

### Docker Installation (Recommended)

**Prerequisites:**
- Docker and Docker Compose installed
- Telegram Bot Token from [@BotFather](https://t.me/botfather)

**Step 1: Clone the repository**
```bash
git clone <repository-url>
cd scoutbot
```

**Step 2: Create environment file**
```bash
cp .env.example .env
```

**Step 3: Configure environment variables**
Edit `.env` and set at minimum:
```bash
BOT_TOKEN=your_telegram_bot_token_here
ENABLE_FFMPEG=true  # Required for MP3 conversion
```

**Optional but recommended settings:**
```bash
ENABLE_ARIA2=false  # Enable for faster direct downloads
AUDIO_FORMAT=m4a    # Default audio format (mp3, m4a, wav, etc.)
```

**Step 4: Start the application**
```bash
docker-compose up -d --build
```

**Step 5: Verify deployment**
```bash
# Check container status
docker-compose ps

# Check health endpoint
curl http://localhost:8916/health

# View logs
docker-compose logs -f scoutbot
```

**Step 6: Test the bot**
1. Open Telegram and find your bot
2. Send `/start` to initialize
3. Send `/ping` to verify it's responding

**Docker Services:**
- `scoutbot` - Main bot application (Python)
- `redis` - Redis cache (optional, can be disabled)
- `telegram-bot-api` - Local Telegram Bot API Server (enables 2GB uploads)

**Stopping the application:**
```bash
docker-compose down
```

**Updating the application:**
```bash
git pull
docker-compose up -d --build
```

For detailed installation instructions, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

### Local Development Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your BOT_TOKEN
```

4. Run the application:
```bash
python run.py
```

For detailed local development setup, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Basic Usage

Start a conversation with your bot on Telegram and use the following commands:

**Feed Management:**
- `/start` - Initialize the bot
- `/help` - Show available commands
- `/add <name> <url>` - Add a new RSS feed
- `/list` - List all monitored feeds
- `/stats` - Show bot statistics

**Video Download:**
- `/download <url>` - Download video from YouTube or supported sites
- `/download mp3 <url>` - Download and convert video to MP3 audio format
- `/direct <url>` - Direct download from URL
- `/spdl <url>` - Special download (Instagram, Pixeldrain, KrakenFiles)
- `/settings` - Configure download quality and format

**Media Toolbox:**
- `/clip <url> <start_time> <duration>` - Extract video segment (returns ZIP)
- `/gif <url> <start_time> <duration>` - Generate optimized GIF from video (returns ZIP)
- `/audio <url> [format] [options]` - Extract audio (mp3, m4a, opus, wav) (returns ZIP)
- `/compress <file>` - Compress video/audio for Telegram (returns ZIP)
- `/subs <url>` - Download subtitles from video (returns ZIP)
- `/frames <url> [count]` - Generate thumbnail grid from video (returns ZIP)
- `/convert <format>` - Convert image format (supports batch up to 20 images) (returns ZIP)
- `/sticker` - Convert image to Telegram sticker format (returns ZIP)
- `/meme <top_text> <bottom_text>` - Create meme from image (returns ZIP)

**Note:** All generated files are automatically compressed into ZIP archives before delivery. There is no option to receive files without ZIP compression.

**Smart Link Detection:**
- Just paste a URL in chat - the bot will automatically detect it and offer action buttons (Download, Audio, Clip, GIF, Info)

**Examples:**
```
# Add RSS feeds (automatic detection)
/add TechNews https://example.com
/add MyBlog https://myblog.com

# Add platform-specific feeds
/add MediumBlog medium.com/@username
/add SubstackNews substack.com/@author
/add DevBlog dev.to/username
/add RedditPython https://reddit.com/r/Python
/add YouTubeChannel youtube.com/@channelname
/add GitHubReleases github.com/owner/repo
/add VimeoChannel vimeo.com/user/username

# Download video
/download https://youtube.com/watch?v=...

# Download and convert to MP3
/download mp3 https://youtube.com/watch?v=...
/download mp3 https://youtu.be/dQw4w9WgXcQ

# Download from music streaming platforms
/download https://open.spotify.com/track/...
/download https://open.spotify.com/playlist/...
/download https://open.spotify.com/album/...
/download https://open.spotify.com/artist/...

# Direct download
/direct https://example.com/file.mp4
```

**MP3 Conversion:**
- Requires `ENABLE_FFMPEG=true` in `.env` (enabled by default in Docker)
- FFmpeg is pre-installed in the Docker image
- Converts video audio to MP3 format (192kbps)
- Files are sent as audio messages in Telegram

**Music Downloads:**
- Supports Spotify tracks, playlists, albums, and artists
- Downloads music from YouTube/YouTube Music based on metadata
- Configurable audio format (MP3, M4A, OPUS, FLAC, OGG, WAV)
- Configurable bitrate (128k, 256k, auto, disable)
- Playlists/albums/artists limited to 50 songs per download
- No authentication required - works out of the box

## File Naming Convention

All generated files follow a standardized naming pattern:

- **ZIP Archives**: `scoutbot{format}.zip`
  - Examples: `scoutbotpng.zip`, `scoutbotjpg.zip`, `scoutbotgif.zip`, `scoutbotmp4.zip`
  
- **Files Inside ZIP**: `scoutbot{num}.{extension}`
  - Examples: `scoutbot1.png`, `scoutbot2.jpg`, `scoutbot3.gif`, `scoutbot1.mp4`

**Important:** All generated files are always sent as ZIP archives. There is no option to receive files without ZIP compression.

## Batch Conversion

The `/convert` command supports batch processing:
- Send up to 20 images at once (as an album or multiple messages)
- All images will be converted to the specified format
- All converted images are returned in a single ZIP file with sequential numbering
- Example: Send 4 images and use `/convert png` → Receive `scoutbotpng.zip` containing `scoutbot1.png`, `scoutbot2.png`, `scoutbot3.png`, `scoutbot4.png`

For complete command reference and usage examples, see [docs/USAGE.md](docs/USAGE.md).

## Notes

- **Music Downloads**: Fully functional. Download music from Spotify and other streaming platforms.
- **YouTube Downloads**: Fully functional with anti-blocking measures.

## Documentation

- [Installation Guide](docs/INSTALLATION.md) - Comprehensive installation instructions
- [Configuration Reference](docs/CONFIGURATION.md) - Complete configuration options
- [System Architecture](docs/ARCHITECTURE.md) - Architecture and design documentation
- [Usage Guide](docs/USAGE.md) - Bot commands and usage examples
- [Operations Manual](docs/OPERATIONS.md) - Monitoring, logging, and troubleshooting
- [Development Guide](docs/DEVELOPMENT.md) - Development setup and contribution guidelines

## Technology Stack

- **Python 3.11+** - Core language
- **FastAPI** - HTTP endpoints and health checks
- **aiogram** - Telegram Bot API framework
- **SQLModel** - Database ORM (SQLite)
- **APScheduler** - Job scheduling for feed monitoring
- **aiohttp** - Async HTTP client
- **feedparser** - RSS/Atom/JSON Feed parsing
- **yt-dlp** - Video download from YouTube and other platforms
- **FFmpeg** - Video/audio processing and MP3 conversion
- **Aria2** - Multi-threaded direct downloads (optional)
- **Redis** - Caching layer (optional)
- **Docker** - Containerized deployment

## Related Projects

ScoutBot is based on and inspired by [RSS Skull Bot](https://github.com/runawaydevil/rssskull), the enterprise-grade RSS to Telegram bot that serves as the foundation for this project. RSS Skull Bot features advanced anti-blocking capabilities, comprehensive resilience systems, and production-ready architecture.

For more information about the core RSS monitoring technology, advanced anti-blocking mechanisms, or the original implementation, visit the [RSS Skull Bot repository](https://github.com/runawaydevil/rssskull).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Version: 0.4
- Author: runawaydevil
- Repository: https://github.com/runawaydevil/scoutbot

---

## 🚀 VPS/Production Deployment

When deploying to a VPS or cloud server, YouTube may block downloads from datacenter IPs.

**Symptoms:**
- Downloads work locally but fail on VPS
- Error: "YT-DLP download error" or "Sign in to confirm you're not a bot"

**Solution:**
Configure YouTube cookies authentication. See [VPS_SETUP.md](VPS_SETUP.md) for detailed instructions.

**Quick fix:**
1. Export cookies from your browser (use "Get cookies.txt LOCALLY" extension)
2. Transfer to VPS: `scp youtube-cookies.txt user@vps:/path/to/scoutbot/secrets/`
3. Configure `.env`: `YTDLP_AUTH_MODE=cookiefile`
4. Restart: `docker-compose restart scoutbot`

**Note:** Local/residential IPs typically work without authentication.

> **Disclaimer:** This project is a combination of multiple other projects and tools. The author(s) are not responsible for misuse or any unlawful use. You are solely responsible for how you run and operate this software and for complying with all applicable laws and terms of service.

*Along the shore the cloud waves break,  
The twin suns sink behind the lake,  
The shadows lengthen  
In Carcosa.*

*Strange is the night where black stars rise,  
And strange moons circle through the skies,  
But stranger still is  
Lost Carcosa.*

**Robert W. Chambers**
