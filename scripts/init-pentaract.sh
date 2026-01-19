#!/bin/bash
# Pentaract Initialization Script
# This script creates the initial user account in Pentaract

echo "🚀 Initializing Pentaract..."

# Wait for Pentaract to be ready
echo "⏳ Waiting for Pentaract API to be ready..."
for i in {1..30}; do
    if curl -f http://localhost:8547/api/health > /dev/null 2>&1; then
        echo "✅ Pentaract API is ready!"
        break
    fi
    echo "   Attempt $i/30..."
    sleep 2
done

# Create user account
echo "👤 Creating Pentaract user account..."
RESPONSE=$(curl -X POST http://localhost:8547/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "pablo@pablomurad.com",
    "password": "driver21",
    "username": "pablo"
  }' 2>/dev/null)

echo ""
echo "Response: $RESPONSE"
echo ""
echo "✅ Pentaract initialization complete!"
echo ""
echo "📋 Account Details:"
echo "   Email: pablo@pablomurad.com"
echo "   Password: driver21"
echo ""
echo "🔗 API URL: http://localhost:8547/api"
echo ""
echo "Test connection:"
echo "   curl http://localhost:8547/api/health"
echo ""
echo "Test login:"
echo '   curl -X POST http://localhost:8547/api/auth/login -H "Content-Type: application/json" -d '"'"'{"email":"pablo@pablomurad.com","password":"driver21"}'"'"''

