#!/usr/bin/env python3
"""
Verify PostgreSQL setup is working
"""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

print("=" * 80)
print("POSTGRESQL SETUP VERIFICATION")
print("=" * 80)
print()

# Check if DATABASE_URL is set
database_url = os.getenv("DATABASE_URL")
if database_url:
    print("✅ DATABASE_URL found in environment")
    # Mask password for security
    masked_url = database_url.split('@')[0].split(':')[:-1]
    if len(masked_url) > 1:
        print(f"   Connection: {masked_url[0]}://***@{database_url.split('@')[1]}")
    else:
        print(f"   Connection: {database_url[:30]}...")
else:
    print("⚠️  DATABASE_URL not set")
    print("   Set it in .env file or Railway environment variables")

print()

# Test PostgreSQL connection
if database_url:
    try:
        import psycopg2
        print("✅ psycopg2-binary installed")
        
        print("\n🔌 Testing PostgreSQL connection...")
        conn = psycopg2.connect(database_url)
        conn.set_session(autocommit=False)
        cur = conn.cursor()
        
        # Check tables exist
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        print(f"✅ Connected successfully!")
        print(f"   Tables found: {', '.join(tables) if tables else 'None (will be created on first use)'}")
        
        # Check data
        if 'bets' in tables:
            cur.execute("SELECT COUNT(*) FROM bets")
            bet_count = cur.fetchone()[0]
            print(f"   Bets in database: {bet_count}")
        
        if 'windows' in tables:
            cur.execute("SELECT COUNT(*) FROM windows")
            window_count = cur.fetchone()[0]
            print(f"   Windows in database: {window_count}")
        
        conn.close()
        print("\n✅ PostgreSQL setup is working!")
        
    except ImportError:
        print("❌ psycopg2-binary not installed")
        print("   Run: pip install psycopg2-binary")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("   Check DATABASE_URL is correct")
else:
    print("⚠️  Cannot test connection - DATABASE_URL not set")

print()
print("=" * 80)
print("NEXT STEPS")
print("=" * 80)
print()
print("1. Bot: Set DATABASE_URL in local .env file")
print("2. Dashboard: Set DATABASE_URL on Railway (already done?)")
print("3. Test bot: python3.11 main.py")
print("4. Test dashboard: https://vig-production.up.railway.app/")
print()
print("If you want to migrate existing SQLite data:")
print("  python3.11 migrate_to_postgres.py")
