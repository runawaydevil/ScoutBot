#!/bin/bash
set -e

echo "Deploying ScoutBot v0.03..."

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Check if we should use a specific tag
if [ -n "$1" ]; then
    echo "📌 Checking out tag: $1"
    git checkout "$1"
fi

# Build Docker images
echo "🔨 Building Docker images..."
docker compose build --no-cache

# Stop and remove old containers
echo "🛑 Stopping old containers..."
docker compose down

# Start new containers
echo "▶️  Starting new containers..."
docker compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo "🏥 Checking health..."
HEALTH_CHECK=$(curl -s http://localhost:8916/health || echo "failed")
if echo "$HEALTH_CHECK" | grep -q "ok"; then
    echo "✅ Health check passed"
else
    echo "⚠️  Health check failed or service not ready yet"
fi

# Show container status
echo "📊 Container status:"
docker compose ps

# Show recent logs
echo "📋 Recent logs:"
docker compose logs --tail=50 scoutbot

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Useful commands:"
echo "  View logs:        docker compose logs -f scoutbot"
echo "  Check health:     curl http://localhost:8916/health"
echo "  Container status: docker compose ps"
echo "  Stop services:    docker compose down"
