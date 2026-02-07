#!/bin/bash
# Check auto-redemption status on Hetzner

echo "🔍 Checking Auto-Redemption Status"
echo "=================================="
echo ""

# Check if cron job exists
echo "📋 Cron Jobs:"
crontab -l 2>/dev/null | grep -i redeem || echo "  ❌ No redemption cron job found"
echo ""

# Check if auto_redeem.py process is running
echo "🔄 Running Processes:"
ps aux | grep -i "auto_redeem\|redeem_winnings" | grep -v grep || echo "  ❌ No redemption process running"
echo ""

# Check last redemption log
echo "📝 Last Redemption Log (if exists):"
if [ -f "/root/vig/redeem.log" ]; then
    echo "  Last 20 lines:"
    tail -20 /root/vig/redeem.log
else
    echo "  ⚠️  No redeem.log file found"
fi
echo ""

# Check if auto_redeem.py exists
echo "📁 Script Location:"
if [ -f "/root/vig/auto_redeem.py" ]; then
    echo "  ✅ auto_redeem.py found"
else
    echo "  ❌ auto_redeem.py not found"
fi

if [ -f "/root/vig/redeem_winnings.py" ]; then
    echo "  ✅ redeem_winnings.py found"
else
    echo "  ❌ redeem_winnings.py not found"
fi
echo ""

echo "💡 To set up auto-redemption every 2 hours, run:"
echo "   crontab -e"
echo "   Add: 0 */2 * * * cd /root/vig && /root/vig/venv/bin/python3 redeem_winnings.py >> /root/vig/redeem.log 2>&1"
