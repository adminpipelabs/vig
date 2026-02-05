#!/usr/bin/env python3
"""Simple migration test - just migrate 100 windows to test connection"""
import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = os.getenv("DATABASE_URL")
if not POSTGRES_URL:
    print("❌ DATABASE_URL not set")
    exit(1)

print("Testing PostgreSQL connection...")
try:
    pg_conn = psycopg2.connect(POSTGRES_URL)
    pg_cur = pg_conn.cursor()
    pg_cur.execute("SELECT version()")
    print(f"✅ Connected: {pg_cur.fetchone()[0][:50]}...")
    
    # Test insert speed
    print("\nTesting insert speed with 100 rows...")
    import time
    start = time.time()
    
    test_data = [(f"test_{i}", None, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 10.0, "growth") for i in range(100)]
    pg_cur.executemany("""
        INSERT INTO windows (started_at, ended_at, bets_placed, bets_won, bets_lost, bets_pending,
                             deployed, returned, profit, pocketed, clip_size, phase)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, test_data)
    pg_conn.commit()
    
    elapsed = time.time() - start
    print(f"✅ Inserted 100 rows in {elapsed:.2f} seconds")
    print(f"   Rate: {100/elapsed:.0f} rows/second")
    print(f"   Estimated time for 33,160 windows: {(33160/100)*elapsed/60:.1f} minutes")
    
    # Clean up test data
    pg_cur.execute("DELETE FROM windows WHERE started_at LIKE 'test_%'")
    pg_conn.commit()
    
    pg_conn.close()
    print("\n✅ Connection test successful!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
