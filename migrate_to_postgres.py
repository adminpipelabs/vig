#!/usr/bin/env python3
"""
Migrate SQLite database to PostgreSQL
Exports data from SQLite and imports to PostgreSQL
"""
import os
import sqlite3
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

SQLITE_DB = os.getenv("DB_PATH", "vig.db")
POSTGRES_URL = os.getenv("DATABASE_URL")

if not POSTGRES_URL:
    print("❌ DATABASE_URL not found in environment")
    print("   Set DATABASE_URL=postgresql://user:pass@host:port/dbname")
    exit(1)

print("=" * 80)
print("SQLITE → POSTGRESQL MIGRATION")
print("=" * 80)
print()

# Connect to SQLite
print(f"📂 Reading from SQLite: {SQLITE_DB}")
sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_conn.row_factory = sqlite3.Row

# Connect to PostgreSQL
print(f"📊 Connecting to PostgreSQL...")
pg_conn = psycopg2.connect(POSTGRES_URL)
pg_conn.set_session(autocommit=False)
pg_cur = pg_conn.cursor()

# Create tables in PostgreSQL
print("🔨 Creating tables in PostgreSQL...")
pg_cur.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        id SERIAL PRIMARY KEY,
        window_id INTEGER,
        platform TEXT,
        market_id TEXT,
        condition_id TEXT,
        market_question TEXT,
        token_id TEXT,
        side TEXT,
        price REAL,
        amount REAL,
        size REAL,
        order_id TEXT,
        placed_at TEXT,
        resolved_at TEXT,
        result TEXT DEFAULT 'pending',
        payout REAL DEFAULT 0,
        profit REAL DEFAULT 0,
        paper BOOLEAN DEFAULT TRUE
    )
""")

pg_cur.execute("""
    CREATE TABLE IF NOT EXISTS windows (
        id SERIAL PRIMARY KEY,
        started_at TEXT,
        ended_at TEXT,
        bets_placed INTEGER DEFAULT 0,
        bets_won INTEGER DEFAULT 0,
        bets_lost INTEGER DEFAULT 0,
        bets_pending INTEGER DEFAULT 0,
        deployed REAL DEFAULT 0,
        returned REAL DEFAULT 0,
        profit REAL DEFAULT 0,
        pocketed REAL DEFAULT 0,
        clip_size REAL DEFAULT 0,
        phase TEXT DEFAULT 'growth'
    )
""")

pg_cur.execute("""
    CREATE TABLE IF NOT EXISTS circuit_breaker_log (
        id SERIAL PRIMARY KEY,
        triggered_at TEXT,
        reason TEXT,
        clip_at_trigger REAL,
        resolved_at TEXT,
        action_taken TEXT
    )
""")

pg_conn.commit()
print("✅ Tables created")

# Migrate bets
print("\n📥 Migrating bets...")
sqlite_cur = sqlite_conn.cursor()
sqlite_cur.execute("SELECT * FROM bets ORDER BY id")
bets = sqlite_cur.fetchall()

if bets:
    pg_cur.executemany("""
        INSERT INTO bets (window_id, platform, market_id, condition_id, market_question, token_id,
                          side, price, amount, size, order_id, placed_at, resolved_at,
                          result, payout, profit, paper)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (b['window_id'], b['platform'], b['market_id'], b.get('condition_id', ''),
         b['market_question'], b['token_id'], b['side'], b['price'], b['amount'], b['size'],
         b['order_id'], b['placed_at'], b.get('resolved_at'), b['result'],
         b['payout'], b['profit'], bool(b['paper']))
        for b in bets
    ])
    print(f"✅ Migrated {len(bets)} bets")
else:
    print("⚠️  No bets to migrate")

# Migrate windows
print("\n📥 Migrating windows...")
sqlite_cur.execute("SELECT * FROM windows ORDER BY id")
windows = sqlite_cur.fetchall()

if windows:
    pg_cur.executemany("""
        INSERT INTO windows (started_at, ended_at, bets_placed, bets_won, bets_lost, bets_pending,
                             deployed, returned, profit, pocketed, clip_size, phase)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (w['started_at'], w.get('ended_at'), w['bets_placed'], w['bets_won'], w['bets_lost'],
         w['bets_pending'], w['deployed'], w['returned'], w['profit'], w['pocketed'],
         w['clip_size'], w['phase'])
        for w in windows
    ])
    print(f"✅ Migrated {len(windows)} windows")
else:
    print("⚠️  No windows to migrate")

# Migrate circuit_breaker_log
print("\n📥 Migrating circuit_breaker_log...")
sqlite_cur.execute("SELECT * FROM circuit_breaker_log ORDER BY id")
logs = sqlite_cur.fetchall()

if logs:
    pg_cur.executemany("""
        INSERT INTO circuit_breaker_log (triggered_at, reason, clip_at_trigger, resolved_at, action_taken)
        VALUES (%s, %s, %s, %s, %s)
    """, [
        (l['triggered_at'], l.get('reason'), l.get('clip_at_trigger'),
         l.get('resolved_at'), l.get('action_taken'))
        for l in logs
    ])
    print(f"✅ Migrated {len(logs)} circuit breaker logs")
else:
    print("⚠️  No circuit breaker logs to migrate")

pg_conn.commit()

# Verify
print("\n🔍 Verifying migration...")
pg_cur.execute("SELECT COUNT(*) FROM bets")
bet_count = pg_cur.fetchone()[0]
pg_cur.execute("SELECT COUNT(*) FROM windows")
window_count = pg_cur.fetchone()[0]

print(f"✅ PostgreSQL now has:")
print(f"   - {bet_count} bets")
print(f"   - {window_count} windows")

sqlite_conn.close()
pg_conn.close()

print("\n" + "=" * 80)
print("✅ MIGRATION COMPLETE")
print("=" * 80)
print("\nNext steps:")
print("1. Update bot to use DATABASE_URL environment variable")
print("2. Update dashboard to use DATABASE_URL")
print("3. Test connection")
print("\nTo use PostgreSQL, set in .env:")
print("DATABASE_URL=postgresql://user:pass@host:port/dbname")
