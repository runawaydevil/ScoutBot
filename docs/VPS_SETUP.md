# VPS Setup Guide

YouTube blocks downloads from VPS/datacenter IPs. Use authenticated cookies to bypass.

## Quick Setup

### 1. Export Cookies

**Browser Extension (Recommended):**
- Chrome/Edge: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

Steps:
1. Go to https://www.youtube.com and login
2. Click extension icon → Export
3. Save as `youtube-cookies.txt`

**Alternative (yt-dlp):**
```bash
yt-dlp --cookies-from-browser chrome --cookies youtube-cookies.txt "https://www.youtube.com"
```

### 2. Transfer to VPS

```bash
scp youtube-cookies.txt user@vps-ip:/path/to/scoutbot/secrets/
```

### 3. Configure VPS

Edit `.env`:
```bash
YTDLP_AUTH_MODE=cookiefile
YTDLP_COOKIES_FILE=/secrets/youtube-cookies.txt
```

### 4. Restart

```bash
docker-compose restart scoutbot
docker-compose logs -f scoutbot | grep -i cookie
```

### 5. Test

Send to bot: `/download https://open.spotify.com/track/...`

## Troubleshooting

**Cookies file not found:**
```bash
docker-compose exec scoutbot ls -lh /secrets/
# Verify docker-compose.yml has: - ./secrets:/secrets:ro
```

**Downloads still fail:**
- Cookies may be expired - re-export fresh cookies
- Test manually:
```bash
docker-compose exec scoutbot yt-dlp \
  --cookies /secrets/youtube-cookies.txt \
  --print-json "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**Works locally but not on VPS:**
- Normal behavior - local IP is residential, VPS IP is datacenter
- Local: `YTDLP_AUTH_MODE=none`
- VPS: `YTDLP_AUTH_MODE=cookiefile`

## Cookie Refresh

Cookies last 30-90 days. Refresh when:
- Downloads fail with "Sign in to confirm you're not a bot"
- HTTP 403 errors in logs

**Refresh:**
1. Export new cookies
2. Transfer to VPS
3. Restart: `docker-compose restart scoutbot`

## Security

- Cookies are in `.gitignore` (never committed)
- Docker mount is read-only (`:ro`)
- Rotate cookies every 30-60 days
