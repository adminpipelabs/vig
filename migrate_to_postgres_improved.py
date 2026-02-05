#!/usr/bin/env python3
"""
Improved Migration Script with Error Handling and Progress Tracking
Migrate SQLite database to PostgreSQL with better error handling
"""
import os
import sqlite3
import psycopg2
import sys
from pathlib import Path
from dotenv import load_dotenv
from psycopg2 import OperationalError

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

SQLITE_DB = os.getenv("DB_PATH", "vig.db")
POSTGRES_URL = os.getenv("DATABASE_URL")

if not POSTGRES_URL:
    print("❌ DATABASE_URL not found in environment")
    print("   Set DATABASE_URL=postgresql://user:pass@host:port/dbname")
    sys.exit(1)

print("=" * 80)
print("SQLITE → POSTGRESQL MIGRATION (IMPROVED)")
print("=" * 80)
print()

# Connect to SQLite
print(f"📂 Reading from SQLite: {SQLITE_DB}")
if not os.path.exists(SQLITE_DB):
    print(f"❌ SQLite database not found: {SQLITE_DB}")
    sys.exit(1)

sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_conn.row_factory = sqlite3.Row

# Connect to PostgreSQL with timeout and retry
print(f"📊 Connecting to PostgreSQL...")
max_retries = 3
retry_delay = 2
pg_conn = None

for attempt in range(max_retries):
    try:
        print(f"  Attempt {attempt + 1}/{max_retries}...")
        pg_conn = psycopg2.connect(POSTGRES_URL, connect_timeout=10)
        pg_conn.set_session(autocommit=False)
        print("✅ Connected to PostgreSQL!")
        break
    except OperationalError as e:
        print(f"  ❌ Connection failed: {e}")
        if attempt < max_retries - 1:
            print(f"  Retrying in {retry_delay} seconds...")
            import time
            time.sleep(retry_delay)
        else:
            print("❌ Could not connect to PostgreSQL after multiple attempts")
            sqlite_conn.close()
            sys.exit(1)

if not pg_conn:
    print("❌ Failed to establish PostgreSQL connection")
    sqlite_conn.close()
    sys.exit(1)

pg_cur = pg_conn.cursor()

# Create tables in PostgreSQL
print("\n🔨 Creating tables in PostgreSQL...")
try:
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
except Exception as e:
    print(f"❌ Error creating tables: {e}")
    pg_conn.rollback()
    sqlite_conn.close()
    pg_conn.close()
    sys.exit(1)

# Check if data already exists (idempotent check)
print("\n🔍 Checking existing data in PostgreSQL...")
try:
    pg_cur.execute("SELECT COUNT(*) FROM bets")
    existing_bets = pg_cur.fetchone()[0]
    pg_cur.execute("SELECT COUNT(*) FROM windows")
    existing_windows = pg_cur.fetchone()[0]
    print(f"  Existing: {existing_bets} bets, {existing_windows} windows")
except Exception as e:
    print(f"  ⚠️  Could not check existing data: {e}")

# Migrate bets
print("\n📥 Migrating bets...")
sqlite_cur = sqlite_conn.cursor()
sqlite_cur.execute("SELECT * FROM bets ORDER BY id")
bets = sqlite_cur.fetchall()

if bets:
    try:
        # Check if bets already exist
        if existing_bets > 0:
            print(f"  ⚠️  {existing_bets} bets already exist. Skipping bets migration.")
            print("  (Delete existing bets first if you want to re-migrate)")
        else:
            bet_data = []
            for b in bets:
                bet_data.append((
                    b['window_id'], b['platform'], b['market_id'],
                    b['condition_id'] if 'condition_id' in b.keys() else '',
                    b['market_question'], b['token_id'], b['side'], b['price'], b['amount'], b['size'],
                    b['order_id'], b['placed_at'],
                    b['resolved_at'] if 'resolved_at' in b.keys() else None,
                    b['result'], b['payout'], b['profit'], bool(b['paper'])
                ))
            
            pg_cur.executemany("""
                INSERT INTO bets (window_id, platform, market_id, condition_id, market_question, token_id,
                                  side, price, amount, size, order_id, placed_at, resolved_at,
                                  result, payout, profit, paper)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, bet_data)
            pg_conn.commit()
            print(f"✅ Migrated {len(bets)} bets")
    except Exception as e:
        print(f"❌ Error migrating bets: {e}")
        pg_conn.rollback()
else:
    print("⚠️  No bets to migrate")

# Migrate windows with improved progress tracking
print("\n📥 Migrating windows...")
sqlite_cur.execute("SELECT * FROM windows ORDER BY id")
windows = sqlite_cur.fetchall()

if windows:
    try:
        # Check if windows already exist
        if existing_windows > 0:
            print(f"  ⚠️  {existing_windows} windows already exist.")
            response = input("  Delete existing windows and re-migrate? (yes/no): ")
            if response.lower() != 'yes':
                print("  Skipping windows migration.")
            else:
                print("  Deleting existing windows...")
                pg_cur.execute("DELETE FROM windows")
                pg_conn.commit()
                existing_windows = 0
        
        if existing_windows == 0:
            window_data = []
            for w in windows:
                window_data.append((
                    w['started_at'],
                    w['ended_at'] if 'ended_at' in w.keys() else None,
                    w['bets_placed'], w['bets_won'], w['bets_lost'],
                    w['bets_pending'], w['deployed'], w['returned'], w['profit'], w['pocketed'],
                    w['clip_size'], w['phase']
                ))
            
            # Use batch inserts with progress tracking for EVERY batch
            batch_size = 1000
            total_inserted = 0
            total_batches = (len(window_data) + batch_size - 1) // batch_size
            
            print(f"  Migrating {len(window_data)} windows in {total_batches} batches...")
            
            for i in range(0, len(window_data), batch_size):
                batch = window_data[i:i+batch_size]
                batch_num = (i // batch_size) + 1
                
                try:
                    pg_cur.executemany("""
                        INSERT INTO windows (started_at, ended_at, bets_placed, bets_won, bets_lost, bets_pending,
                                             deployed, returned, profit, pocketed, clip_size, phase)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, batch)
                    total_inserted += len(batch)
                    
                    # Show progress for EVERY batch
                    print(f"  ✅ Batch {batch_num}/{total_batches}: {total_inserted}/{len(window_data)} windows ({total_inserted*100//len(window_data)}%)")
                    
                    # Commit every 5 batches to avoid too many commits
                    if batch_num % 5 == 0:
                        pg_conn.commit()
                        print(f"     💾 Committed progress...")
                        
                except Exception as e:
                    print(f"  ❌ Error in batch {batch_num}: {e}")
                    pg_conn.rollback()
                    print(f"  ⚠️  Migration stopped at batch {batch_num}. {total_inserted} windows migrated so far.")
                    raise
            
            # Final commit
            pg_conn.commit()
            print(f"\n✅ Successfully migrated {total_inserted} windows")
            
    except Exception as e:
        print(f"❌ Error migrating windows: {e}")
        import traceback
        traceback.print_exc()
        pg_conn.rollback()
else:
    print("⚠️  No windows to migrate")

# Migrate circuit_breaker_log
print("\n📥 Migrating circuit_breaker_log...")
sqlite_cur.execute("SELECT * FROM circuit_breaker_log ORDER BY id")
logs = sqlite_cur.fetchall()

if logs:
    try:
        log_data = []
        for l in logs:
            log_data.append((
                l['triggered_at'],
                l['reason'] if 'reason' in l.keys() else None,
                l['clip_at_trigger'] if 'clip_at_trigger' in l.keys() else None,
                l['resolved_at'] if 'resolved_at' in l.keys() else None,
                l['action_taken'] if 'action_taken' in l.keys() else None
            ))
        
        pg_cur.executemany("""
            INSERT INTO circuit_breaker_log (triggered_at, reason, clip_at_trigger, resolved_at, action_taken)
            VALUES (%s, %s, %s, %s, %s)
        """, log_data)
        pg_conn.commit()
        print(f"✅ Migrated {len(logs)} circuit breaker logs")
    except Exception as e:
        print(f"❌ Error migrating logs: {e}")
        pg_conn.rollback()
else:
    print("⚠️  No circuit breaker logs to migrate")

# Verify
print("\n🔍 Verifying migration...")
try:
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
except Exception as e:
    print(f"⚠️  Could not verify: {e}")

sqlite_conn.close()
pg_conn.close()

print("\n" + "=" * 80)
print("✅ MIGRATION COMPLETE")
print("=" * 80)
