#!/bin/sh

echo "Starting ScoutBot v0.03 (Karina Katarazzo)..."

# Ensure PATH includes standard binary directories
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH}"

# Create data directory if it doesn't exist
mkdir -p /app/data

# Set database URL if not already set
export DATABASE_URL=${DATABASE_URL:-file:/app/data/production.db}

# Set timezone from environment variable (defaults to UTC if not set)
if [ -n "${TZ}" ]; then
    echo "🌍 Setting timezone to ${TZ}..."
    export TZ
    # Install tzdata if not already installed (for timezone support)
    if [ ! -f /usr/share/zoneinfo/${TZ} ]; then
        echo "⚠️  Warning: Timezone ${TZ} not found, using UTC"
        export TZ=UTC
    else
        ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime
        echo "✅ Timezone set to ${TZ}"
    fi
else
    echo "⚠️  TZ environment variable not set, using UTC"
    export TZ=UTC
fi

# Wait for Redis to be ready (if not disabled)
if [ "${DISABLE_REDIS}" != "true" ]; then
    echo "⏳ Waiting for Redis to be ready..."
    until nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379} 2>/dev/null; do
        echo "Waiting for Redis..."
        sleep 1
    done
    echo "✅ Redis is ready"
fi

# Start Xvfb (virtual display) for headless Chromium (PO Token Provider)
if [ -n "${DISPLAY}" ]; then
    echo "🖥️ Starting Xvfb virtual display..."
    Xvfb ${DISPLAY} -screen 0 1280x720x24 >/dev/null 2>&1 &
    sleep 1  # Give Xvfb time to start
    echo "✅ Xvfb started on ${DISPLAY}"
fi

# Start the application
echo "🎯 Starting ScoutBot..."
exec python run.py

