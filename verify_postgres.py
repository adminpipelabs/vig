#!/usr/bin/env python3
"""Verify PostgreSQL connection and data"""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

db_url = os.getenv('DATABASE_URL')

if not db_url:
    print('❌ DATABASE_URL not found')
    exit(1)

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM bets')
    bet_count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM windows')
    window_count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM circuit_breaker_log')
    log_count = cur.fetchone()[0]

    print('✅ PostgreSQL Database Status:')
    print(f'   - {bet_count} bets')
    print(f'   - {window_count} windows')
    print(f'   - {log_count} circuit breaker logs')

    # Check recent bets
    cur.execute('SELECT id, market_question, result, amount, profit FROM bets ORDER BY id DESC LIMIT 5')
    recent = cur.fetchall()
    if recent:
        print('\n📊 Recent bets:')
        for r in recent:
            question = r[1][:40] if r[1] else 'N/A'
            print(f'   Bet {r[0]}: {question}... | {r[2]} | ${r[3]:.2f} | P&L: ${r[4]:.2f}')

    conn.close()
    print('\n✅ Connection successful! PostgreSQL is ready.')
    
except Exception as e:
    print(f'❌ Error: {e}')
    exit(1)
