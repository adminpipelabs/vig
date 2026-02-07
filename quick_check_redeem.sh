#!/bin/bash
# Quick one-liner to check auto-redemption status

echo "🔍 Auto-Redemption Status Check"
echo "================================"
echo ""

# Check cron
echo "📋 Cron Job:"
if crontab -l 2>/dev/null | grep -q "redeem"; then
    echo "  ✅ AUTO-REDEMPTION IS CONFIGURED"
    crontab -l | grep redeem
    echo ""
    echo "  Schedule: Every 2 hours"
else
    echo "  ❌ NO AUTO-REDEMPTION CRON JOB FOUND"
    echo ""
    echo "  To set it up, run:"
    echo "    bash /root/vig/setup_auto_redeem.sh"
fi

echo ""
echo "📝 Recent Logs:"
if [ -f "/root/vig/redeem.log" ]; then
    echo "  Last 10 lines:"
    tail -10 /root/vig/redeem.log | sed 's/^/    /'
else
    echo "  ⚠️  No log file yet (will be created on first run)"
fi

echo ""
echo "📊 Next Runs:"
echo "  Auto-redemption runs every 2 hours at:"
echo "  00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00"
echo "  14:00, 16:00, 18:00, 20:00, 22:00 UTC"
