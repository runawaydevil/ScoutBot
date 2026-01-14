# Usage Guide

Complete guide to using ScoutBot, including all available commands and feed management procedures.

## Getting Started

After installation and configuration, start a conversation with your bot on Telegram. Send the `/start` command to initialize the bot.

The bot will respond with a welcome message and list of available commands.

## Bot Commands

### Basic Commands

#### /start
Initialize the bot and display welcome message.

Usage:
```
/start
```

Response includes welcome message and basic command overview.

#### /help
Display comprehensive help message with all available commands.

Usage:
```
/help
```

Shows all commands organized by category with usage examples.

#### /ping
Verify bot connectivity and responsiveness.

Usage:
```
/ping
```

Returns "Pong! Bot is alive and running." if bot is operational.

### Feed Management Commands

#### /add
Add a new RSS feed to monitoring.

Usage:
```
/add <name> <url>
```

Parameters:
- `name`: Unique name for the feed (alphanumeric, spaces allowed)
- `url`: Feed URL (RSS, Reddit, or YouTube)

Examples:
```
/add TechNews https://example.com/rss
/add RedditPython https://reddit.com/r/Python
/add YouTubeChannel https://youtube.com/@channelname
/add MyChannel youtube.com/channel/UCxxxxx
```

The bot will:
1. Validate the URL
2. Convert Reddit/YouTube URLs to RSS format if needed
3. Fetch and verify the feed is accessible
4. Create feed entry in database
5. Confirm successful addition

If the feed already exists with the same name, you'll receive an error. Use a different name or remove the existing feed first.

#### /remove
Remove a feed from monitoring.

Usage:
```
/remove <name>
```

Parameters:
- `name`: Name of the feed to remove

Example:
```
/remove TechNews
```

Removes the feed and all associated data. This action cannot be undone.

#### /list
List all feeds configured for your chat.

Usage:
```
/list
```

Displays:
- Feed name
- Feed URL
- Enabled/disabled status
- Total number of feeds

Example output:
```
Your RSS Feeds (3):

1. Enabled TechNews
   https://example.com/rss

2. Enabled RedditPython
   https://reddit.com/r/Python

3. Disabled OldFeed
   https://oldfeed.com/rss
```

#### /enable
Enable a disabled feed.

Usage:
```
/enable <name>
```

Parameters:
- `name`: Name of the feed to enable

Example:
```
/enable OldFeed
```

Re-enables monitoring for a previously disabled feed.

#### /disable
Temporarily disable a feed without removing it.

Usage:
```
/disable <name>
```

Parameters:
- `name`: Name of the feed to disable

Example:
```
/disable TechNews
```

Disables monitoring but preserves feed configuration. Use `/enable` to re-enable.

### Information Commands

#### /health
Check health status of all feeds.

Usage:
```
/health
```

Displays:
- Feeds with high failure rates (3+ failures)
- Healthy feeds count
- Recommendations for problematic feeds

Example output:
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

#### /stats
Show bot statistics and metrics.

Usage:
```
/stats
```

Displays:
- Bot information (username, ID, polling status)
- Database statistics (total feeds, enabled/disabled counts)
- Chat count

#### /blockstats
Display anti-blocking system statistics.

Usage:
```
/blockstats
```

Shows:
- Overall performance metrics
- Per-domain statistics (top 10 by request count)
- Success rates per domain
- Circuit breaker states
- Current delays per domain
- Low success rate domains

Example output:
```
Anti-Blocking Statistics

Overall Performance:
• Total Requests: 1250
• Success Rate: 87.5%
• Blocked (403): 45
• Rate Limited (429): 112
• Domains Tracked: 8

Top Domains:
OK example.com
  Success: 95.2% (200/210)
  Delay: 5.0s

WARNING reddit.com
  Success: 65.0% (130/200)
  Blocked: 35
  Delay: 15.5s
  Circuit: open
```

### Download Commands

#### /download
Download video or audio from supported sites.

Usage:
```
/download <url>
/download mp3 <url>
```

Parameters:
- `url`: URL of the content to download
- `mp3`: Optional parameter to convert video to MP3 audio format

Supported sites:
- **YouTube**: Videos and playlists
- **Spotify**: Tracks, playlists, albums, and artists (temporarily disabled for updates)
- **Instagram/Threads**: Posts and reels
- **Pixeldrain**: Direct file downloads
- **KrakenFiles**: Direct file downloads
- **Direct URLs**: Any direct file URL

Examples:
```
/download https://youtube.com/watch?v=...
/download mp3 https://youtube.com/watch?v=...
# Spotify downloads temporarily disabled
# /download https://open.spotify.com/track/...
# /download https://open.spotify.com/playlist/...
# /download https://open.spotify.com/album/...
# /download https://open.spotify.com/artist/...
```

#### Spotify Downloads

**Note**: Spotify downloads are temporarily disabled for updates. This feature will be re-enabled in a future update.

The bot supports downloading music from Spotify via the `/download` command:

- **Track**: `/download https://open.spotify.com/track/...`
- **Playlist**: `/download https://open.spotify.com/playlist/...`
- **Album**: `/download https://open.spotify.com/album/...`
- **Artist**: `/download https://open.spotify.com/artist/...`

**Requisitos**:
- Credenciais do Spotify (SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET configurados no .env)
- FFmpeg instalado (para conversão de formatos)
- Spotify downloads habilitados (SPOTIFY_ENABLED=true)

**Notas**:
- Playlists, álbuns e artistas são limitados a 50 músicas por download
- Cada música é enviada individualmente
- O formato de saída padrão é MP3 (configurável via SPOTIFY_AUDIO_FORMAT)
- O bitrate padrão é 128k (configurável via SPOTIFY_BITRATE)

#### /settings
Configure download quality and format preferences.

Usage:
```
/settings
```

Opens an interactive menu to configure:
- **Format**: Document, Video, or Audio
- **Quality**: High (1080P), Medium (720P), or Low (480P)

Settings are saved per user and persist across sessions.

## Supported Feed Types

### Automatic Feed Detection

The bot can automatically detect feeds from any webpage by:
- Scanning HTML for `<link rel="alternate">` tags
- Trying common feed paths (`/feed`, `/rss`, `/atom.xml`, etc.)
- Supporting RSS, Atom, and JSON Feed formats

**Just provide the website URL - the bot will find the feed automatically!**

Example:
```
/add MyBlog https://example.com
```

The bot will automatically:
1. Detect feed links in the page HTML
2. Try common feed paths if no links found
3. Use the best available feed (RSS > Atom > JSON)

### RSS 2.0
Standard RSS feeds in RSS 2.0 format.

Example:
```
/add NewsFeed https://example.com/feed.rss
```

### Atom
Atom syndication format feeds.

Example:
```
/add AtomFeed https://example.com/atom.xml
```

### JSON Feed
JSON Feed 1.1 specification feeds.

Example:
```
/add JSONFeed https://example.com/feed.json
```

### Content Platforms

#### Medium
Medium publication and user feeds.

Supported formats:
- `medium.com/@username`
- `medium.com/publication-name`

Example:
```
/add MediumBlog medium.com/@username
```

#### Substack
Substack newsletter feeds.

Supported formats:
- `substack.com/@username`
- `substack.com/@username/p/...`

Example:
```
/add Newsletter substack.com/@author
```

#### Dev.to
Dev.to user feeds.

Supported formats:
- `dev.to/username`
- `dev.to/username/posts/...`

Example:
```
/add DevBlog dev.to/username
```

#### WordPress
WordPress blog feeds (auto-detected).

Supported formats:
- Any WordPress site URL
- `wordpress.com/username`

Example:
```
/add WordPressBlog https://myblog.wordpress.com
```

The bot automatically detects WordPress feeds via HTML link tags or common paths.

### Video Platforms

#### YouTube
YouTube channel feeds. Automatically converted to RSS format.

Supported formats:
- Channel ID: `youtube.com/channel/UCxxxxx`
- Handle: `youtube.com/@username`
- Handle: `@username`
- Plain channel ID: `UCxxxxx`

Examples:
```
/add TechChannel youtube.com/channel/UCxxxxx
/add MyChannel youtube.com/@username
/add ShortHandle @username
```

#### Vimeo
Vimeo user and channel feeds.

Supported formats:
- `vimeo.com/user/username`
- `vimeo.com/channels/channelname`

Example:
```
/add VimeoChannel vimeo.com/user/username
```

#### Twitch
Twitch channel feeds (via feed detection).

Note: Twitch doesn't provide native RSS feeds. The bot will attempt to detect feeds if available.

### Code Platforms

#### GitHub
GitHub repository feeds (releases, tags, commits).

Supported formats:
- `github.com/owner/repo` (automatically tries releases, tags, activity)
- Repository URLs automatically converted to feed URLs

Example:
```
/add MyRepo github.com/owner/repository
```

The bot automatically tries:
1. Releases feed (`/releases.atom`)
2. Tags feed (`/tags.atom`)
3. Activity feed (`.atom`)

#### GitLab
GitLab repository feeds (releases, tags).

Supported formats:
- `gitlab.com/owner/repo`
- `gitlab.io/username/project`

Example:
```
/add GitLabRepo gitlab.com/owner/repository
```

### Social Platforms

#### Reddit
Reddit subreddit feeds. Automatically converted to RSS format.

Supported formats:
- `https://reddit.com/r/subreddit`
- `https://www.reddit.com/r/subreddit`
- `https://reddit.com/r/subreddit/.rss`

Example:
```
/add PythonReddit https://reddit.com/r/Python
```

The bot automatically:
1. Detects Reddit URL
2. Converts to RSS format
3. Uses fallback chain if standard RSS fails
4. Handles non-chronological sorting

#### Mastodon
Mastodon instance feeds (native RSS support).

Supported formats:
- `instance.com/@username`
- `instance.com/users/username`

Example:
```
/add MastodonUser mastodon.social/@username
```

The bot automatically detects Mastodon RSS feeds via HTML link tags.

## Feed Management

### Adding Feeds

When adding a feed, the bot performs validation:
1. Automatic feed detection (if URL is a webpage)
2. Platform detection (YouTube, Reddit, Medium, etc.)
3. URL conversion to RSS format if needed
4. Feed accessibility check
5. Feed parsing verification

**Detection Order:**
1. Direct feed URL (RSS/Atom/JSON) → Fetch directly
2. Automatic HTML feed detection → Find feed links in page
3. Platform-specific service → Convert platform URL to feed
4. Generic feed fetch → Try to fetch as-is

If any step fails, you'll receive an error message with details and suggestions.

### Feed Configuration

Each feed has the following properties:
- Name: Unique identifier
- URL: Original URL (for display)
- RSS URL: Converted RSS URL (for fetching)
- Check interval: Minutes between checks (default: 10)
- Max age: Maximum age of items to notify (default: 1440 minutes / 24 hours)
- Enabled: Whether feed is actively monitored
- Last item ID: Most recent item processed
- Last notified at: Timestamp of last notification
- Last check: Timestamp of last feed check
- Failures: Consecutive failure count

### Feed Monitoring

The bot checks all enabled feeds every 5 minutes. For each feed:
1. Checks if check interval has elapsed
2. Fetches feed content
3. Compares items with last known item
4. Identifies new items
5. Sends notifications for new items
6. Updates feed state

### Notification Behavior

Notifications are sent when:
- New items are detected in the feed
- Item publication date is newer than last notification time
- Item age is within max_age_minutes limit
- Feed is enabled

Notifications include:
- Feed name
- Item title
- Item description (truncated to 500 characters)
- Publication date
- Link to full content

### Feed State Management

Feed state is automatically managed:
- First check: Sets baseline to most recent post date (prevents spam)
- Subsequent checks: Compares all items with last notification date
- Failure handling: Increments failure count, may disable feed
- Success handling: Resets failure count

## Best Practices

### Feed Naming
- Use descriptive, unique names
- Avoid special characters
- Keep names short but meaningful

### URL Format
- Use full URLs with protocol (https://)
- For Reddit, use standard subreddit URLs
- For YouTube, use channel URLs or handles

### Feed Management
- Regularly check `/health` for problematic feeds
- Remove feeds that consistently fail
- Use `/disable` instead of `/remove` for temporary issues
- Monitor `/blockstats` for blocking issues

### Performance
- Limit number of feeds per chat (recommended: 50 or fewer)
- Use appropriate check intervals (default 10 minutes)
- Monitor system resources via `/stats`

## Troubleshooting

### Feed Not Adding
- Verify URL is accessible
- Check URL format is correct
- Ensure feed is valid RSS/Atom/JSON
- Check bot logs for errors

### No Notifications
- Verify feed is enabled (`/list` shows enabled status)
- Check feed has new items
- Verify last notification time
- Check feed health (`/health`)

### Feed Failures
- Check `/blockstats` for blocking issues
- Verify feed URL is still valid
- Check feed is accessible from bot server
- Review feed health status

### Reddit Feeds Not Working
- Reddit may block automated access
- Check `/blockstats` for reddit.com statistics
- Wait for circuit breaker recovery
- Consider using Reddit API (requires credentials)

### YouTube Feeds Not Working
- Verify channel ID or handle is correct
- Check channel is public
- Ensure channel has videos
- Verify YouTube RSS feed is accessible

## Command Reference Summary

| Command | Description | Parameters |
|---------|-------------|------------|
| `/start` | Initialize bot | None |
| `/help` | Show help | None |
| `/ping` | Check connectivity | None |
| `/add` | Add feed | `<name> <url>` |
| `/remove` | Remove feed | `<name>` |
| `/list` | List feeds | None |
| `/enable` | Enable feed | `<name>` |
| `/disable` | Disable feed | `<name>` |
| `/health` | Check feed health | None |
| `/stats` | Show statistics | None |
| `/blockstats` | Show blocking stats | None |
