#!/bin/bash
# Automated SSH key setup using expect (if available) or manual instructions

HETZNER_IP="5.161.64.209"
HETZNER_USER="root"
SSH_KEY="$HOME/.ssh/id_ed25519.pub"

echo "🔑 Automated SSH Key Setup"
echo "=========================="
echo ""

# Check if expect is available
if command -v expect &> /dev/null; then
    echo "✅ Found 'expect' - will automate password entry"
    echo ""
    echo "Enter Hetzner root password:"
    read -s HETZNER_PASSWORD
    
    expect << EOF
set timeout 30
spawn ssh-copy-id -i $SSH_KEY ${HETZNER_USER}@${HETZNER_IP}
expect {
    "password:" {
        send "$HETZNER_PASSWORD\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}
EOF
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ SSH key copied successfully!"
        echo ""
        echo "🧪 Testing passwordless connection..."
        ssh -o BatchMode=yes ${HETZNER_USER}@${HETZNER_IP} "echo '✅ Passwordless SSH works!'" 2>&1
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "🎉 SUCCESS! You can now SSH without password"
        fi
    else
        echo ""
        echo "❌ Failed. Trying manual method..."
    fi
fi

# If expect not available or failed, try sshpass
if command -v sshpass &> /dev/null; then
    echo ""
    echo "✅ Found 'sshpass' - will automate password entry"
    echo ""
    echo "Enter Hetzner root password:"
    read -s HETZNER_PASSWORD
    
    sshpass -p "$HETZNER_PASSWORD" ssh-copy-id -i $SSH_KEY ${HETZNER_USER}@${HETZNER_IP}
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ SSH key copied successfully!"
        ssh -o BatchMode=yes ${HETZNER_USER}@${HETZNER_IP} "echo '✅ Passwordless SSH works!'" 2>&1
    fi
fi

# If neither expect nor sshpass available, provide manual instructions
if ! command -v expect &> /dev/null && ! command -v sshpass &> /dev/null; then
    echo ""
    echo "⚠️  Neither 'expect' nor 'sshpass' found"
    echo ""
    echo "📋 Manual Setup Required:"
    echo ""
    echo "Run this command (enter password when prompted):"
    echo ""
    echo "  cat $SSH_KEY | ssh ${HETZNER_USER}@${HETZNER_IP} 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && chmod 700 ~/.ssh'"
    echo ""
    echo "Or install expect/sshpass:"
    echo "  brew install expect sshpass"
    echo ""
fi
