#!/bin/bash
# Quick script to push to GitHub

cd /Users/mikaelo/vig

echo "🚀 Pushing 7 commits to GitHub..."

# Try GitHub CLI first
if command -v gh &> /dev/null; then
    echo "Trying GitHub CLI..."
    gh auth login --web --hostname github.com
    if [ $? -eq 0 ]; then
        git push origin main
        exit 0
    fi
fi

# Try with token if provided
if [ -n "$GH_TOKEN" ]; then
    echo "Using GH_TOKEN..."
    git remote set-url origin https://${GH_TOKEN}@github.com/adminpipelabs/vig.git
    git push origin main
    exit 0
fi

# Try SSH
echo "Trying SSH..."
git remote set-url origin git@github.com:adminpipelabs/vig.git
ssh-add ~/.ssh/id_ed25519 2>/dev/null
git push origin main

# If all fail, show manual steps
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Automatic push failed. Manual options:"
    echo ""
    echo "Option 1: GitHub Desktop"
    echo "  - Open GitHub Desktop"
    echo "  - Open /Users/mikaelo/vig"
    echo "  - Click 'Push origin'"
    echo ""
    echo "Option 2: Set token and push"
    echo "  export GH_TOKEN=your_token"
    echo "  ./push_to_github.sh"
    echo ""
    echo "Option 3: Manual git push"
    echo "  git push origin main"
fi
