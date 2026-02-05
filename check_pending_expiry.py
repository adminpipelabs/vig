#!/usr/bin/env python3
"""
Check when pending bets actually expire to verify expiry filter bug
"""
import os
import sqlite3
import httpx
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

conn = sqlite3.connect('/Users/mikaelo/vig/vig.db')
conn.row_factory = sqlite3.Row

pending_bets = conn.execute("""
    SELECT id, market_question, market_id, condition_id, placed_at, amount, price, size
    FROM bets 
    WHERE paper=0 AND result='pending'
    ORDER BY placed_at
""").fetchall()

print("=" * 100)
print(f"CHECKING EXPIRY TIMES FOR {len(pending_bets)} PENDING BETS")
print("=" * 100)
print()

now = datetime.now(timezone.utc)
client = httpx.Client(timeout=30)

for bet in pending_bets:
    market_id = bet['market_id']
    placed_at = datetime.fromisoformat(bet['placed_at'].replace('Z', '+00:00'))
    time_since_placed = (now - placed_at).total_seconds() / 60
    
    print(f"Bet {bet['id']}: {bet['market_question'][:60]}")
    print(f"  Placed: {placed_at.strftime('%Y-%m-%d %H:%M:%S UTC')} ({time_since_placed:.1f} minutes ago)")
    print(f"  Amount: ${bet['amount']:.2f}")
    
    try:
        # Try Gamma API first
        resp = client.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=10)
        if resp.status_code == 200:
            market = resp.json()
            end_date_str = market.get('endDate') or market.get('endDateIso', '')
            
            if end_date_str:
                # Parse end date
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                           "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        end_date = datetime.strptime(end_date_str.replace('Z', ''), fmt.replace('Z', ''))
                        end_date = end_date.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    end_date = None
                
                if end_date:
                    minutes_to_expiry = (end_date - now).total_seconds() / 60
                    hours_to_expiry = minutes_to_expiry / 60
                    
                    print(f"  Expires: {end_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    print(f"  Time to expiry: {minutes_to_expiry:.1f} minutes ({hours_to_expiry:.2f} hours)")
                    
                    if minutes_to_expiry > 60:
                        print(f"  ⚠️  BUG: Market expires in {hours_to_expiry:.1f} hours (should be < 60 min)")
                    elif minutes_to_expiry < 5:
                        print(f"  ⚠️  Market expires very soon ({minutes_to_expiry:.1f} min)")
                    else:
                        print(f"  ✅ Within 5-60 min window")
                    
                    # Check if market is closed
                    closed = market.get('closed', False)
                    if closed:
                        print(f"  ⚠️  Market is CLOSED but bet still pending")
                else:
                    print(f"  ❌ Could not parse end date: {end_date_str}")
            else:
                print(f"  ❌ No end date in market data")
        else:
            print(f"  ❌ API error: {resp.status_code}")
    except Exception as e:
        print(f"  ❌ Error fetching market: {e}")
    
    print()

# Summary
print("=" * 100)
print("SUMMARY")
print("=" * 100)

total_pending_value = sum(b['amount'] for b in pending_bets)
print(f"Total pending bets: {len(pending_bets)}")
print(f"Total pending value: ${total_pending_value:.2f}")
print()
print("If markets expire in > 60 minutes, the expiry filter bug is confirmed.")
print("The bot should only bet on markets expiring within 5-60 minutes.")

conn.close()
client.close()
