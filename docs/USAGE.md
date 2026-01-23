# Usage Guide

## Basic Commands

- `/start` - Initialize bot
- `/help` - Show all commands
- `/ping` - Check bot status

## Feed Management

**Add feed:**
```
/add <name> <url>
```
Examples:
- `/add TechNews https://example.com/rss`
- `/add RedditPython https://reddit.com/r/Python`
- `/add YouTubeChannel youtube.com/@username`

**Manage feeds:**
- `/list` - List all feeds
- `/remove <name>` - Remove feed
- `/enable <name>` - Enable feed
- `/disable <name>` - Disable feed
- `/health` - Check feed health
- `/stats` - Show statistics
- `/blockstats` - Anti-blocking statistics

## Downloads

**Video/Audio:**
```
/download <url>
/download mp3 <url>
```
Supports: YouTube, Spotify (tracks/playlists/albums/artists), most yt-dlp sites

**Note:** Downloads are sent via Telegram. For cloud storage, use `/storage upload` instead.

**Direct download:**
```
/direct <url>
```

**Special platforms:**
```
/spdl <url>
```
Supports: Instagram, Pixeldrain, KrakenFiles

**Settings:**
```
/settings
```
Configure quality (High/Medium/Low) and format (Video/Audio/Document)

## Media Processing

All media commands return ZIP files.

**Video:**
- `/clip <url> <start> <duration>` - Extract segment
- `/gif <url> <start> <duration>` - Generate GIF
- `/audio <url> [format]` - Extract audio (mp3, m4a, opus, wav)
- `/compress <file>` - Compress for Telegram
- `/subs <url>` - Download subtitles

**Images:**
- `/convert <format>` - Convert format (PNG, JPG, WEBP, etc.) - batch up to 20 images
- `/sticker` - Convert to sticker
- `/meme <top> <bottom>` - Create meme
- `/ocr` - Extract text from image

## Supported Platforms

**Feeds:**
- RSS 2.0, Atom, JSON Feed
- Reddit, YouTube, Medium, Substack, Dev.to, WordPress
- Vimeo, Twitch, GitHub, GitLab, Mastodon

**Downloads:**
- YouTube, Spotify, Instagram, Pixeldrain, KrakenFiles
- Direct file URLs

## Pentaract Storage (Separate Service)

**IMPORTANT:** Pentaract Storage is a completely separate service from downloads. Commands do not mix.

**Upload files:**
```
/storage upload <url>  - Download from URL and upload to Pentaract
/storage               - Upload file (attach file to message)
```

**List files:**
```
/storage list
```

**Download file:**
```
/storage download <code>
```
Use the file code shown when uploading or listing files.

**Delete file:**
```
/storage delete <code>
```
Requires confirmation before deletion.

**View statistics:**
```
/storage stats
```
Shows total files, storage used, upload statistics, and success rate.

**File information:**
```
/storage info <code>
```
Shows file name, size, type, and upload date.

**Key Differences:**
- `/download` - Downloads and sends files via Telegram
- `/storage upload` - Downloads and uploads to Pentaract cloud storage (separate service)
- Storage commands are completely independent and do not interfere with download commands

## File Naming

- ZIP files: `scoutbot{format}.zip` (e.g., `scoutbotpng.zip`)
- Files inside: `scoutbot{num}.{extension}` (e.g., `scoutbot1.png`)

All generated files are sent as ZIP archives.

## Smart Link Detection

Paste any URL in chat - bot automatically detects and offers action buttons (Download, Audio, Clip, GIF, Info).

## Examples

```
# Add feeds
/add TechNews https://techcrunch.com/feed/
/add PythonReddit https://reddit.com/r/Python

# Download video
/download https://youtube.com/watch?v=...

# Convert to MP3
/download mp3 https://youtu.be/...

# Spotify
/download https://open.spotify.com/track/...
/download https://open.spotify.com/playlist/...

# Media processing
/clip https://youtube.com/watch?v=... 0:30 10
/gif https://youtube.com/watch?v=... 0:30 5
/convert png (with image attached)

# Pentaract Storage (if enabled)
/storage upload https://youtube.com/watch?v=...
/storage list
/storage download ABC123
/storage stats
```
