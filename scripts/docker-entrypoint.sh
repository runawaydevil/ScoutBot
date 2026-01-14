#!/bin/sh

echo "🚀 Starting RSS Skull Bot..."

# Create data directory and set database URL
mkdir -p /app/data
export DATABASE_URL='file:/app/data/production.db'

# Apply migrations (works for both new and existing databases)
echo "📋 Applying database migrations..."

# Check if database exists, if not create it first
if [ ! -f /app/data/production.db ]; then
  echo "📝 Database doesn't exist, creating it..."
  touch /app/data/production.db
fi

# Try to check migration status only if database exists and has tables
MIGRATE_STATUS=$(npx prisma migrate status --schema=./prisma/schema.prisma 2>&1 || echo "")
if [ -n "$MIGRATE_STATUS" ]; then
  echo "$MIGRATE_STATUS"
  
  # Check if there are failed migrations
  if echo "$MIGRATE_STATUS" | grep -q "failed"; then
    echo "⚠️  Found failed migrations, attempting to resolve..."
    # The last failed migration is usually the one causing issues
    # Mark it as rolled back and then we can reapply
    FAILED_MIG=$(echo "$MIGRATE_STATUS" | grep "failed" | tail -1 | awk '{print $1}' || echo "")
    if [ -n "$FAILED_MIG" ]; then
      echo "🔧 Marking migration as rolled back: $FAILED_MIG"
      npx prisma migrate resolve --rolled-back "$FAILED_MIG" --schema=./prisma/schema.prisma || true
    fi
  fi
fi

# Try to deploy migrations
DEPLOY_OUTPUT=$(npx prisma migrate deploy --schema=./prisma/schema.prisma 2>&1)
DEPLOY_EXIT=$?

if [ $DEPLOY_EXIT -eq 0 ]; then
  echo "✅ Migrations applied successfully"
else
  echo "$DEPLOY_OUTPUT"
  echo "⚠️  Migrations failed, attempting fallback..."
  
  # Check if the error is about duplicate columns
  if echo "$DEPLOY_OUTPUT" | grep -q "duplicate column"; then
    echo "🔍 Detected duplicate column error"
    FAILED_MIG=$(echo "$DEPLOY_OUTPUT" | grep "Migration name:" | sed 's/.*Migration name: //' || echo "")
    if [ -n "$FAILED_MIG" ]; then
      echo "🔧 Marking duplicate column migration as applied: $FAILED_MIG"
      npx prisma migrate resolve --applied "$FAILED_MIG" --schema=./prisma/schema.prisma || true
      
      # Try deploying again
      echo "🔄 Retrying migration deployment..."
      npx prisma migrate deploy --schema=./prisma/schema.prisma || echo "⚠️  Second attempt failed, continuing anyway..."
    fi
  fi
  
  echo "🔄 Continuing with startup despite migration errors..."
fi

# Verify Prisma client exists
if [ ! -d "/app/node_modules/.prisma/client" ]; then
  echo "🔧 Prisma client not found, generating..."
  npx prisma generate --schema=./prisma/schema.prisma || echo "⚠️ Prisma generate failed, continuing anyway..."
else
  echo "✅ Prisma client already exists"
fi

# Start the application
echo "🎯 Starting RSS Skull Bot..."
exec node dist/main.js
