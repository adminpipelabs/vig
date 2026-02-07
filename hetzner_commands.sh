#!/bin/bash
# Quick commands for Hetzner server (after SSH keys are set up)

HETZNER_IP="5.161.64.209"
HETZNER_USER="root"

# Function to run command on Hetzner
hetzner() {
    ssh ${HETZNER_USER}@${HETZNER_IP} "$@"
}

# Check auto-redemption
check_redeem() {
    echo "🔍 Checking Auto-Redemption..."
    hetzner "crontab -l | grep redeem && echo '✅ Configured' || echo '❌ Not configured'"
    echo ""
    echo "📝 Recent logs:"
    hetzner "tail -20 /root/vig/redeem.log 2>/dev/null || echo 'No log file yet'"
}

# Check bot status
check_bot() {
    echo "🤖 Bot Status:"
    hetzner "ps aux | grep 'main.py' | grep -v grep || echo 'Bot not running'"
    echo ""
    echo "📋 Last 20 lines of bot log:"
    hetzner "tail -20 /root/vig/bot.log 2>/dev/null || echo 'No log file'"
}

# Check systemd service
check_service() {
    echo "⚙️  Systemd Service:"
    hetzner "systemctl status vigbot --no-pager | head -15"
}

# Quick SSH
ssh_hetzner() {
    ssh ${HETZNER_USER}@${HETZNER_IP}
}

# Show usage
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  check-redeem    - Check auto-redemption status"
    echo "  check-bot       - Check bot status and logs"
    echo "  check-service   - Check systemd service status"
    echo "  ssh             - SSH into Hetzner server"
    echo "  <any command>   - Run command on Hetzner server"
    echo ""
    echo "Examples:"
    echo "  $0 check-redeem"
    echo "  $0 'tail -50 /root/vig/bot.log'"
    echo "  $0 'systemctl restart vigbot'"
}

case "$1" in
    check-redeem)
        check_redeem
        ;;
    check-bot)
        check_bot
        ;;
    check-service)
        check_service
        ;;
    ssh)
        ssh_hetzner
        ;;
    "")
        usage
        ;;
    *)
        hetzner "$@"
        ;;
esac
