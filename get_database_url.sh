#!/bin/bash
# Quick script to help set up DATABASE_URL

echo "=========================================="
echo "PostgreSQL Setup Helper"
echo "=========================================="
echo ""
echo "1. Go to Railway: https://railway.app"
echo "2. Open your 'vig-production' project"
echo "3. Click on the PostgreSQL service"
echo "4. Go to 'Variables' tab"
echo "5. Copy the DATABASE_URL value"
echo ""
echo "Then run:"
echo "  export DATABASE_URL='your_postgres_url_here'"
echo "  echo 'DATABASE_URL=your_postgres_url_here' >> .env"
echo ""
echo "Or paste the DATABASE_URL here and I'll add it to .env"
echo ""
