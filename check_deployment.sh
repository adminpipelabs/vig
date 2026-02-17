#!/bin/bash
# Check deployment status - Railway or Hetzner

echo "🔍 Checking Deployment Status"
echo "=============================="

# Check Railway deployment
echo ""
echo "1. Railway Deployment:"
RAILWAY_URL="https://vig-production.up.railway.app"
if curl -s --max-time 5 "$RAILWAY_URL/api/health" > /dev/null 2>&1; then
    echo "   ✅ Railway is responding"
    HEALTH=$(curl -s --max-time 5 "$RAILWAY_URL/api/health" 2>/dev/null)
    echo "   Response: $HEALTH"
else
    echo "   ❌ Railway is not responding"
    echo "   URL: $RAILWAY_URL"
fi

# Check Hetzner deployment
echo ""
echo "2. Hetzner Server:"
HETZNER_IP="5.161.64.209"
HETZNER_USER="root"

if ssh -o ConnectTimeout=5 -o BatchMode=yes ${HETZNER_USER}@${HETZNER_IP} "echo 'connected'" 2>/dev/null; then
    echo "   ✅ Can connect to Hetzner"
    
    # Check if dashboard is running
    echo ""
    echo "   Checking dashboard service..."
    ssh ${HETZNER_USER}@${HETZNER_IP} "
        if systemctl is-active --quiet vig-dashboard 2>/dev/null; then
            echo '   ✅ Dashboard service is running'
            systemctl status vig-dashboard --no-pager | head -10
        elif pgrep -f 'uvicorn dashboard' > /dev/null; then
            echo '   ✅ Dashboard process is running'
            ps aux | grep 'uvicorn dashboard' | grep -v grep
        else
            echo '   ❌ Dashboard is not running'
        fi
    " 2>/dev/null || echo "   ⚠️  Could not check Hetzner status (SSH may not be configured)"
else
    echo "   ⚠️  Cannot connect to Hetzner (SSH keys may not be set up)"
    echo "   IP: $HETZNER_IP"
fi

echo ""
echo "=============================="
echo ""
echo "To test locally:"
echo "  python3 test_dashboard.py"
echo ""
echo "To check Hetzner:"
echo "  ./hetzner_commands.sh check-bot"
echo "  ssh root@5.161.64.209 'systemctl status vig-dashboard'"
echo ""
echo "Railway URL: $RAILWAY_URL"
