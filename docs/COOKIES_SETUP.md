# Quick Cookies Setup Guide

## Why Cookies Are Needed

YouTube blocks downloads from VPS/datacenter IPs. Using authenticated cookies bypasses this restriction.

## Step-by-Step Setup

### 1. Export Cookies from Browser (5 minutes)

**Install Browser Extension:**
- **Chrome/Edge**: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- **Firefox**: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

**Export Cookies:**
1. Go to https://www.youtube.com and **login to your account**
2. Click the extension icon in your browser toolbar
3. Click "Export" or "Download"
4. Save file as `youtube-cookies.txt`

### 2. Transfer to VPS

**From Windows (PowerShell or Git Bash):**
```bash
scp youtube-cookies.txt root@your-vps-ip:/root/scoutbot/secrets/
```

**Or use WinSCP/FileZilla:**
- Connect to your VPS via SFTP
- Navigate to `/root/scoutbot/secrets/`
- Upload `youtube-cookies.txt`

### 3. Verify on VPS

```bash
# SSH into VPS
ssh root@your-vps-ip

# Check file exists
ls -lh /root/scoutbot/secrets/youtube-cookies.txt

# Set correct permissions
chmod 644 /root/scoutbot/secrets/youtube-cookies.txt
```

### 4. Deploy Updated Code

```bash
# On VPS
cd /root/scoutbot

# Pull latest changes
git pull origin main

# Rebuild containers
docker compose down
docker compose build --no-cache
docker compose up -d

# Check logs
docker compose logs -f scoutbot | grep -i "spotdl\|cookie"
```

**Expected log output:**
```
SpotdlWrapper initialized with ... cookie_file=configured, yt_dlp_args=configured
Using cookies file for Spotify downloads: /secrets/***cookies.txt
```

### 5. Test Download

Send to bot:
```
/download https://open.spotify.com/track/2W3kEYBdN8UTHH5GRzYvGC
```

Should work without errors!

## Troubleshooting

### "Cookies file not found"

**Check file location:**
```bash
docker compose exec scoutbot ls -lh /secrets/
```

**Verify docker-compose.yml has volume mount:**
```yaml
volumes:
  - ./secrets:/secrets:ro
```

### "YT-DLP download error" persists

**Cookies may be expired or invalid:**
1. Re-export fresh cookies from browser (logout and login again)
2. Make sure you're logged into YouTube when exporting
3. Use Netscape format (not JSON)

**Test cookies manually:**
```bash
docker compose exec scoutbot yt-dlp \
  --cookies /secrets/youtube-cookies.txt \
  --print-json \
  "https://music.youtube.com/watch?v=43e0Bv4P_3k"
```

### Cookies work locally but not on VPS

This is expected! Your local IP is residential, VPS IP is datacenter.

**Solution:**
- **Local (.env)**: `YTDLP_AUTH_MODE=none` (no cookies needed)
- **VPS (.env)**: `YTDLP_AUTH_MODE=cookiefile` (cookies required)

## Cookie Maintenance

**Refresh Schedule:**
- Cookies typically last **30-90 days**
- Set a reminder to refresh them monthly

**Signs cookies expired:**
- Downloads fail with "Sign in to confirm you're not a bot"
- HTTP 403 errors in logs

**Quick refresh:**
1. Export new cookies from browser
2. Transfer to VPS: `scp youtube-cookies.txt root@vps:/root/scoutbot/secrets/`
3. Restart: `docker compose restart scoutbot`

## Security

- ✅ Cookies are in `.gitignore` (never committed)
- ✅ Docker mount is read-only (`:ro`)
- ✅ Cookies contain session tokens (keep private)
- ✅ Rotate cookies regularly (every 30-60 days)

## Summary

1. ✅ Install browser extension
2. ✅ Export cookies from YouTube (while logged in)
3. ✅ Transfer to VPS: `secrets/youtube-cookies.txt`
4. ✅ Deploy code: `git pull && docker compose up -d --build`
5. ✅ Test download
6. ✅ Refresh cookies monthly

**That's it!** Your bot will now work on VPS with music downloads.
