#!/usr/bin/env python3
"""
Fast Migration: SQLite → PostgreSQL using COPY (much faster!)
Uses PostgreSQL COPY command for bulk import - 100-1000x faster than INSERT
"""
import os
import sqlite3
import psycopg2
from io import StringIO
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
print("FAST SQLITE → POSTGRESQL MIGRATION (using COPY)")
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

# Clear existing data (if any)
print("🧹 Clearing existing data...")
pg_cur.execute("TRUNCATE TABLE bets, windows, circuit_breaker_log CASCADE")
pg_conn.commit()
print("✅ Tables cleared")

# Migrate bets using COPY (fast!)
print("\n📥 Migrating bets (using COPY)...")
sqlite_cur = sqlite_conn.cursor()
sqlite_cur.execute("SELECT * FROM bets ORDER BY id")
bets = sqlite_cur.fetchall()

if bets:
    # Prepare data for COPY
    output = StringIO()
    for b in bets:
        def escape_csv(val):
            if val is None:
                return '\\N'
            s = str(val)
            # Escape special characters for COPY
            s = s.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return s
        
        row = [
            b.get('window_id') or '\\N',
            escape_csv(b.get('platform', 'polymarket')),
            escape_csv(b.get('market_id', '')),
            escape_csv(b.get('condition_id', '')),
            escape_csv(b.get('market_question', '')),
            escape_csv(b.get('token_id', '')),
            escape_csv(b.get('side', '')),
            b.get('price') or '\\N',
            b.get('amount') or '\\N',
            b.get('size') or '\\N',
            escape_csv(b.get('order_id', '')),
            escape_csv(b.get('placed_at', '')),
            escape_csv(b.get('resolved_at')),
            escape_csv(b.get('result', 'pending')),
            b.get('payout') or '\\N',
            b.get('profit') or '\\N',
            't' if b.get('paper', True) else 'f'
        ]
        output.write('\t'.join(str(x) for x in row) + '\n')
    
    output.seek(0)
    
    # Use COPY for fast bulk insert
    pg_cur.copy_from(
        output,
        'bets',
        columns=('window_id', 'platform', 'market_id', 'condition_id', 'market_question', 
                 'token_id', 'side', 'price', 'amount', 'size', 'order_id', 'placed_at', 
                 'resolved_at', 'result', 'payout', 'profit', 'paper'),
        null='\\N'
    )
    pg_conn.commit()
    print(f"✅ Migrated {len(bets)} bets")
else:
    print("⚠️  No bets to migrate")

# Migrate windows using COPY (fast!)
print("\n📥 Migrating windows (using COPY)...")
sqlite_cur.execute("SELECT * FROM windows ORDER BY id")
windows = sqlite_cur.fetchall()

if windows:
    output = StringIO()
    for w in windows:
        def escape_csv(val):
            if val is None:
                return '\\N'
            s = str(val)
            return s.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        
        row = [
            escape_csv(w.get('started_at', '')),
            escape_csv(w.get('ended_at')),
            w.get('bets_placed') or '\\N',
            w.get('bets_won') or '\\N',
            w.get('bets_lost') or '\\N',
            w.get('bets_pending') or '\\N',
            w.get('deployed') or '\\N',
            w.get('returned') or '\\N',
            w.get('profit') or '\\N',
            w.get('pocketed') or '\\N',
            w.get('clip_size') or '\\N',
            escape_csv(w.get('phase', 'growth'))
        ]
        output.write('\t'.join(str(x) for x in row) + '\n')
    
    output.seek(0)
    
    # Use COPY for fast bulk insert
    pg_cur.copy_from(
        output,
        'windows',
        columns=('started_at', 'ended_at', 'bets_placed', 'bets_won', 'bets_lost', 
                 'bets_pending', 'deployed', 'returned', 'profit', 'pocketed', 'clip_size', 'phase'),
        null='\\N'
    )
    pg_conn.commit()
    print(f"✅ Migrated {len(windows)} windows")
else:
    print("⚠️  No windows to migrate")

# Migrate circuit_breaker_log using COPY
print("\n📥 Migrating circuit_breaker_log (using COPY)...")
sqlite_cur.execute("SELECT * FROM circuit_breaker_log ORDER BY id")
logs = sqlite_cur.fetchall()

if logs:
    output = StringIO()
    for l in logs:
        def escape_csv(val):
            if val is None:
                return '\\N'
            s = str(val)
            return s.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        
        row = [
            escape_csv(l.get('triggered_at', '')),
            escape_csv(l.get('reason')),
            l.get('clip_at_trigger') or '\\N',
            escape_csv(l.get('resolved_at')),
            escape_csv(l.get('action_taken'))
        ]
        output.write('\t'.join(str(x) for x in row) + '\n')
    
    output.seek(0)
    
    pg_cur.copy_from(
        output,
        'circuit_breaker_log',
        columns=('triggered_at', 'reason', 'clip_at_trigger', 'resolved_at', 'action_taken'),
        null='\\N'
    )
    pg_conn.commit()
    print(f"✅ Migrated {len(logs)} circuit breaker logs")
else:
    print("⚠️  No circuit breaker logs to migrate")

# Verify
print("\n🔍 Verifying migration...")
pg_cur.execute("SELECT COUNT(*) FROM bets")
bet_count = pg_cur.fetchone()[0]
pg_cur.execute("SELECT COUNT(*) FROM windows")
window_count = pg_cur.fetchone()[0]
pg_cur.execute("SELECT COUNT(*) FROM circuit_breaker_log")
log_count = pg_cur.fetchone()[0]

print(f"✅ PostgreSQL now has:")
print(f"   - {bet_count} bets")
print(f"   - {window_count} windows")
print(f"   - {log_count} circuit breaker logs")

sqlite_conn.close()
pg_conn.close()

print("\n" + "=" * 80)
print("✅ FAST MIGRATION COMPLETE!")
print("=" * 80)
print("\nThis used PostgreSQL COPY command - much faster than INSERT!")
print("Next steps:")
print("1. Start bot: python3.11 main.py")
print("2. Bot will use PostgreSQL automatically")
