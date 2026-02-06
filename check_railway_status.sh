#!/bin/bash
# Quick script to check Railway deployment status

echo "🔍 Checking Railway Deployment Status"
echo "======================================"
echo ""

# Check if Railway URL is accessible
RAILWAY_URL="https://vig-production.up.railway.app"

echo "1. Testing Dashboard URL..."
if curl -s -o /dev/null -w "%{http_code}" "$RAILWAY_URL" | grep -q "200"; then
    echo "   ✅ Dashboard is accessible"
else
    echo "   ❌ Dashboard not accessible"
fi

echo ""
echo "2. Testing API Endpoints..."

# Test stats endpoint
STATS_RESPONSE=$(curl -s "$RAILWAY_URL/api/stats" 2>/dev/null)
if [ -n "$STATS_RESPONSE" ]; then
    echo "   ✅ /api/stats responds"
    echo "   Response: $STATS_RESPONSE" | head -c 100
    echo "..."
else
    echo "   ❌ /api/stats not responding"
fi

# Test bets endpoint
BETS_RESPONSE=$(curl -s "$RAILWAY_URL/api/bets?limit=5" 2>/dev/null)
if [ -n "$BETS_RESPONSE" ]; then
    echo "   ✅ /api/bets responds"
    BET_COUNT=$(echo "$BETS_RESPONSE" | grep -o '"id"' | wc -l)
    echo "   Found $BET_COUNT bets"
else
    echo "   ❌ /api/bets not responding"
fi

# Test windows endpoint
WINDOWS_RESPONSE=$(curl -s "$RAILWAY_URL/api/windows?limit=5" 2>/dev/null)
if [ -n "$WINDOWS_RESPONSE" ]; then
    echo "   ✅ /api/windows responds"
    WINDOW_COUNT=$(echo "$WINDOWS_RESPONSE" | grep -o '"id"' | wc -l)
    echo "   Found $WINDOW_COUNT windows"
else
    echo "   ❌ /api/windows not responding"
fi

echo ""
echo "3. Next Steps:"
echo "   - Check Railway Dashboard → Logs for bot activity"
echo "   - Look for 'WINDOW 1' or 'Scanning Polymarket' messages"
echo "   - Bot runs every hour by default (SCAN_INTERVAL_SECONDS)"
echo "   - If database is empty, wait for first window to complete"
echo ""
echo "4. To speed up testing:"
echo "   - Set SCAN_INTERVAL_SECONDS=300 (5 minutes) in Railway variables"
echo "   - Or wait ~1 hour for first scan cycle"
