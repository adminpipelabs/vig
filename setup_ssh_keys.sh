#!/bin/bash
# Setup SSH key authentication for Hetzner server (passwordless access)

HETZNER_IP="5.161.64.209"
HETZNER_USER="root"

echo "🔑 Setting up SSH Key Authentication"
echo "====================================="
echo ""

# Check if SSH key exists
if [ ! -f ~/.ssh/id_rsa.pub ] && [ ! -f ~/.ssh/id_ed25519.pub ]; then
    echo "📝 No SSH key found. Generating one..."
    ssh-keygen -t ed25519 -C "vig-bot-hetzner" -f ~/.ssh/id_ed25519 -N ""
    echo ""
fi

# Determine which key to use
if [ -f ~/.ssh/id_ed25519.pub ]; then
    KEY_FILE=~/.ssh/id_ed25519.pub
elif [ -f ~/.ssh/id_rsa.pub ]; then
    KEY_FILE=~/.ssh/id_rsa.pub
else
    echo "❌ No SSH public key found"
    exit 1
fi

echo "✅ Found SSH key: $KEY_FILE"
echo ""
echo "📋 Your public key:"
cat $KEY_FILE
echo ""
echo ""
echo "🔧 Copying SSH key to Hetzner server..."
echo "   (You'll need to enter password ONE MORE TIME)"
echo ""

# Copy SSH key to Hetzner
ssh-copy-id -i $KEY_FILE ${HETZNER_USER}@${HETZNER_IP}

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SSH key copied successfully!"
    echo ""
    echo "🧪 Testing passwordless connection..."
    ssh -o BatchMode=yes ${HETZNER_USER}@${HETZNER_IP} "echo '✅ Passwordless SSH works!'" 2>&1
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "🎉 SUCCESS! You can now SSH without password:"
        echo "   ssh ${HETZNER_USER}@${HETZNER_IP}"
        echo ""
        echo "💡 Quick commands:"
        echo "   ssh ${HETZNER_USER}@${HETZNER_IP} 'crontab -l | grep redeem'"
        echo "   ssh ${HETZNER_USER}@${HETZNER_IP} 'tail -30 /root/vig/redeem.log'"
    else
        echo ""
        echo "⚠️  Key copied but passwordless test failed. Check:"
        echo "   1. Server allows key authentication"
        echo "   2. ~/.ssh/authorized_keys exists on server"
    fi
else
    echo ""
    echo "❌ Failed to copy SSH key. Make sure:"
    echo "   1. You can SSH to the server with password"
    echo "   2. ssh-copy-id is installed (brew install ssh-copy-id on Mac)"
    echo ""
    echo "   Manual method:"
    echo "   cat $KEY_FILE | ssh ${HETZNER_USER}@${HETZNER_IP} 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'"
fi
