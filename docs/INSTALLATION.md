# Installation Guide

## Prerequisites

- Docker & Docker Compose (production) or Python 3.11+ (development)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- Redis (optional, can be disabled)

## Docker Installation

```bash
git clone <repository-url>
cd scoutbot
cp .env.example .env
# Edit .env: set BOT_TOKEN
docker-compose up -d --build
```

**Verify:**
```bash
docker-compose ps
curl http://localhost:8916/health
docker-compose logs -f scoutbot
```

**Test:**
1. Open Telegram, find your bot
2. Send `/start`
3. Send `/ping`

## Local Development

```bash
git clone <repository-url>
cd scoutbot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set BOT_TOKEN, DATABASE_URL, DISABLE_REDIS=true
python run.py
```

## Configuration

**Required:**
- `BOT_TOKEN` - Telegram bot token

**Optional:**
- `ENABLE_FFMPEG=true` - Video/audio processing
- `ENABLE_ARIA2=false` - Faster direct downloads
- `DISABLE_REDIS=true` - Disable Redis (local dev)

See [CONFIGURATION.md](CONFIGURATION.md) for all options.

## Redis (Optional)

**Docker:** Automatically included, no setup needed.

**Local:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Start
redis-server
```

Update `.env`:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
DISABLE_REDIS=false
```

## Troubleshooting

**Containers fail to start:**
- Check Docker is running: `docker ps`
- Check port 8916 is free: `netstat -an | grep 8916`
- View logs: `docker-compose logs scoutbot`

**Bot not responding:**
- Verify `BOT_TOKEN` is correct
- Check logs for errors
- Test with `/ping` command

**Import errors (local):**
- Verify venv is activated
- Reinstall: `pip install -r requirements.txt --force-reinstall`
