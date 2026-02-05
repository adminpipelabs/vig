#!/usr/bin/env python3
"""
Check redemption status and wallet configuration
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

print("=" * 80)
print("REDEMPTION STATUS CHECK")
print("=" * 80)

# Check wallet config
print("\n1. WALLET CONFIGURATION")
print("-" * 80)
funder_address = os.getenv("POLYGON_FUNDER_ADDRESS", "")
signature_type = int(os.getenv("SIGNATURE_TYPE", "0"))
print(f"POLYGON_FUNDER_ADDRESS: {funder_address}")
print(f"SIGNATURE_TYPE: {signature_type}")

if signature_type == 0 and not funder_address:
    print("✅ Pure EOA wallet (can redeem programmatically)")
elif signature_type == 0 and funder_address:
    print("⚠️  EOA with funder address (may need manual redemption)")
else:
    print("⚠️  Proxy/Safe wallet (may need manual redemption via Polymarket.com)")

# Check database schema
print("\n2. DATABASE SCHEMA")
print("-" * 80)
db = sqlite3.connect('vig.db')
db.row_factory = sqlite3.Row

schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bets'").fetchone()
print("Bets table schema:")
print(schema['sql'] if schema else "Not found")

# Check if condition_id exists
columns = [row[1] for row in db.execute("PRAGMA table_info(bets)").fetchall()]
has_condition_id = 'condition_id' in columns
print(f"\nHas condition_id column: {has_condition_id}")

# Get won bets info
print("\n3. WON BETS STATUS")
print("-" * 80)
won_bets = db.execute("""
    SELECT id, market_id, token_id, size, payout, profit
    FROM bets 
    WHERE result='won'
    ORDER BY placed_at DESC
    LIMIT 5
""").fetchall()

print(f"Total won bets: {len(won_bets)}")
print("\nSample won bets:")
for bet in won_bets:
    print(f"  Bet #{bet['id']}:")
    print(f"    Market ID: {bet['market_id']}")
    print(f"    Token ID: {bet['token_id'][:30] if bet['token_id'] else 'N/A'}...")
    print(f"    Size: {bet['size']:.2f}")
    print(f"    Payout: ${bet['payout']:.2f}")

# Check if we can look up condition_id from market_id
print("\n4. CONDITION_ID LOOKUP TEST")
print("-" * 80)
if won_bets:
    test_market_id = won_bets[0]['market_id']
    print(f"Testing lookup for market_id: {test_market_id}")
    
    try:
        import httpx
        resp = httpx.get(f"https://gamma-api.polymarket.com/markets/{test_market_id}", timeout=10)
        if resp.status_code == 200:
            market = resp.json()
            condition_id = market.get('conditionId', '')
            print(f"✅ Found condition_id: {condition_id}")
            print(f"   Can look up condition_id from market_id via Gamma API")
        else:
            print(f"❌ Gamma API returned {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

db.close()

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"""
1. Wallet Type: {'Pure EOA' if signature_type == 0 and not funder_address else 'Proxy/Safe or EOA with funder'}
2. condition_id in DB: {'✅ Yes' if has_condition_id else '❌ No - need to add'}
3. Can look up condition_id: {'✅ Yes (via Gamma API)' if won_bets else 'N/A'}

NEXT STEPS:
- If Pure EOA: Can implement programmatic redemption
- If Proxy/Safe: Must redeem manually on Polymarket.com
- If condition_id missing: Need to add to DB schema and bet_manager.py
""")
