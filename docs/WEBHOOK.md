# Webhook Setup Guide

## Overview

ScoutBot supports both **polling** (default) and **webhook** modes for receiving Telegram updates. Webhook mode provides better scalability and performance for production deployments.

## Polling vs Webhook

### Polling Mode (Default)
- Bot continuously polls Telegram API for updates
- Simple setup, no additional configuration needed
- Single instance limitation
- Higher server load

### Webhook Mode
- Telegram pushes updates to your server
- Supports multiple instances (horizontal scaling)
- Lower server load
- Requires HTTPS and public URL

## Prerequisites

1. **Public Domain**: Your server must be accessible via public domain
2. **HTTPS**: Webhook URL must use HTTPS (Telegram requirement)
3. **SSL Certificate**: Valid SSL certificate (Let's Encrypt recommended)
4. **Reverse Proxy**: nginx or similar for SSL termination

## Setup Instructions

### Step 1: Configure Environment Variables

Edit your `.env` file:

```env
USE_WEBHOOK=true
WEBHOOK_URL=https://yourdomain.com/webhook/YOUR_BOT_TOKEN
WEBHOOK_SECRET=your_secret_token_here  # Optional but recommended
WEBHOOK_PORT=8916
```

**Important**: Replace `YOUR_BOT_TOKEN` with your actual bot token in the webhook URL.

### Step 2: Configure Reverse Proxy (nginx)

Example nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location /webhook/ {
        proxy_pass http://localhost:8916;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://localhost:8916;
    }
}
```

### Step 3: Set Up SSL Certificate

Using Let's Encrypt (Certbot):

```bash
sudo certbot --nginx -d yourdomain.com
```

### Step 4: Start ScoutBot

The bot will automatically:
1. Detect `USE_WEBHOOK=true`
2. Set up webhook with Telegram
3. Start receiving updates via webhook endpoint

If webhook setup fails, it will automatically fall back to polling mode.

## Verification

### Check Webhook Status

```bash
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
```

### Test Webhook Endpoint

```bash
curl -X POST https://yourdomain.com/webhook/YOUR_BOT_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"update_id": 123}'
```

## Troubleshooting

### Webhook Not Receiving Updates

1. **Check HTTPS**: Ensure webhook URL uses HTTPS
2. **Verify URL**: Check that webhook URL is correct
3. **Check Firewall**: Ensure port 8916 is accessible
4. **Review Logs**: Check bot logs for webhook errors
5. **Test Endpoint**: Verify webhook endpoint is reachable

### Fallback to Polling

If webhook setup fails, the bot automatically falls back to polling mode. Check logs for error messages.

### Multiple Instances

For multiple instances:
1. Use load balancer (nginx, HAProxy)
2. Configure sticky sessions (optional)
3. Ensure all instances share the same database
4. Use Redis for shared state

## Security Considerations

1. **Webhook Secret**: Use `WEBHOOK_SECRET` for additional security
2. **HTTPS Only**: Never use HTTP for webhook URLs
3. **Token Verification**: Webhook endpoint verifies bot token
4. **Rate Limiting**: Configure rate limiting in reverse proxy

## Migration from Polling

1. Set up reverse proxy and SSL
2. Configure `WEBHOOK_URL` in `.env`
3. Set `USE_WEBHOOK=true`
4. Restart ScoutBot
5. Verify webhook is active
6. Monitor logs for any issues

## Reverting to Polling

Simply set `USE_WEBHOOK=false` and restart the bot. The webhook will be automatically removed.
