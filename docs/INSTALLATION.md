# Installation Guide

This guide provides comprehensive installation instructions for ScoutBot in both Docker and local development environments.

## System Requirements

### Docker Installation
- Docker Engine 20.10 or later
- Docker Compose 2.0 or later
- Minimum 2GB RAM available
- Minimum 1GB disk space

### Local Development
- Python 3.11 or later
- pip package manager
- Minimum 512MB RAM
- Minimum 500MB disk space

### Required Services
- Telegram Bot Token (obtain from [@BotFather](https://t.me/botfather))
- Redis server (optional, can be disabled)

## Docker Installation

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd scoutbot
```

### Step 2: Verify Docker Installation

Verify Docker and Docker Compose are installed and running:

```bash
docker --version
docker-compose --version
docker ps
```

If Docker is not installed, follow the official installation guide for your operating system:
- Linux: https://docs.docker.com/engine/install/
- macOS: https://docs.docker.com/desktop/install/mac-install/
- Windows: https://docs.docker.com/desktop/install/windows-install/

### Step 3: Create Environment File

Copy the example environment file:

```bash
cp .env.example .env
```

### Step 4: Configure Environment Variables

Edit the `.env` file with your preferred text editor. The minimum required configuration is:

```bash
BOT_TOKEN=your_telegram_bot_token_here
```

To obtain a Telegram Bot Token:
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the token provided (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz-123456789`)
5. Paste the token as the value for `BOT_TOKEN` in your `.env` file

### Step 5: Review Docker Compose Configuration

The `docker-compose.yml` file defines two services:
- `scoutbot`: Main application container
- `redis`: Redis cache container

Default configuration:
- Application port: 8916
- Redis port: 6379
- Database volume: `app_data`
- Backups volume: `backups_data`
- Redis data volume: `redis_data`

Modify `docker-compose.yml` if you need to change ports or resource limits.

### Step 6: Build and Start Containers

Build and start all services:

```bash
docker-compose up -d --build
```

The `-d` flag runs containers in detached mode. The `--build` flag ensures images are rebuilt.

### Step 7: Verify Installation

Check container status:

```bash
docker-compose ps
```

All containers should show status "Up" and health status "healthy".

View application logs:

```bash
docker-compose logs -f scoutbot
```

Check health endpoint:

```bash
curl http://localhost:8916/health
```

Expected response includes status "ok" and service health checks.

### Step 8: Test Bot Functionality

1. Open Telegram and search for your bot by username
2. Send `/start` command
3. Verify you receive a welcome message
4. Test adding a feed: `/add TestFeed https://www.reddit.com/r/Python/.rss`

## Local Development Installation

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd scoutbot
```

### Step 2: Verify Python Version

Check Python version:

```bash
python --version
```

Must be Python 3.11 or later. If not installed, download from https://www.python.org/downloads/

### Step 3: Create Virtual Environment

Create isolated Python environment:

```bash
python -m venv venv
```

Activate virtual environment:

```bash
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

When activated, your prompt should show `(venv)` prefix.

### Step 4: Install Dependencies

Upgrade pip:

```bash
pip install --upgrade pip
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

This installs all required packages including:
- aiogram 3.15.0
- fastapi 0.115.0
- sqlmodel 0.0.23
- aiohttp 3.9.0+
- feedparser 6.0.11
- apscheduler 3.10.4
- redis 5.0.0+
- And other dependencies

### Step 5: Configure Environment

Create environment file:

```bash
cp .env.example .env
```

Edit `.env` file with your configuration. Minimum required:

```bash
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=sqlite:///./data/development.db
DISABLE_REDIS=true
ENVIRONMENT=development
LOG_LEVEL=debug
```

For local development, Redis can be disabled by setting `DISABLE_REDIS=true`.

### Step 6: Create Data Directory

Create directory for database:

```bash
mkdir -p data
```

### Step 7: Initialize Database

The database is automatically created on first run. No manual initialization required.

### Step 8: Run Application

Start the application:

```bash
python run.py
```

The application will:
- Initialize database
- Connect to Redis (if enabled)
- Start FastAPI server on port 8916
- Start Telegram bot polling
- Schedule background jobs

You should see startup logs indicating successful initialization.

### Step 9: Verify Installation

Check health endpoint:

```bash
curl http://localhost:8916/health
```

Or open in browser: http://localhost:8916/health

Test bot functionality as described in Docker installation Step 8.

## Redis Installation (Optional)

Redis is optional but recommended for production. The application can run without Redis by setting `DISABLE_REDIS=true`.

### Docker (Automatic)

Redis is automatically started with `docker-compose up`. No additional configuration needed.

### Local Installation

Install Redis:

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# Download from https://redis.io/download
```

Start Redis:

```bash
# Linux/macOS
redis-server

# Windows
redis-server.exe
```

Verify Redis is running:

```bash
redis-cli ping
```

Should return "PONG".

Update `.env`:

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
DISABLE_REDIS=false
```

## Troubleshooting

### Docker Issues

**Containers fail to start:**
- Check Docker daemon is running: `docker ps`
- Verify port 8916 is not in use: `netstat -an | grep 8916`
- Check logs: `docker-compose logs scoutbot`

**Health check fails:**
- Wait 60 seconds for initial startup period
- Check application logs: `docker-compose logs -f scoutbot`
- Verify BOT_TOKEN is set correctly

**Redis connection errors:**
- Verify Redis container is running: `docker-compose ps redis`
- Check Redis logs: `docker-compose logs redis`
- Set `DISABLE_REDIS=true` to disable Redis

### Local Development Issues

**Python version error:**
- Verify Python 3.11+: `python --version`
- Use `python3` instead of `python` if needed
- Update PATH if Python not found

**Import errors:**
- Verify virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
- Check Python path: `which python` (should point to venv)

**Database errors:**
- Verify data directory exists and is writable
- Check DATABASE_URL path is correct
- Delete database file and restart to recreate

**Bot not responding:**
- Verify BOT_TOKEN is correct
- Check bot is started: `/start` command
- Review logs for errors
- Verify internet connectivity

**Port already in use:**
- Change PORT in `.env` file
- Or stop other service using port 8916
- Check: `netstat -an | grep 8916`

## Webhook Setup (Optional)

For production deployments with multiple instances or better scalability, you can configure webhook mode instead of polling.

### Prerequisites
- Public domain with HTTPS
- SSL certificate (Let's Encrypt recommended)
- Reverse proxy (nginx)

### Configuration

1. Set webhook environment variables in `.env`:
```bash
USE_WEBHOOK=true
WEBHOOK_URL=https://yourdomain.com/webhook/YOUR_BOT_TOKEN
WEBHOOK_SECRET=your_secret_token_here  # Optional but recommended
```

2. Configure reverse proxy (nginx example):
```nginx
location /webhook/ {
    proxy_pass http://localhost:8916;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

3. Restart the application:
```bash
docker-compose restart scoutbot
```

For detailed webhook setup instructions, see [WEBHOOK.md](WEBHOOK.md).

## Next Steps

After successful installation:
1. Review [Configuration Reference](CONFIGURATION.md) for advanced settings
2. Read [Usage Guide](USAGE.md) for bot commands
3. Check [Operations Manual](OPERATIONS.md) for monitoring and maintenance
4. Configure webhook mode for production (see [WEBHOOK.md](WEBHOOK.md))