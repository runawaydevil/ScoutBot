# Secrets Directory

This directory contains sensitive configuration files that should never be committed to version control.

## Files

### `youtube-cookies.txt` (Optional)

YouTube authentication cookies in Netscape format. Used for downloading age-restricted or private videos.

**Note**: For music downloads from Spotify, cookies are **NOT required**. The bot works perfectly without authentication by using YouTube's public API.

**Format**: Netscape HTTP Cookie File
```
# Netscape HTTP Cookie File
.youtube.com    TRUE    /    TRUE    1234567890    COOKIE_NAME    cookie_value
```

**How to obtain**:
1. Install a browser extension like "Get cookies.txt" or "cookies.txt"
2. Log in to YouTube in your browser
3. Export cookies using the extension
4. Save the file as `youtube-cookies.txt` in this directory

**When to use**:
- Downloading age-restricted videos
- Downloading private videos (if you have access)
- Bypassing regional restrictions

**When NOT needed**:
- Music downloads from Spotify (works without cookies)
- Public YouTube videos
- Most standard downloads

## Security

- **Never commit** files in this directory to version control
- The `.gitignore` file is configured to exclude this directory
- Keep your cookies file private and secure
- Cookies may expire and need to be refreshed periodically

## Docker Volume

In Docker deployments, this directory is mounted as a volume:
```yaml
volumes:
  - ./secrets:/secrets:ro
```

The `:ro` flag mounts it as read-only for security.

## Troubleshooting

**Problem**: Downloads failing with authentication errors
**Solution**: 
1. For Spotify downloads: No action needed, cookies are not used
2. For YouTube videos: Check if cookies file exists and is valid
3. Refresh cookies if they're expired (usually after 6-12 months)

**Problem**: "No YouTube authentication configured" warning
**Solution**: This is normal and expected. Music downloads work without authentication.

## Support

For issues or questions:
- Repository: https://github.com/runawaydevil/scoutbot
- Open an issue on GitHub
