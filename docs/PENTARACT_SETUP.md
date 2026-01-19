# Pentaract Storage Setup Guide

## Overview

Pentaract is a storage system that splits files into chunks and stores them in Telegram, providing unlimited storage capacity without using local disk space. This guide covers complete setup and configuration for ScoutBot integration.

> **⚠️ IMPORTANT:** Pentaract runs as a **separate server** and must be deployed independently from ScoutBot. The `Pentaract/` folder has been removed from this repository. ScoutBot communicates with Pentaract via its REST API.

## Table of Contents

- [What is Pentaract?](#what-is-pentaract)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [User Guide](#user-guide)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## What is Pentaract?

Pentaract is a distributed storage system that:
- **Splits files** into small chunks (typically 1-2MB each)
- **Stores chunks** in Telegram channels/chats
- **Provides unlimited storage** without local disk usage
- **Manages metadata** for file reconstruction
- **Offers API access** for programmatic file management

**Benefits:**
- ✅ Unlimited storage capacity (uses Telegram's infrastructure)
- ✅ No local disk space required
- ✅ Automatic chunking and reconstruction
- ✅ RESTful API for integration
- ✅ User-level access control

**Use Cases:**
- Large video/audio file storage
- Backup and archival
- Media library management
- Reducing server disk usage

## Prerequisites

Before setting up Pentaract, ensure you have:

1. **Telegram Account** - For storing file chunks
2. **Telegram Bot Token** - Create via [@BotFather](https://t.me/botfather)
3. **Telegram API Credentials** - Get from [my.telegram.org/apps](https://my.telegram.org/apps)
4. **Docker & Docker Compose** - For running Pentaract server
5. **ScoutBot** - Already installed and running

## Installation

### Step 1: Deploy Pentaract Server

Pentaract runs as a separate service. You have two deployment options:

#### Option A: Docker Compose (Recommended)

1. **Clone Pentaract repository:**
```bash
git clone https://github.com/yourusername/pentaract.git
cd pentaract
```

2. **Configure environment:**
```bash
cp .env.example .env
nano .env
```

Required variables:
```bash
# Telegram Configuration
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Database
DATABASE_URL=postgresql://pentaract:password@postgres:5432/pentaract

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=your-secret-key-here

# Storage Configuration
DEFAULT_CHUNK_SIZE=2097152  # 2MB
MAX_FILE_SIZE=2147483648    # 2GB per file
```

3. **Start Pentaract:**
```bash
docker-compose up -d
```

4. **Verify installation:**
```bash
curl http://localhost:8000/api/health
# Should return: {"status": "healthy"}
```

#### Option B: Manual Installation

1. **Install dependencies:**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure database:**
```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb pentaract
sudo -u postgres createuser pentaract -P
```

3. **Run migrations:**
```bash
alembic upgrade head
```

4. **Start server:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 2: Create Pentaract Account

1. **Register account:**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "secure_password",
    "username": "admin"
  }'
```

2. **Verify account creation:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "secure_password"
  }'
```

You should receive an access token.

### Step 3: Configure ScoutBot

1. **Edit ScoutBot `.env` file:**
```bash
cd /path/to/scoutbot
nano .env
```

2. **Add Pentaract configuration:**
```bash
# Pentaract Storage Configuration
PENTARACT_ENABLED=true
PENTARACT_API_URL=http://pentaract:8000/api
PENTARACT_EMAIL=admin@example.com
PENTARACT_PASSWORD=secure_password
PENTARACT_UPLOAD_THRESHOLD=50
```

**Configuration explained:**
- `PENTARACT_ENABLED=true` - Enables Pentaract integration
- `PENTARACT_API_URL` - Pentaract API endpoint (use `http://pentaract:8000/api` for Docker, `http://localhost:8000/api` for local)
- `PENTARACT_EMAIL` - Your Pentaract account email
- `PENTARACT_PASSWORD` - Your Pentaract account password
- `PENTARACT_UPLOAD_THRESHOLD=50` - Files larger than 50MB auto-upload to Pentaract

3. **Restart ScoutBot:**
```bash
docker-compose restart scoutbot
```

4. **Verify integration:**
Check ScoutBot logs for successful Pentaract initialization:
```bash
docker-compose logs scoutbot | grep -i pentaract
```

You should see:
```
INFO: Pentaract storage service initialized successfully
INFO: Connected to Pentaract API at http://pentaract:8000/api
```

## Configuration

### Environment Variables

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PENTARACT_ENABLED` | Enable Pentaract integration | `true` |
| `PENTARACT_API_URL` | Pentaract API base URL | `http://pentaract:8000/api` |
| `PENTARACT_EMAIL` | Pentaract account email | `admin@example.com` |
| `PENTARACT_PASSWORD` | Pentaract account password | `secure_password` |

#### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PENTARACT_UPLOAD_THRESHOLD` | `50` | Minimum file size (MB) for auto-upload |
| `PENTARACT_AUTO_CLEANUP` | `true` | Auto-delete temp files after upload |
| `PENTARACT_CLEANUP_INTERVAL` | `30` | Cleanup interval (minutes) |
| `PENTARACT_MAX_CONCURRENT_UPLOADS` | `3` | Max simultaneous uploads |
| `PENTARACT_TIMEOUT` | `30` | API request timeout (seconds) |
| `PENTARACT_RETRY_ATTEMPTS` | `3` | Retry attempts for failed uploads |

### Upload Threshold Strategy

The `PENTARACT_UPLOAD_THRESHOLD` determines when files are automatically uploaded to Pentaract:

**Recommended values:**
- **50MB** (default) - Good balance for most use cases
- **100MB** - For faster local Telegram uploads
- **25MB** - For aggressive Pentaract usage (saves more disk space)
- **10MB** - For maximum disk space savings

**Considerations:**
- Telegram's standard API limit: 50MB per file
- Local Bot API limit: 2GB per file
- Upload time increases with file size
- Smaller threshold = more Pentaract usage = less disk space

### Storage Preferences

Users can override the automatic threshold via `/settings`:

| Preference | Behavior |
|------------|----------|
| **Auto** | Uses `PENTARACT_UPLOAD_THRESHOLD` to decide |
| **Pentaract** | All files upload to Pentaract (ignores threshold) |
| **Local** | All files use local Telegram storage (ignores threshold) |

## User Guide

### Storage Commands

#### List Files

**Command:** `/storage list [folder]`

**Examples:**
```
/storage list
/storage list downloads
/storage list downloads/youtube
```

**Output:**
```
📦 Your Pentaract Storage

Folders:
📁 downloads/
📁 music/

Files:
📄 video.mp4 (125.5 MB) - 2024-01-19
📄 song.mp3 (8.2 MB) - 2024-01-19

Total: 2 files, 133.7 MB
```

#### Download File

**Command:** `/storage download <filename>`

**Examples:**
```
/storage download video.mp4
/storage download downloads/youtube/video.mp4
```

**Process:**
1. Bot downloads file from Pentaract
2. Bot sends file to you via Telegram
3. Temporary file is automatically deleted

**Note:** Large files may take time to download and send.

#### Delete File

**Command:** `/storage delete <filename>`

**Examples:**
```
/storage delete video.mp4
/storage delete downloads/old_video.mp4
```

**Process:**
1. Bot shows confirmation dialog
2. You confirm or cancel deletion
3. File is permanently deleted from Pentaract

**Warning:** Deletion cannot be undone!

#### View Statistics

**Command:** `/storage stats`

**Output:**
```
📊 Storage Statistics

📦 Files: 15
📁 Folders: 3
💾 Total Size: 1.2 GB

📤 Uploads (24h): 5
✅ Success Rate: 98.5%
⏱️ Avg Upload Time: 12.3s
```

**Metrics explained:**
- **Files** - Total number of files in your storage
- **Folders** - Number of folders/directories
- **Total Size** - Combined size of all files
- **Uploads (24h)** - Files uploaded in last 24 hours
- **Success Rate** - Percentage of successful uploads
- **Avg Upload Time** - Average time to upload files

#### File Information

**Command:** `/storage info <filename>`

**Example:**
```
/storage info video.mp4
```

**Output:**
```
📄 File Information

Name: video.mp4
Size: 125.5 MB
Type: video/mp4
Uploaded: 2024-01-19 14:30:25
```

### Automatic Upload Behavior

When you download content with ScoutBot:

1. **File is downloaded** to temporary storage
2. **Size is checked** against threshold and user preference
3. **Decision is made:**
   - **Pentaract:** File > threshold OR user preference = "Pentaract"
   - **Local:** File ≤ threshold OR user preference = "Local"
4. **Upload occurs** to chosen destination
5. **User is notified** with file information
6. **Temp file is deleted** automatically

**Notifications:**

**Pentaract upload:**
```
⏳ Uploading to Pentaract storage...
✅ File uploaded successfully!
📦 Stored in Pentaract: video.mp4 (125.5 MB)
```

**Local upload:**
```
✅ Download complete!
📄 video.mp4 (45.2 MB)
```

**Fallback to local:**
```
⚠️ Pentaract unavailable, using local storage
✅ File sent via Telegram
```

### Fallback Strategy

ScoutBot automatically handles Pentaract failures:

**Fallback triggers:**
- Pentaract service is down
- API timeout (30 seconds)
- Authentication failure
- Network error
- Upload error

**Fallback behavior:**
1. ScoutBot detects Pentaract failure
2. Automatically switches to local Telegram storage
3. Notifies you about the fallback
4. File is sent normally via Telegram
5. Pentaract reconnection is attempted every 5 minutes

**User experience:**
- No manual intervention required
- Downloads continue working
- You're informed about storage location
- Service resumes automatically when Pentaract recovers

## Troubleshooting

### Common Issues

#### 1. "Pentaract storage is not enabled"

**Cause:** `PENTARACT_ENABLED` is not set to `true` in `.env`

**Solution:**
```bash
# Edit .env
PENTARACT_ENABLED=true

# Restart ScoutBot
docker-compose restart scoutbot
```

#### 2. "Pentaract storage service is currently unavailable"

**Causes:**
- Pentaract server is down
- Network connectivity issues
- Wrong API URL
- Authentication failure

**Solutions:**

**Check Pentaract server status:**
```bash
curl http://localhost:8000/api/health
```

**Check ScoutBot logs:**
```bash
docker-compose logs scoutbot | grep -i pentaract
```

**Verify API URL:**
```bash
# In .env, ensure correct URL
PENTARACT_API_URL=http://pentaract:8000/api  # Docker
# OR
PENTARACT_API_URL=http://localhost:8000/api  # Local
```

**Test authentication:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password"
  }'
```

#### 3. "Failed to upload file"

**Causes:**
- File too large
- Network timeout
- Insufficient storage quota
- API error

**Solutions:**

**Check file size:**
```bash
# Pentaract default max: 2GB per file
# Increase if needed in Pentaract .env:
MAX_FILE_SIZE=5368709120  # 5GB
```

**Check timeout settings:**
```bash
# In ScoutBot .env:
PENTARACT_TIMEOUT=60  # Increase to 60 seconds
```

**Check Pentaract logs:**
```bash
docker-compose logs pentaract | tail -50
```

#### 4. "Authentication failed"

**Cause:** Invalid credentials or expired token

**Solutions:**

**Verify credentials:**
```bash
# Test login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password"
  }'
```

**Reset password:**
```bash
# Via Pentaract API
curl -X POST http://localhost:8000/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com"
  }'
```

**Update ScoutBot credentials:**
```bash
# Edit .env with correct credentials
PENTARACT_EMAIL=correct_email@example.com
PENTARACT_PASSWORD=correct_password

# Restart
docker-compose restart scoutbot
```

#### 5. Slow uploads

**Causes:**
- Large file size
- Network bandwidth
- Pentaract server performance

**Solutions:**

**Increase concurrent uploads:**
```bash
# In .env:
PENTARACT_MAX_CONCURRENT_UPLOADS=5  # Default: 3
```

**Optimize chunk size:**
```bash
# In Pentaract .env:
DEFAULT_CHUNK_SIZE=4194304  # 4MB chunks (default: 2MB)
```

**Check network:**
```bash
# Test upload speed
curl -X POST http://localhost:8000/api/files/upload \
  -F "file=@test.mp4" \
  -w "Time: %{time_total}s\n"
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

**ScoutBot:**
```bash
# In .env:
LOG_LEVEL=debug

# Restart
docker-compose restart scoutbot

# View logs
docker-compose logs -f scoutbot
```

**Pentaract:**
```bash
# In Pentaract .env:
LOG_LEVEL=DEBUG

# Restart
docker-compose restart pentaract

# View logs
docker-compose logs -f pentaract
```

### Health Checks

**Check ScoutBot → Pentaract connection:**
```bash
docker-compose exec scoutbot python -c "
from app.services.pentaract_storage_service import pentaract_storage
import asyncio
print(asyncio.run(pentaract_storage.is_available()))
"
```

**Check Pentaract API:**
```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/storages
```

## Advanced Configuration

### Custom Storage Paths

Organize files in custom folders:

```python
# In downloader code
await pentaract_storage.upload_file(
    file_path=local_file,
    remote_path="downloads/youtube/video.mp4",
    folder="downloads"
)
```

### Cleanup Configuration

**Aggressive cleanup (save disk space):**
```bash
PENTARACT_AUTO_CLEANUP=true
PENTARACT_CLEANUP_INTERVAL=15  # Every 15 minutes
```

**Conservative cleanup (keep files longer):**
```bash
PENTARACT_AUTO_CLEANUP=true
PENTARACT_CLEANUP_INTERVAL=60  # Every hour
```

**Manual cleanup only:**
```bash
PENTARACT_AUTO_CLEANUP=false
```

### Performance Tuning

**High-performance setup:**
```bash
# ScoutBot .env
PENTARACT_MAX_CONCURRENT_UPLOADS=5
PENTARACT_TIMEOUT=60
PENTARACT_RETRY_ATTEMPTS=5

# Pentaract .env
DEFAULT_CHUNK_SIZE=4194304  # 4MB chunks
MAX_CONCURRENT_CHUNKS=10
```

**Low-resource setup:**
```bash
# ScoutBot .env
PENTARACT_MAX_CONCURRENT_UPLOADS=1
PENTARACT_TIMEOUT=30
PENTARACT_RETRY_ATTEMPTS=3

# Pentaract .env
DEFAULT_CHUNK_SIZE=1048576  # 1MB chunks
MAX_CONCURRENT_CHUNKS=4
```

### Network Configuration

**Docker Compose network:**
```yaml
# docker-compose.yml
services:
  scoutbot:
    networks:
      - scoutbot-network
  
  pentaract:
    networks:
      - scoutbot-network

networks:
  scoutbot-network:
    driver: bridge
```

**External Pentaract server:**
```bash
# ScoutBot .env
PENTARACT_API_URL=https://pentaract.example.com/api
```

### Security Best Practices

1. **Use strong passwords:**
```bash
# Generate secure password
openssl rand -base64 32
```

2. **Enable HTTPS for production:**
```bash
# Use reverse proxy (nginx/traefik)
PENTARACT_API_URL=https://pentaract.example.com/api
```

3. **Restrict network access:**
```yaml
# docker-compose.yml
services:
  pentaract:
    ports:
      - "127.0.0.1:8000:8000"  # Only localhost
```

4. **Use environment secrets:**
```bash
# Don't commit .env to git
echo ".env" >> .gitignore

# Use Docker secrets for production
docker secret create pentaract_password password.txt
```

5. **Regular backups:**
```bash
# Backup Pentaract database
docker-compose exec postgres pg_dump -U pentaract pentaract > backup.sql
```

### Monitoring

**Setup monitoring:**
```bash
# Check upload success rate
docker-compose exec scoutbot python -c "
from app.database import database
from app.models.pentaract_upload import PentaractUpload
from sqlmodel import select, func

with database.get_session() as session:
    total = session.exec(select(func.count(PentaractUpload.id))).first()
    success = session.exec(
        select(func.count(PentaractUpload.id))
        .where(PentaractUpload.status == 'completed')
    ).first()
    print(f'Success rate: {success/total*100:.1f}%')
"
```

**Setup alerts:**
```bash
# Monitor Pentaract availability
*/5 * * * * curl -f http://localhost:8000/api/health || echo "Pentaract down!" | mail -s "Alert" admin@example.com
```

## Additional Resources

- **Pentaract Documentation:** [https://github.com/yourusername/pentaract](https://github.com/yourusername/pentaract)
- **ScoutBot Documentation:** [README.md](../README.md)
- **Telegram Bot API:** [https://core.telegram.org/bots/api](https://core.telegram.org/bots/api)
- **Support:** Open an issue on GitHub

## FAQ

**Q: Is Pentaract free?**  
A: Yes, Pentaract is open-source. You only need a Telegram account.

**Q: How much can I store?**  
A: Unlimited, as long as you have Telegram storage space.

**Q: Can I use Pentaract without ScoutBot?**  
A: Yes, Pentaract has its own API and can be used independently.

**Q: What happens if Pentaract goes down?**  
A: ScoutBot automatically falls back to local Telegram storage.

**Q: Can I migrate existing files to Pentaract?**  
A: Not automatically, but you can re-download and upload them.

**Q: Is my data secure?**  
A: Files are stored in your Telegram account. Use HTTPS and strong passwords.

**Q: Can multiple users share Pentaract storage?**  
A: Each user has their own storage space. Files are isolated by user ID.

**Q: What's the maximum file size?**  
A: Default is 2GB per file, configurable in Pentaract settings.

---

**Need help?** Open an issue on [GitHub](https://github.com/yourusername/scoutbot/issues) or check the [troubleshooting section](#troubleshooting).
