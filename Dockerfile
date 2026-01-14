# Multi-stage build for ScoutBot v0.03
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssl \
    ca-certificates \
    ffmpeg \
    aria2 \
    netcat-openbsd \
    nodejs \
    npm \
    imagemagick \
    ghostscript \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    chromium \
    xvfb \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with UID/GID 101:101 to match telegram-bot-api
# This allows direct filesystem access to files created by telegram-bot-api
# Use || true to handle case where group/user already exists
RUN (groupadd -g 101 app || true) && \
    (useradd -r -u 101 -g app -m -d /home/app app || true) && \
    id app || (echo "User creation failed, checking existing user:" && getent passwd 101 || true)

# Set working directory
WORKDIR /app

# Copy Python environment from builder
COPY --from=builder --chown=app:app /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=app:app /usr/local/bin /usr/local/bin

# Configure DISPLAY for Xvfb (virtual display for headless Chromium)
# Note: Chromium is installed but only used if YTDLP_ENABLE_PO_PROVIDER=true
ENV DISPLAY=:99

# Ensure Node.js is available for yt-dlp JavaScript execution
ENV PATH="/usr/local/bin:/usr/bin:${PATH}"
ENV NODE_PATH="/usr/lib/node_modules"

# Copy application code
COPY --chown=app:app app/ ./app/
COPY --chown=app:app run.py ./
COPY --chown=app:app pyproject.toml ./

# Copy entrypoint script
COPY --chown=app:app docker-entrypoint.sh /app/docker-entrypoint.sh

# Create data directory
RUN mkdir -p /app/data && \
    chown app:app /app/data /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R app:app /home/app

# Switch to non-root user
USER app

# Expose port
EXPOSE 8916

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=10 \
    CMD curl -f http://localhost:8916/health || exit 1

# Run application with entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
