#!/bin/bash
# Setup auto-redemption cron job on Hetzner (runs every 2 hours)

echo "🔧 Setting up Auto-Redemption (Every 2 Hours)"
echo "=============================================="
echo ""

# Get current crontab
crontab -l > /tmp/current_cron 2>/dev/null || touch /tmp/current_cron

# Check if redemption cron already exists
if grep -q "redeem_winnings\|auto_redeem" /tmp/current_cron; then
    echo "⚠️  Redemption cron job already exists:"
    grep "redeem_winnings\|auto_redeem" /tmp/current_cron
    echo ""
    read -p "Replace it? (y/n): " replace
    if [ "$replace" != "y" ]; then
        echo "Cancelled."
        rm /tmp/current_cron
        exit 0
    fi
    # Remove old redemption entries
    grep -v "redeem_winnings\|auto_redeem" /tmp/current_cron > /tmp/new_cron
    mv /tmp/new_cron /tmp/current_cron
fi

# Add new cron job (runs every 2 hours at :00)
echo "# Auto-redeem winning positions every 2 hours" >> /tmp/current_cron
echo "0 */2 * * * cd /root/vig && /root/vig/venv/bin/python3 redeem_winnings.py >> /root/vig/redeem.log 2>&1" >> /tmp/current_cron

# Install new crontab
crontab /tmp/current_cron
rm /tmp/current_cron

echo "✅ Auto-redemption cron job installed!"
echo ""
echo "📋 Current crontab:"
crontab -l
echo ""
echo "⏰ Will run every 2 hours at: 00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00"
echo ""
echo "📝 Logs will be written to: /root/vig/redeem.log"
echo ""
echo "🧪 Test it now? (y/n): "
read test_now
if [ "$test_now" == "y" ]; then
    echo ""
    echo "Running redemption now..."
    cd /root/vig && /root/vig/venv/bin/python3 redeem_winnings.py
fi
