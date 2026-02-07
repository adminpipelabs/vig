#!/bin/bash
# Automated SSH key setup using expect

HETZNER_IP="5.161.64.209"
HETZNER_USER="root"
SSH_KEY="$HOME/.ssh/id_ed25519.pub"

echo "🔑 Automated SSH Key Setup"
echo "=========================="
echo ""
echo "Enter Hetzner root password:"
read -s PASSWORD
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found at $SSH_KEY"
    echo "Generating one now..."
    ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
fi

# Use expect to automate ssh-copy-id
expect << EOF
set timeout 30
spawn ssh-copy-id -i $SSH_KEY ${HETZNER_USER}@${HETZNER_IP}
expect {
    "password:" {
        send "$PASSWORD\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    "Permission denied" {
        puts "\n❌ Authentication failed. Check password."
        exit 1
    }
    eof
}
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SSH key copied!"
    echo ""
    echo "🧪 Testing passwordless connection..."
    
    ssh -o BatchMode=yes ${HETZNER_USER}@${HETZNER_IP} "echo '✅ Passwordless SSH works!'" 2>&1
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "🎉 SUCCESS! Passwordless SSH is now configured"
        echo ""
        echo "You can now run:"
        echo "  ssh ${HETZNER_USER}@${HETZNER_IP}"
        echo ""
        echo "Or use helper script:"
        echo "  cd /Users/mikaelo/vig && ./hetzner_commands.sh check-redeem"
    else
        echo "⚠️  Key copied but test failed. May need to check server config."
    fi
else
    echo ""
    echo "❌ Failed to copy SSH key. Please check password and try again."
    exit 1
fi
