#!/usr/bin/env python3
"""Check migration status - compare SQLite vs PostgreSQL"""
import os
import sqlite3
from dotenv import load_dotenv
from pathlib import Path

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

SQLITE_DB = os.getenv("DB_PATH", "vig.db")
POSTGRES_URL = os.getenv("DATABASE_URL")

print("=" * 60)
print("MIGRATION STATUS CHECK")
print("=" * 60)

# Check SQLite
if os.path.exists(SQLITE_DB):
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cur = sqlite_conn.cursor()
    
    sqlite_cur.execute("SELECT COUNT(*) FROM bets")
    sqlite_bets = sqlite_cur.fetchone()[0]
    sqlite_cur.execute("SELECT COUNT(*) FROM windows")
    sqlite_windows = sqlite_cur.fetchone()[0]
    sqlite_cur.execute("SELECT COUNT(*) FROM circuit_breaker_log")
    sqlite_logs = sqlite_cur.fetchone()[0]
    
    print(f"\n📂 SQLite ({SQLITE_DB}):")
    print(f"   - bets: {sqlite_bets}")
    print(f"   - windows: {sqlite_windows}")
    print(f"   - circuit_breaker_log: {sqlite_logs}")
    
    sqlite_conn.close()
else:
    print(f"\n❌ SQLite DB not found: {SQLITE_DB}")
    sqlite_bets = sqlite_windows = sqlite_logs = 0

# Check PostgreSQL
if POSTGRES_URL:
    try:
        import psycopg2
        print(f"\n📊 Connecting to PostgreSQL...")
        pg_conn = psycopg2.connect(POSTGRES_URL, connect_timeout=5)
        pg_cur = pg_conn.cursor()
        
        pg_cur.execute("SELECT COUNT(*) FROM bets")
        pg_bets = pg_cur.fetchone()[0]
        pg_cur.execute("SELECT COUNT(*) FROM windows")
        pg_windows = pg_cur.fetchone()[0]
        pg_cur.execute("SELECT COUNT(*) FROM circuit_breaker_log")
        pg_logs = pg_cur.fetchone()[0]
        
        print(f"✅ PostgreSQL:")
        print(f"   - bets: {pg_bets}")
        print(f"   - windows: {pg_windows}")
        print(f"   - circuit_breaker_log: {pg_logs}")
        
        print(f"\n📊 Migration Status:")
        print(f"   - bets: {pg_bets}/{sqlite_bets} ({'✅ Complete' if pg_bets == sqlite_bets else '⚠️  Partial'})")
        print(f"   - windows: {pg_windows}/{sqlite_windows} ({'✅ Complete' if pg_windows == sqlite_windows else '⚠️  Partial'})")
        print(f"   - logs: {pg_logs}/{sqlite_logs} ({'✅ Complete' if pg_logs == sqlite_logs else '⚠️  Partial'})")
        
        if pg_windows < sqlite_windows:
            remaining = sqlite_windows - pg_windows
            print(f"\n⚠️  {remaining:,} windows still need to be migrated")
            print(f"   Progress: {pg_windows/sqlite_windows*100:.1f}%")
        
        pg_conn.close()
    except psycopg2.OperationalError as e:
        print(f"\n❌ PostgreSQL connection failed: {e}")
        print("   This might be why the migration was stuck!")
    except Exception as e:
        print(f"\n❌ Error checking PostgreSQL: {e}")
else:
    print("\n❌ DATABASE_URL not set in environment")

print("\n" + "=" * 60)
