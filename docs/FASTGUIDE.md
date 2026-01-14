# ScoutBot v0.4 - Fast Guide

Version: 0.4  
Author: runawaydevil  
Last Updated: 2026-01-14

---

## Table of Contents

- [Basic Commands](#basic-commands)
- [Feed Management](#feed-management)
- [Video Download](#video-download)
- [Statistics & Monitoring](#statistics--monitoring)
- [Practical Examples](#practical-examples)
- [Advanced Configuration](#advanced-configuration)

---

## Basic Commands

### `/start`
**Description:** Start the bot and see welcome message with available commands.

**Usage:**
```
/start
```

**What it does:**
- Displays welcome message
- Shows list of available commands
- Checks user authorization (if `ALLOWED_USER_ID` is configured)

**Example:**
```
/start
```

---

### `/help`
**Description:** Show comprehensive help message with all available commands and examples.

**Usage:**
```
/help
```

**What it does:**
- Displays detailed help message
- Shows all commands organized by category
- Includes usage examples

**Example:**
```
/help
```

---

### `/ping`
**Description:** Check if the bot is alive and responding.

**Usage:**
```
/ping
```

**Response:**
```
Pong! Bot is alive and running.
```

**Example:**
```
/ping
```

---

## Feed Management

### `/list`
**Description:** List all RSS feeds configured for the current chat.

**Usage:**
```
/list
```

**What it does:**
- Shows all feeds for the current chat
- Displays feed status (enabled / disabled)
- Shows feed name and URL

**Response Format:**
```
Your RSS Feeds (3):

1. Enabled MyFeed
https://example.com/rss

2. Disabled AnotherFeed
https://reddit.com/r/subreddit
```

**Example:**
```
/list
```

**Error Messages:**
- `No feeds configured.` - No feeds found, use `/add` to add one

---

### `/add`
**Description:** Add a new RSS feed to monitor.

**Usage:**
```
/add <name> <url>
```

**Parameters:**
- `<name>` (required) - Name for the feed (can contain spaces)
- `<url>` (required) - RSS feed URL or supported platform URL

**Supported Platforms:**
- Standard RSS feeds (RSS 2.0, Atom, JSON Feed 1.1)
- Reddit: `https://reddit.com/r/subreddit` or `https://reddit.com/r/subreddit/.rss`
- YouTube: `youtube.com/@username` or `youtube.com/channel/UCxxxxx`

**What it does:**
- Validates the feed URL
- Tests if the feed is accessible
- Adds the feed to the database
- Enables the feed by default

**Examples:**
```
/add TechNews https://example.com/rss
/add RedditPython https://reddit.com/r/Python
/add MyChannel youtube.com/@username
/add MyChannel youtube.com/channel/UCxxxxx
```

**Error Messages:**
- `Invalid syntax.` - Missing name or URL
- `Failed to add feed: <error>` - Feed validation failed or already exists

**Tips:**
- Use descriptive names for easy identification
- URLs can contain spaces, they will be joined automatically
- Reddit feeds work with or without `.rss` extension

---

### `/remove`
**Description:** Remove a feed from monitoring.

**Usage:**
```
/remove <name>
```

**Parameters:**
- `<name>` (required) - Exact name of the feed to remove

**What it does:**
- Removes the feed from the database
- Stops monitoring the feed
- All feed data is deleted

**Example:**
```
/remove TechNews
```

**Error Messages:**
- `Invalid syntax.` - Missing feed name
- `Failed to remove feed: Feed not found` - Feed name doesn't exist

**Tips:**
- Use `/list` to see exact feed names
- Feed names are case-sensitive

---

### `/enable`
**Description:** Enable a disabled feed to resume monitoring.

**Usage:**
```
/enable <name>
```

**Parameters:**
- `<name>` (required) - Exact name of the feed to enable

**What it does:**
- Enables the feed
- Resumes automatic monitoring
- Feed will be checked according to its interval

**Example:**
```
/enable TechNews
```

**Error Messages:**
- `Invalid syntax.` - Missing feed name
- `Failed to enable feed: Feed not found` - Feed name doesn't exist

**Tips:**
- Use `/list` to see which feeds are disabled
- Enabled feeds show "Enabled" status in `/list`

---

### `/disable`
**Description:** Disable a feed to temporarily stop monitoring.

**Usage:**
```
/disable <name>
```

**Parameters:**
- `<name>` (required) - Exact name of the feed to disable

**What it does:**
- Disables the feed
- Stops automatic monitoring
- Feed data is preserved (can be re-enabled later)

**Example:**
```
/disable TechNews
```

**Error Messages:**
- `Invalid syntax.` - Missing feed name
- `Failed to disable feed: Feed not found` - Feed name doesn't exist

**Tips:**
- Disabled feeds won't be checked or send notifications
- Use `/enable` to resume monitoring

---

### `/health`
**Description:** Check the health status of all feeds in the current chat.

**Usage:**
```
/health
```

**What it does:**
- Analyzes all feeds for the chat
- Identifies feeds with high failure rates (≥3 failures)
- Shows feed status and failure counts
- Provides recommendations

**Response Format:**
```
Feed Health Report

Problem Feeds:
• TechNews
  URL: https://example.com/rss
  Failures: 5
  Status: Enabled

Healthy Feeds: 2

Tip: Use /remove <name> to remove problematic feeds.
```

**Example:**
```
/health
```

**Tips:**
- Feeds with 3+ failures are marked as problematic
- Consider removing or fixing problematic feeds
- Healthy feeds show no issues

---

## Image Conversion

### `/convert`
**Description:** Convert images to various formats. Supports batch processing of up to 20 images.

**Usage:**
```
/convert <format>
```

**Parameters:**
- `<format>` (required) - Target format: PNG, JPG, JPEG, WEBP, BMP, GIF, ICO

**Supported Formats:**
- PNG, JPG, JPEG, WEBP, BMP, GIF, ICO

**What it does:**
- Converts image(s) to the specified format
- Supports batch processing: send up to 20 images at once
- All converted images are returned in a single ZIP file
- Files are named `scoutbot1.{format}`, `scoutbot2.{format}`, etc.
- ZIP file is named `scoutbot{format}.zip`

**Examples:**
```
# Single image conversion
/convert png (with image attached)

# Batch conversion (send multiple images)
Send 4 images → /convert jpg
Result: scoutbotjpg.zip containing scoutbot1.jpg, scoutbot2.jpg, scoutbot3.jpg, scoutbot4.jpg
```

**Error Messages:**
- `Invalid syntax.` - Missing format parameter
- `Unsupported format: <format>` - Format not supported
- `No image attached.` - No image found in message or reply

**Tips:**
- Works with images attached to message or as reply
- Batch conversion: send up to 20 images, all will be converted
- All files are returned in ZIP format (mandatory)

---

## Video Download

### `/download`
**Description:** Download video from YouTube or other supported sites using yt-dlp. Can also convert videos to MP3 audio format.

**Usage:**
```
/download <url>
/download mp3 <url>
```

**Parameters:**
- `<url>` (required) - URL of the video to download
- `mp3` (optional) - Convert video to MP3 audio format instead of downloading video

**Supported Platforms:**
- YouTube (youtube.com, youtu.be)
- Most sites supported by yt-dlp
- Works with user quality/format settings from `/settings`

**What it does:**
- Downloads video using yt-dlp
- Applies user quality and format preferences
- Shows download progress
- Uploads to Telegram
- Uses anti-blocking mechanisms
- **With `mp3` parameter:** Extracts audio and converts to MP3 format

**Examples:**
```
/download https://youtube.com/watch?v=dQw4w9WgXcQ
/download https://youtu.be/dQw4w9WgXcQ
/download https://example.com/video.mp4
/download mp3 https://youtube.com/watch?v=dQw4w9WgXcQ
/download MP3 https://youtu.be/dQw4w9WgXcQ
```

**Error Messages:**
- `Invalid URL.` - URL format is invalid
- `FFmpeg not available or disabled.` - MP3 conversion requires FFmpeg (install FFmpeg and set ENABLE_FFMPEG=true)
- `Download failed: <error>` - Download or processing error

**Tips:**
- Configure quality/format with `/settings` before downloading
- Large videos may take time to process
- Uses FFmpeg for format conversion if enabled
- **MP3 conversion:** Requires FFmpeg installed and `ENABLE_FFMPEG=true` in configuration
- MP3 files are sent as audio messages in Telegram

---

### `/direct`
**Description:** Direct download from a URL using aria2 (if enabled) or aiohttp.

**Usage:**
```
/direct <url>
```

**Parameters:**
- `<url>` (required) - Direct download URL

**What it does:**
- Downloads file directly from URL
- Uses aria2 for multi-threaded download (if `ENABLE_ARIA2=true`)
- Falls back to aiohttp if aria2 is disabled
- Shows download progress
- Uploads to Telegram

**Examples:**
```
/direct https://example.com/file.mp4
/direct https://example.com/video.mkv
```

**Error Messages:**
- `Invalid URL.` - URL format is invalid
- `Download failed: <error>` - Download or network error

**Tips:**
- Best for direct file links
- aria2 provides faster downloads for large files
- Enable aria2 in `.env` for better performance

---

### `/spdl`
**Description:** Special download for Instagram, Pixeldrain, and KrakenFiles.

**Usage:**
```
/spdl <url>
```

**Parameters:**
- `<url>` (required) - URL from supported platform

**Supported Platforms:**
- Instagram: `instagram.com/p/...` or `threads.net/...`
- Pixeldrain: `pixeldrain.com/u/...`
- KrakenFiles: `krakenfiles.com/view/...`

**What it does:**
- Detects platform from URL
- Uses platform-specific downloader
- Extracts media links
- Downloads and uploads to Telegram

**Examples:**
```
/spdl https://instagram.com/p/ABC123xyz/
/spdl https://pixeldrain.com/u/abc123
/spdl https://krakenfiles.com/view/abc123
```

**Error Messages:**
- `Invalid URL.` - URL format is invalid
- `For YouTube links, use /download instead of /spdl` - Wrong command for YouTube
- `Unsupported URL for /spdl: <hostname>` - Platform not supported
- `Download failed: <error>` - Download failed

**Tips:**
- Instagram posts and reels are supported
- Pixeldrain requires file ID from share URL
- KrakenFiles requires view/ID from share URL

---

### `/settings`
**Description:** Configure download quality and format preferences.

**Usage:**
```
/settings
```

**What it does:**
- Shows current quality and format settings
- Displays interactive buttons to change settings
- Updates user preferences in database
- Settings apply to all future downloads

**Quality Options:**
- **High** - 1080P (best quality, larger file size)
- **Medium** - 720P (balanced quality and size)
- **Low** - 480P (smaller file size, lower quality)

**Format Options:**
- **Video** - Send as video (streamable in Telegram)
- **Audio** - Extract audio only (converts to configured format)
- **Document** - Send as document (not streamable, preserves original)

**Example:**
```
/settings
```

**Interactive Buttons:**
- Click format buttons (Document/Video/Audio) to change format
- Click quality buttons (High/Medium/Low) to change quality
- Settings update immediately

**Tips:**
- Audio format can be configured in `.env` (`AUDIO_FORMAT`)
- Document format preserves original file without Telegram compression
- Video format allows streaming in Telegram

---

## Statistics & Monitoring

### `/stats`
**Description:** Show comprehensive bot statistics for the current chat.

**Usage:**
```
/stats
```

**What it does:**
- Shows feed overview (enabled/disabled/total)
- Lists most active feeds (by last notification)
- Shows recent activity (last check, last notification)
- Displays feed health information
- Shows global statistics (all chats)

**Response Format:**
```
Bot Statistics

Your Feeds Overview
Enabled: 3 | Disabled: 1 | Total: 4

Most Active Feeds
TechNews
   Last notified: 2h ago

Recent Activity
TechNews
   Last check: 5m ago
   Last notified: 2h ago

Global Statistics
Total Feeds: 15
Total Chats: 3
```

**Example:**
```
/stats
```

**Tips:**
- Shows time ago in seconds (s), minutes (m), hours (h), or days (d)
- Most active feeds are sorted by last notification time
- Recent activity shows last check and notification times

---

### `/blockstats`
**Description:** Show anti-blocking system statistics and performance metrics.

**Usage:**
```
/blockstats
```

**What it does:**
- Shows overall request statistics
- Displays success rates per domain
- Lists circuit breaker states
- Shows rate limiting information
- Identifies domains with low success rates

**Response Format:**
```
Anti-Blocking Statistics

Overall Performance:
• Total Requests: 1250
• Success Rate: 94.5%
• Blocked (403): 45
• Rate Limited (429): 23
• Domains Tracked: 12

Top Domains:
OK reddit.com
  Success: 98.2% (245/250)
  Delay: 5.5s

WARNING example.com
  Success: 65.0% (130/200)
  Blocked: 50
  Delay: 15.2s
  Circuit: open

Circuit Breakers:
Open: 1
Testing: 0

Low Success Rate Domains:
• example.com: 65.0%
```

**Example:**
```
/blockstats
```

**Status Indicators:**
- OK - Success rate ≥ 80%
- WARNING - Success rate 50-79%
- ERROR - Success rate < 50%
- OPEN - Circuit breaker open (blocked)
- TESTING - Circuit breaker half-open (testing)

**Tips:**
- High success rates indicate good performance
- Open circuit breakers mean domain is temporarily blocked
- Low success rate domains may need configuration adjustments

---

## Practical Examples

### Example 1: Setting Up RSS Monitoring
```
1. Add a feed:
   /add TechNews https://techcrunch.com/feed/

2. Check if it's working:
   /list

3. Monitor health:
   /health
```

### Example 2: Downloading YouTube Videos
```
1. Configure settings:
   /settings
   (Select: Video format, High quality)

2. Download video:
   /download https://youtube.com/watch?v=dQw4w9WgXcQ
```

### Example 3: Managing Multiple Feeds
```
1. List all feeds:
   /list

2. Disable problematic feed:
   /disable OldFeed

3. Check statistics:
   /stats
```

### Example 4: Downloading from Instagram
```
1. Get Instagram post URL
2. Use special download:
   /spdl https://instagram.com/p/ABC123xyz/
```

### Example 5: Monitoring Reddit
```
1. Add Reddit feed:
   /add PythonReddit https://reddit.com/r/Python

2. Check health:
   /health

3. View statistics:
   /stats
```

---

## File Naming Convention

All generated files follow a standardized naming pattern:

**ZIP Archives:**
- Format: `scoutbot{format}.zip`
- Examples: `scoutbotpng.zip`, `scoutbotjpg.zip`, `scoutbotgif.zip`, `scoutbotmp4.zip`, `scoutbotmeme.zip`, `scoutbotsticker.zip`

**Files Inside ZIP:**
- Format: `scoutbot{num}.{extension}`
- Examples: `scoutbot1.png`, `scoutbot2.jpg`, `scoutbot3.gif`, `scoutbot1.mp4`

**Important Notes:**
- All generated files are **always** sent as ZIP archives
- There is **no option** to receive files without ZIP compression
- This applies to all commands that generate files: `/convert`, `/gif`, `/clip`, `/audio`, `/compress`, `/frames`, `/subs`, `/sticker`, `/meme`

**Batch Conversion Example:**
1. Send 4 images to the bot
2. Use `/convert png` as reply or command
3. Receive `scoutbotpng.zip` containing:
   - `scoutbot1.png`
   - `scoutbot2.png`
   - `scoutbot3.png`
   - `scoutbot4.png`

---

## Advanced Configuration

### Environment Variables

Key configuration options in `.env`:

**Video Download Settings:**
- `ENABLE_FFMPEG=false` - Enable FFmpeg for video processing
- `ENABLE_ARIA2=false` - Enable aria2 for faster downloads
- `AUDIO_FORMAT=m4a` - Audio format for audio-only downloads
- `M3U8_SUPPORT=false` - Enable HLS stream support
- `TG_NORMAL_MAX_SIZE=2000` - Max file size in MB for Telegram uploads
- `CAPTION_URL_LENGTH_LIMIT=150` - Max URL length in captions
- `TMPFILE_PATH=` - Path for temporary files (optional)

**Anti-Blocking Settings:**
- `ANTI_BLOCK_ENABLED=true` - Enable anti-blocking system
- `ANTI_BLOCK_MIN_DELAY=5.0` - Minimum delay between requests (seconds)
- `ANTI_BLOCK_MAX_DELAY=300.0` - Maximum delay between requests (seconds)
- `ANTI_BLOCK_CIRCUIT_BREAKER_THRESHOLD=5` - Failures before circuit opens

**YouTube Anti-Blocking:**
- `POTOKEN=` - PO Token for YouTube (optional)
- `BROWSERS=` - Browser for cookies (firefox, chrome, edge)

### Tips for Best Performance

1. **Download Settings:**
   - Enable `ENABLE_ARIA2` for faster direct downloads
   - Enable `ENABLE_FFMPEG` for video processing and thumbnails
   - Adjust `TG_NORMAL_MAX_SIZE` based on your server capacity

2. **Feed Management:**
   - Use descriptive feed names
   - Regularly check `/health` for problematic feeds
   - Disable feeds you don't need instead of removing them

3. **Anti-Blocking:**
   - Monitor `/blockstats` regularly
   - Adjust delays if you see high blocking rates
   - Use Reddit API credentials for better Reddit feed performance

4. **Download Quality:**
   - Use "High" quality for important videos
   - Use "Medium" or "Low" for faster downloads
   - "Document" format preserves original quality

---

## Troubleshooting

### Common Issues

**Feed not updating:**
- Check `/health` for feed status
- Verify feed URL is accessible
- Check if feed is enabled with `/list`

**Download fails:**
- Verify URL is correct and accessible
- Check `/blockstats` for blocking issues
- Ensure FFmpeg is installed if processing is needed

**High blocking rates:**
- Check `/blockstats` for problematic domains
- Increase `ANTI_BLOCK_MIN_DELAY` in `.env`
- Consider using Reddit API credentials

**Bot not responding:**
- Use `/ping` to check if bot is alive
- Check bot logs for errors
- Verify `BOT_TOKEN` is correct in `.env`

---

## Support

Version: 0.4  
Author: runawaydevil  
Repository: https://github.com/runawaydevil/scoutbot

For issues, feature requests, or questions, please open an issue on GitHub.

---

Last updated: 2026-01-10
