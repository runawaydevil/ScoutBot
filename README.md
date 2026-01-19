> **Note (Music downloads on VPS):** When using the music download feature, many VPS/cloud providers are **natively blocked by YouTube/YouTube Music** (datacenter IP ranges). If you run into failures, prefer **less-known VPS providers** or run ScoutBot on a **local computer / residential connection**. We're actively working on ways to mitigate and bypass these restrictions, but reliability may vary depending on your provider/IP reputation.

# ScoutBot v0.4 (Lispector)

<p align="center">
    <img src="https://skillicons.dev/icons?i=ts,js,py,redis" />
</p>

<p align="center">
    <img src="https://shot.1208.pro/uploads/JOj7l1k6JfTDIAyil19cZpHQbQoc6y95ykHHaVGB.png" alt="ScoutBot" width="200" height="200" />
</p>

Telegram bot for RSS monitoring, video/music downloads, and media processing.

## Quick Start

```bash
git clone <repository-url>
cd scoutbot
cp .env.example .env
# Edit .env: set BOT_TOKEN
docker-compose up -d --build
```

## Features

- RSS feed monitoring (RSS 2.0, Atom, JSON Feed)
- Platform support: YouTube, Reddit, Medium, Substack, Dev.to, WordPress, Vimeo, GitHub, GitLab, Mastodon
- Video downloads (YouTube and other platforms)
- Music downloads (Spotify tracks, playlists, albums, artists)
- Media processing (clip, GIF, audio extraction, compression, subtitles)
- Image tools (convert, sticker, meme, OCR)
- Anti-blocking system with rate limiting and circuit breakers

## Installation

**Docker (Recommended):**
```bash
docker-compose up -d --build
```

**Local:**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for details.

## Basic Commands

**Feeds:**
- `/add <name> <url>` - Add RSS feed
- `/list` - List feeds
- `/remove <name>` - Remove feed
- `/stats` - Show statistics

**Downloads:**
- `/download <url>` - Download video
- `/download mp3 <url>` - Convert to MP3
- `/direct <url>` - Direct download
- `/spdl <url>` - Instagram/Pixeldrain/KrakenFiles

**Media:**
- `/clip <url> <start> <duration>` - Extract segment
- `/gif <url> <start> <duration>` - Generate GIF
- `/audio <url> [format]` - Extract audio
- `/convert <format>` - Convert images (batch up to 20)
- `/sticker` - Convert to sticker
- `/meme <top> <bottom>` - Create meme

See [docs/USAGE.md](docs/USAGE.md) for complete command reference.

## Configuration

Required: `BOT_TOKEN` from [@BotFather](https://t.me/botfather)

Optional: See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all options.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Usage Guide](docs/USAGE.md)
- [Configuration](docs/CONFIGURATION.md)
- [VPS Setup](docs/VPS_SETUP.md)
- [Architecture](docs/ARCHITECTURE.md)

## Technology Stack

Python 3.11+, FastAPI, aiogram, SQLModel, APScheduler, yt-dlp, FFmpeg, Redis, Docker

## License

MIT License - see [LICENSE](LICENSE)

---

## 🚀 VPS/Production Deployment

When deploying to a VPS or cloud server, YouTube may block downloads from datacenter IPs.

**Symptoms:**
- Downloads work locally but fail on VPS
- Error: "YT-DLP download error" or "Sign in to confirm you're not a bot"

**Solution:**
Configure YouTube cookies authentication. See [docs/VPS_SETUP.md](docs/VPS_SETUP.md) for detailed instructions.

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
