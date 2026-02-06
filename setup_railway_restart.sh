#!/bin/bash
#
# Safe script to setup Railway API variables for bot restart functionality
# This script will NOT overwrite existing variables unless you explicitly confirm
#

set -e  # Exit on error

echo "=========================================="
echo "Railway Bot Restart Setup"
echo "=========================================="
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Please install it first:"
    echo "   npm i -g @railway/cli"
    echo ""
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "⚠️  Not logged into Railway. Logging in..."
    railway login
fi

echo "✅ Railway CLI found and authenticated"
echo ""

# Get current project
PROJECT=$(railway status --json 2>/dev/null | grep -o '"project":"[^"]*"' | cut -d'"' -f4 || echo "")
if [ -z "$PROJECT" ]; then
    echo "❌ Could not detect Railway project. Please run this from your project directory or:"
    echo "   cd /path/to/vig"
    echo "   railway link"
    exit 1
fi

echo "📦 Project: $PROJECT"
echo ""

# Get current service
SERVICE=$(railway status --json 2>/dev/null | grep -o '"service":"[^"]*"' | cut -d'"' -f4 || echo "")
if [ -z "$SERVICE" ]; then
    echo "⚠️  Could not detect service. You may need to select it."
    echo ""
    read -p "Enter service name (or press Enter to auto-detect): " SERVICE_INPUT
    if [ -n "$SERVICE_INPUT" ]; then
        SERVICE="$SERVICE_INPUT"
    fi
fi

echo "🔧 Service: $SERVICE"
echo ""

# Check existing variables
echo "Checking existing environment variables..."
RAILWAY_TOKEN_EXISTS=$(railway variables --json 2>/dev/null | grep -c "RAILWAY_TOKEN" || echo "0")
RAILWAY_SERVICE_ID_EXISTS=$(railway variables --json 2>/dev/null | grep -c "RAILWAY_SERVICE_ID" || echo "0")

if [ "$RAILWAY_TOKEN_EXISTS" -gt 0 ]; then
    echo "⚠️  RAILWAY_TOKEN already exists"
    read -p "   Do you want to update it? (y/N): " UPDATE_TOKEN
    if [[ ! "$UPDATE_TOKEN" =~ ^[Yy]$ ]]; then
        echo "   Skipping RAILWAY_TOKEN (keeping existing value)"
        SKIP_TOKEN=true
    else
        SKIP_TOKEN=false
    fi
else
    SKIP_TOKEN=false
fi

if [ "$RAILWAY_SERVICE_ID_EXISTS" -gt 0 ]; then
    echo "⚠️  RAILWAY_SERVICE_ID already exists"
    read -p "   Do you want to update it? (y/N): " UPDATE_SERVICE_ID
    if [[ ! "$UPDATE_SERVICE_ID" =~ ^[Yy]$ ]]; then
        echo "   Skipping RAILWAY_SERVICE_ID (keeping existing value)"
        SKIP_SERVICE_ID=true
    else
        SKIP_SERVICE_ID=false
    fi
else
    SKIP_SERVICE_ID=false
fi

echo ""

# Get Railway API Token
if [ "$SKIP_TOKEN" != "true" ]; then
    echo "Step 1: Get Railway API Token"
    echo "--------------------------------"
    echo "1. Go to: https://railway.app/account"
    echo "2. Scroll to 'API Tokens' section"
    echo "3. Click 'Create Token'"
    echo "4. Copy the token (starts with 'railway_...')"
    echo ""
    read -p "Enter Railway API Token: " RAILWAY_TOKEN
    
    if [ -z "$RAILWAY_TOKEN" ]; then
        echo "❌ Token cannot be empty. Exiting."
        exit 1
    fi
    
    # Validate token format
    if [[ ! "$RAILWAY_TOKEN" =~ ^railway_ ]]; then
        echo "⚠️  Warning: Token doesn't start with 'railway_'. Are you sure this is correct?"
        read -p "Continue anyway? (y/N): " CONTINUE
        if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    echo "✅ Token format looks good"
    echo ""
fi

# Get Service ID
if [ "$SKIP_SERVICE_ID" != "true" ]; then
    echo "Step 2: Get Railway Service ID"
    echo "--------------------------------"
    echo "Option A: Auto-detect from current service"
    echo "Option B: Manual entry"
    echo ""
    read -p "Auto-detect Service ID? (Y/n): " AUTO_DETECT
    
    if [[ "$AUTO_DETECT" =~ ^[Nn]$ ]]; then
        echo ""
        echo "To find Service ID manually:"
        echo "1. Go to Railway dashboard → Your project → Your service"
        echo "2. Look at the URL: https://railway.app/project/[PROJECT_ID]/service/[SERVICE_ID]"
        echo "3. Copy the SERVICE_ID part"
        echo ""
        read -p "Enter Service ID: " RAILWAY_SERVICE_ID
    else
        # Try to get service ID from Railway API
        echo "🔍 Attempting to auto-detect Service ID..."
        
        # Use Railway CLI to get service info
        SERVICE_INFO=$(railway service --json 2>/dev/null || echo "")
        if [ -n "$SERVICE_INFO" ]; then
            RAILWAY_SERVICE_ID=$(echo "$SERVICE_INFO" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
        fi
        
        if [ -z "$RAILWAY_SERVICE_ID" ]; then
            echo "⚠️  Could not auto-detect. Please enter manually:"
            read -p "Enter Service ID: " RAILWAY_SERVICE_ID
        else
            echo "✅ Auto-detected Service ID: $RAILWAY_SERVICE_ID"
        fi
    fi
    
    if [ -z "$RAILWAY_SERVICE_ID" ]; then
        echo "❌ Service ID cannot be empty. Exiting."
        exit 1
    fi
    
    echo ""
fi

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
if [ "$SKIP_TOKEN" != "true" ]; then
    echo "RAILWAY_TOKEN: ${RAILWAY_TOKEN:0:20}... (will be set)"
else
    echo "RAILWAY_TOKEN: (keeping existing)"
fi
echo "RAILWAY_SERVICE_ID: (auto-injected by Railway - no need to set)"
echo ""

# Confirmation
read -p "Proceed with setting these variables? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled. No changes made."
    exit 0
fi

echo ""
echo "Setting environment variables..."

# Set variables
if [ "$SKIP_TOKEN" != "true" ]; then
    echo "Setting RAILWAY_TOKEN..."
    railway variables set RAILWAY_TOKEN="$RAILWAY_TOKEN" 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ RAILWAY_TOKEN set successfully"
    else
        echo "❌ Failed to set RAILWAY_TOKEN"
        exit 1
    fi
fi

echo ""
echo "ℹ️  RAILWAY_SERVICE_ID is automatically injected by Railway"
echo "   No need to set it manually - Railway provides it automatically"

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart your Railway service once to load the new variables"
echo "2. Go to your dashboard and click 'Restart' button"
echo "3. The bot should restart automatically!"
echo ""
echo "To restart Railway service:"
echo "  railway restart"
echo ""
