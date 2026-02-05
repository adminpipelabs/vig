#!/bin/bash
# Script to add DATABASE_URL to .env file

echo "PostgreSQL DATABASE_URL Setup"
echo "================================"
echo ""
echo "Please provide your DATABASE_URL from Railway:"
echo "(Format: postgresql://postgres:password@host:port/railway)"
echo ""
read -p "DATABASE_URL: " DB_URL

if [ -z "$DB_URL" ]; then
    echo "❌ DATABASE_URL is empty. Exiting."
    exit 1
fi

# Add to .env file
echo "" >> .env
echo "# PostgreSQL Database URL (from Railway)" >> .env
echo "DATABASE_URL=$DB_URL" >> .env

echo ""
echo "✅ DATABASE_URL added to .env file"
echo ""
echo "Next steps:"
echo "1. Set DATABASE_URL on Railway dashboard service (Variables tab)"
echo "2. Run: python3.11 migrate_to_postgres.py"
echo "3. Start bot: python3.11 main.py"
