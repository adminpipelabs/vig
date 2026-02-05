#!/usr/bin/env python3
"""
Backfill condition_id for existing bets by looking up from market_id
"""
import sqlite3
import httpx
import time

db = sqlite3.connect('vig.db')
db.row_factory = sqlite3.Row

# Get all bets missing condition_id
bets = db.execute("""
    SELECT id, market_id, market_question
    FROM bets 
    WHERE condition_id IS NULL OR condition_id = ''
    ORDER BY placed_at
""").fetchall()

print(f"Found {len(bets)} bets missing condition_id")
print("Looking up condition_ids from Gamma API...\n")

updated = 0
for i, bet in enumerate(bets, 1):
    market_id = bet['market_id']
    print(f"[{i}/{len(bets)}] Market {market_id}: {bet['market_question'][:50]}...")
    
    try:
        resp = httpx.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=10)
        if resp.status_code == 200:
            market = resp.json()
            condition_id = market.get('conditionId', '')
            if condition_id:
                db.execute("UPDATE bets SET condition_id = ? WHERE id = ?", (condition_id, bet['id']))
                db.commit()
                print(f"  ✅ Updated: {condition_id[:20]}...")
                updated += 1
            else:
                print(f"  ⚠️  No conditionId in API response")
        else:
            print(f"  ❌ API returned {resp.status_code}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    time.sleep(0.5)  # Rate limit

print(f"\n✅ Updated {updated} bets with condition_id")

db.close()
