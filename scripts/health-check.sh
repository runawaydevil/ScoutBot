#!/bin/bash

# Health check script for RSS Skull Bot with Resilience System
# This script checks the health of the bot and resilience system

set -e

HOST=${HOST:-localhost}
PORT=${PORT:-8916}
BASE_URL="http://${HOST}:${PORT}"

echo "🔍 Checking RSS Skull Bot health..."

# Function to make HTTP request with timeout
make_request() {
    local url=$1
    local timeout=${2:-10}
    
    if command -v curl >/dev/null 2>&1; then
        curl -f -s --max-time "$timeout" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -T "$timeout" -O - "$url"
    else
        echo "Error: Neither curl nor wget is available"
        exit 1
    fi
}

# Check basic health endpoint
echo "📊 Checking basic health..."
HEALTH_RESPONSE=$(make_request "${BASE_URL}/health")
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$HEALTH_STATUS" = "ok" ]; then
    echo "✅ Basic health: OK"
else
    echo "❌ Basic health: $HEALTH_STATUS"
    echo "Response: $HEALTH_RESPONSE"
    exit 1
fi

# Check resilience system
echo "🛡️ Checking resilience system..."
RESILIENCE_RESPONSE=$(make_request "${BASE_URL}/resilience-stats" 15)

if [ $? -eq 0 ]; then
    echo "✅ Resilience system: Available"
    
    # Extract key metrics
    SUCCESS_RATE=$(echo "$RESILIENCE_RESPONSE" | grep -o '"successRate":[0-9.]*' | cut -d':' -f2)
    QUEUE_SIZE=$(echo "$RESILIENCE_RESPONSE" | grep -o '"totalMessages":[0-9]*' | cut -d':' -f2)
    
    if [ -n "$SUCCESS_RATE" ]; then
        echo "📈 Success Rate: ${SUCCESS_RATE}"
        
        # Check if success rate is acceptable (> 0.8 = 80%)
        if [ "$(echo "$SUCCESS_RATE > 0.8" | bc -l 2>/dev/null || echo "1")" = "1" ]; then
            echo "✅ Success rate is healthy"
        else
            echo "⚠️ Success rate is low: ${SUCCESS_RATE}"
        fi
    fi
    
    if [ -n "$QUEUE_SIZE" ]; then
        echo "📬 Queue Size: ${QUEUE_SIZE}"
        
        # Check if queue size is reasonable (< 100)
        if [ "$QUEUE_SIZE" -lt 100 ]; then
            echo "✅ Queue size is healthy"
        else
            echo "⚠️ Queue size is high: ${QUEUE_SIZE}"
        fi
    fi
else
    echo "⚠️ Resilience system: Not available (may be disabled)"
fi

# Check detailed metrics
echo "📊 Checking detailed metrics..."
METRICS_RESPONSE=$(make_request "${BASE_URL}/metrics" 15)

if [ $? -eq 0 ]; then
    echo "✅ Metrics endpoint: Available"
    
    # Check for alerts
    CONNECTION_DOWN=$(echo "$METRICS_RESPONSE" | grep -o '"connectionDown":[^,}]*' | cut -d':' -f2)
    HIGH_ERROR_RATE=$(echo "$METRICS_RESPONSE" | grep -o '"highErrorRate":[^,}]*' | cut -d':' -f2)
    QUEUE_OVERFLOW=$(echo "$METRICS_RESPONSE" | grep -o '"queueOverflow":[^,}]*' | cut -d':' -f2)
    
    if [ "$CONNECTION_DOWN" = "true" ]; then
        echo "🚨 ALERT: Connection is down"
    fi
    
    if [ "$HIGH_ERROR_RATE" = "true" ]; then
        echo "🚨 ALERT: High error rate detected"
    fi
    
    if [ "$QUEUE_OVERFLOW" = "true" ]; then
        echo "🚨 ALERT: Queue overflow detected"
    fi
    
    if [ "$CONNECTION_DOWN" != "true" ] && [ "$HIGH_ERROR_RATE" != "true" ] && [ "$QUEUE_OVERFLOW" != "true" ]; then
        echo "✅ No active alerts"
    fi
else
    echo "⚠️ Metrics endpoint: Not available"
fi

# Check database connectivity (via health endpoint)
DB_STATUS=$(echo "$HEALTH_RESPONSE" | grep -o '"database":[^,}]*' | cut -d':' -f2)
if [ "$DB_STATUS" = "true" ]; then
    echo "✅ Database: Connected"
else
    echo "❌ Database: Disconnected"
fi

# Check Redis connectivity (via health endpoint)
REDIS_STATUS=$(echo "$HEALTH_RESPONSE" | grep -o '"redis":[^,}]*' | cut -d':' -f2)
if [ "$REDIS_STATUS" = "true" ]; then
    echo "✅ Redis: Connected"
else
    echo "⚠️ Redis: Disconnected (may be disabled)"
fi

echo ""
echo "🎉 Health check completed!"
echo "📊 Full health report available at: ${BASE_URL}/health"
echo "🛡️ Resilience stats available at: ${BASE_URL}/resilience-stats"
echo "📈 Detailed metrics available at: ${BASE_URL}/metrics"