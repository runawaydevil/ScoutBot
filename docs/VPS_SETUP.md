# VPS Setup Guide - YouTube Authentication

## Problem: YouTube Blocking VPS Downloads

YouTube often blocks downloads from VPS/datacenter IPs. The solution is to use authenticated cookies.

## Solution: Configure YouTube Cookies on VPS

### Step 1: Export Cookies from Your Browser (on your local machine)

#### Option A: Using Browser Extension (Recommended)

1. Install "Get cookies.txt LOCALLY" extension:
   - **Chrome/Edge**: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
   - **Firefox**: https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/

2. Go to https://www.youtube.com and login to your account

3. Click the extension icon and click "Export" or "Download"

4. Save the file as `youtube-cookies.txt`

#### Option B: Using yt-dlp (Alternative)

```bash
# On your local Windows machine
yt-dlp --cookies-from-browser chrome --cookies youtube-cookies.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Step 2: Transfer Cookies to VPS

```bash
# From your local machine (Windows PowerShell or Git Bash)
scp youtube-cookies.txt user@your-vps-ip:/path/to/scoutbot/secrets/

# Or use WinSCP, FileZilla, or any SFTP client
```

### Step 3: Verify Cookies File on VPS

```bash
# SSH into VPS
ssh user@your-vps-ip

# Check file exists
ls -lh /path/to/scoutbot/secrets/youtube-cookies.txt

# Verify file permissions (should be readable)
chmod 644 /path/to/scoutbot/secrets/youtube-cookies.txt
```

### Step 4: Configure .env on VPS

Edit `.env` file on VPS:

```bash
# YouTube Authentication Configuration
YTDLP_AUTH_MODE=cookiefile
YTDLP_COOKIES_FILE=/secrets/youtube-cookies.txt
```

### Step 5: Restart Bot

```bash
cd /path/to/scoutbot
docker-compose restart scoutbot

# Check logs
docker-compose logs -f scoutbot | grep -i "spotdl\|cookie"
```

You should see:
```
SpotdlWrapper initialized with ... cookie_file=configured, yt_dlp_args=configured
Using cookies file for Spotify downloads: /secrets/***cookies.txt
```

### Step 6: Test Download

Send to bot:
```
/download https://open.spotify.com/track/2W3kEYBdN8UTHH5GRzYvGC
```

## Troubleshooting

### Issue 1: "Cookies file not found"

**Symptoms:**
```
Cookies file not found: /secrets/youtube-cookies.txt, proceeding without authentication
```

**Solution:**
```bash
# Check if file exists in container
docker-compose exec scoutbot ls -lh /secrets/

# If missing, check docker-compose.yml volumes:
# - ./secrets:/secrets:ro
```

### Issue 2: "YT-DLP download error" persists

**Possible causes:**
1. **Cookies expired** - Re-export fresh cookies from browser
2. **Wrong format** - Use Netscape format (not JSON)
3. **VPS IP blocked** - Try using a VPN or proxy

**Test cookies manually:**
```bash
# Test inside container
docker-compose exec scoutbot yt-dlp \
  --cookies /secrets/youtube-cookies.txt \
  --print-json \
  "https://music.youtube.com/watch?v=43e0Bv4P_3k"
```

### Issue 3: Network/DNS Issues

Run diagnostic script:
```bash
chmod +x test_vps_network.sh
./test_vps_network.sh
```

**Common fixes:**

1. **DNS not resolving:**
```bash
# Add Google DNS to /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf
```

2. **Docker DNS issues:**
```yaml
# Add to docker-compose.yml under scoutbot service:
dns:
  - 8.8.8.8
  - 8.8.4.4
```

3. **UFW blocking (unlikely but check):**
```bash
# Allow outgoing HTTPS
sudo ufw allow out 443/tcp
sudo ufw reload
```

### Issue 4: Cookies Work Locally but Not on VPS

This is normal! Your local IP is residential, VPS IP is datacenter. YouTube treats them differently.

**Solution:** Keep using cookies on VPS, disable on local:

**Local .env (Windows):**
```bash
YTDLP_AUTH_MODE=none
```

**VPS .env (Linux):**
```bash
YTDLP_AUTH_MODE=cookiefile
YTDLP_COOKIES_FILE=/secrets/youtube-cookies.txt
```

## Cookie Refresh Schedule

YouTube cookies typically last **30-90 days**. Set a reminder to refresh them.

**Signs cookies expired:**
- Downloads start failing with "Sign in to confirm you're not a bot"
- HTTP 403 errors in logs

**Quick refresh:**
1. Export new cookies from browser
2. Transfer to VPS
3. Restart bot: `docker-compose restart scoutbot`

## Alternative: Use Proxy/VPN

If cookies don't work, consider using a residential proxy:

```bash
# Add to .env
YTDLP_PROXY=http://proxy-server:port
```

Or run VPS through VPN to get residential IP.

## Security Notes

- **Never commit cookies to Git** - Already in `.gitignore`
- **Cookies contain session tokens** - Keep them private
- **Use read-only mount** - Already configured in `docker-compose.yml`
- **Rotate cookies regularly** - Every 30-60 days

## Summary

1. ✅ Export cookies from browser (local machine)
2. ✅ Transfer to VPS: `secrets/youtube-cookies.txt`
3. ✅ Configure `.env`: `YTDLP_AUTH_MODE=cookiefile`
4. ✅ Restart bot: `docker-compose restart scoutbot`
5. ✅ Test download
6. ✅ Refresh cookies every 30-60 days

## Current Configuration

The bot now supports **flexible authentication**:
- **Local (Windows)**: Works without cookies (residential IP)
- **VPS (Linux)**: Uses cookies (datacenter IP blocked by YouTube)
- **Automatic**: Checks `YTDLP_AUTH_MODE` setting and adapts

This allows the same codebase to work in both environments!
