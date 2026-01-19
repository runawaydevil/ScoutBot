#!/bin/bash
set -e

# Start Uvicorn in background with warning level
echo "🚀 Starting Pentaract API..."
uvicorn main:app --host 0.0.0.0 --port 8547 --log-level warning &
UVICORN_PID=$!

# Wait a bit for the server to start
sleep 3

# Initialize user
echo "👤 Initializing user..."
python init-user.py

# Keep uvicorn running in foreground
wait $UVICORN_PID
