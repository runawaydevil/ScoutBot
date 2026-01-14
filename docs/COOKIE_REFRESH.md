# YouTube Cookie Refresh Guide

This document explains how to configure and refresh YouTube cookies to avoid blocking.

## Why are cookies necessary?

YouTube may block downloads when it detects automated behavior. Valid cookies help to:
- Reduce blocks from "Sign in to confirm you're not a bot"
- Access restricted content
- Improve download success rate

## Authentication Methods

The system supports two main methods:

### 1. Browser Cookies (Recommended)

**Advantages:**
- Always automatically updated
- More reliable than file-based cookies
- Works better on VPS

**Configuration:**
```bash
YTDLP_AUTH_MODE=browser
YTDLP_COOKIES_FROM_BROWSER=firefox  # or chrome, chromium, edge, brave
YTDLP_BROWSER_PROFILE=default
```

**Requirements:**
- Browser installed on the server (Firefox, Chrome, etc.)
- Browser profile with active YouTube session

**Limitation:** Does not work in Docker without special configuration (needs virtual display).

### 2. Cookie File (Alternative)

**Advantages:**
- Works in Docker/VPS without browser
- Simpler to configure
- Portable between environments

**Disadvantages:**
- Needs to be manually renewed
- May expire/rotate

**Configuration:**
```bash
YTDLP_AUTH_MODE=cookiefile
YTDLP_COOKIES_FILE=/secrets/youtube-cookies.txt
```

### 3. Hybrid Mode (Recommended for Production)

Tries browser first, falls back to file:

```bash
YTDLP_AUTH_MODE=both
YTDLP_COOKIES_FROM_BROWSER=firefox
YTDLP_COOKIES_FILE=/secrets/youtube-cookies.txt
```

## How to Export Cookies to File

### Method 1: Browser Extension (Easiest)

**Chrome/Edge/Brave:**
1. Install the "Get cookies.txt LOCALLY" extension
2. Open an incognito/private window
3. Visit https://www.youtube.com and log in
4. Click the extension icon
5. Select "Export" → "Netscape format"
6. Save as `youtube-cookies.txt` in `secrets/`

**Firefox:**
1. Install the "cookies.txt" extension
2. Open a private window
3. Visit https://www.youtube.com and log in
4. Click the extension icon → "Export"
5. Save as `youtube-cookies.txt` in `secrets/`

### Method 2: Command Line (Advanced)

**Using yt-dlp:**
```bash
# Export cookies from Firefox
yt-dlp --cookies-from-browser firefox --print-to-file cookies youtube-cookies.txt "https://www.youtube.com"

# Export cookies from Chrome
yt-dlp --cookies-from-browser chrome --print-to-file cookies youtube-cookies.txt "https://www.youtube.com"
```

## Best Practices

### 1. Export from Incognito Window

**Why:** YouTube rotates cookies in open tabs. Exporting from an incognito window avoids this.

**Steps:**
1. Open incognito/private window
2. Log in to YouTube
3. Export cookies **immediately**
4. Close the incognito window
5. Do not open YouTube in other tabs while using the cookies

### 2. Renew Regularly

Cookies expire. Renew when:
- Downloads start failing with "Sign in to confirm you're not a bot"
- Logs show "cookies are no longer valid"
- Success rate decreases significantly

**Recommended frequency:** Every 1-2 weeks, or as needed.

### 3. Verify Valid Cookies

Test if cookies work:
```bash
# In Docker container
docker compose exec scoutbot yt-dlp --cookies /secrets/youtube-cookies.txt --dump-json "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

If it works, you'll see video metadata. If it fails, renew the cookies.

## Troubleshooting

### Error: "cookies are no longer valid"

**Cause:** Cookies were rotated or expired.

**Solution:**
1. Export new cookies following the method above
2. Replace `secrets/youtube-cookies.txt`
3. Restart the container: `docker compose restart scoutbot`

### Error: "Sign in to confirm you're not a bot"

**Possible causes:**
1. Invalid/expired cookies
2. Rate limiting (too many downloads)
3. Blocked IP

**Solutions:**
1. Renew cookies
2. Increase `YTDLP_SLEEP_INTERVAL` (e.g., 10 seconds)
3. Reduce `YOUTUBE_CONCURRENT_FRAGMENTS` (e.g., 1)
4. Use PO Token Provider (automatic when installed)

### Cookies don't work in Docker

**Check:**
1. File exists: `ls -la secrets/youtube-cookies.txt`
2. File is not empty: `wc -l secrets/youtube-cookies.txt` (should have > 10 lines)
3. Volume is mounted: `docker compose exec scoutbot ls -la /secrets/`
4. Correct permissions: file must be readable

## PO Token Provider (Automatic)

The system includes support for automatic PO Token Provider (`yt-dlp-getpot-wpc`).

**How it works:**
- Automatically installed in Docker
- Works without manual configuration
- Automatically resolves 403/enforcement cases

**Verify if it's active:**
```bash
docker compose exec scoutbot yt-dlp -v "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1 | grep -i "po token"
```

If you see "PO Token Providers: wpc...", it's working.

**Manual configuration (rare):**
If the automatic provider doesn't work, you can configure PO Token manually:
```bash
YTDLP_PO_TOKEN=web+YOUR_TOKEN_HERE
```

See the yt-dlp wiki for manual PO Token extraction instructions.

## References

- [yt-dlp Wiki: Exporting YouTube cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
- [yt-dlp Wiki: How do I pass cookies to yt-dlp?](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [yt-dlp-getpot-wpc (PO Token Provider)](https://github.com/yt-dlp/yt-dlp-getpot-wpc)
