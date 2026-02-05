#!/bin/bash
# Start Vig bot with SQLite (local database)
# This bypasses PostgreSQL entirely for local bot operation

echo "🚀 Starting Vig bot with SQLite..."
echo ""

# Unset DATABASE_URL to force SQLite usage
unset DATABASE_URL

# Ensure SQLite database exists
if [ ! -f "vig.db" ]; then
    echo "⚠️  vig.db not found, will be created on first run"
fi

# Check if .env exists and load other config
if [ -f ".env" ]; then
    echo "✓ Loading configuration from .env"
    export $(grep -v '^#' .env | grep -v '^DATABASE_URL' | xargs)
else
    echo "⚠️  .env not found, using defaults"
fi

# Start the bot
echo ""
echo "Starting bot (SQLite mode)..."
echo "Press Ctrl+C to stop"
echo ""

python3 main.py
