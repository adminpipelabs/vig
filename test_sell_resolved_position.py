#!/usr/bin/env python3
"""
Test selling a resolved winning position to see if we can convert shares to cash
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

print("=" * 100)
print("TEST SELLING RESOLVED WINNING POSITION")
print("=" * 100)
print()

client = ClobClient(
    'https://clob.polymarket.com',
    key=os.getenv('POLYGON_PRIVATE_KEY'),
    chain_id=137
)
client.set_api_creds(client.create_or_derive_api_creds())

# Get one won bet from database
conn = sqlite3.connect('/Users/mikaelo/vig/vig.db')
conn.row_factory = sqlite3.Row
won_bet = conn.execute("""
    SELECT id, market_question, condition_id, token_id, size, price, side
    FROM bets 
    WHERE paper=0 AND result='won'
    LIMIT 1
""").fetchone()

if not won_bet:
    print("❌ No won bets found in database")
    exit(1)

print(f"Testing with bet {won_bet['id']}:")
print(f"  Market: {won_bet['market_question'][:60]}")
print(f"  Token ID: {won_bet['token_id']}")
print(f"  Side: {won_bet['side']}")
print(f"  Size: {won_bet['size']}")
print(f"  Price: {won_bet['price']}")
print()

# Calculate shares
shares = won_bet['size'] / won_bet['price']
print(f"Shares owned: {shares:.2f}")
print()

# Check if market is still active
print("1. Checking market status...")
try:
    import httpx
    r = httpx.get(f'https://clob.polymarket.com/markets/{won_bet["condition_id"]}', timeout=10)
    if r.status_code == 200:
        market = r.json()
        closed = market.get('closed', False)
        active = market.get('active', True)
        print(f"   Market closed: {closed}")
        print(f"   Market active: {active}")
        
        if closed or not active:
            print("   ⚠️  Market is closed - may not be able to sell")
        else:
            print("   ✅ Market appears active - should be able to sell")
    else:
        print(f"   ⚠️  Could not fetch market data: {r.status_code}")
except Exception as e:
    print(f"   ⚠️  Error checking market: {e}")
print()

# Try to create a sell order
print("2. Attempting to create SELL order...")
print(f"   Token ID: {won_bet['token_id']}")
print(f"   Price: $0.99 (will fill at market price)")
print(f"   Size: {shares:.2f} shares")
print()

try:
    order_args = OrderArgs(
        token_id=won_bet['token_id'],
        price=0.99,
        size=round(shares, 2),
        side=SELL
    )
    
    print("   Creating order...")
    signed_order = client.create_order(order_args)
    print(f"   ✅ Order created: {signed_order}")
    print()
    
    print("   Posting order (FOK - Fill or Kill)...")
    response = client.post_order(signed_order, OrderType.FOK)
    print(f"   ✅ Response: {response}")
    print()
    
    print("   🎉 SUCCESS! Position sold. Check balance.")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    print()
    print("   This could mean:")
    print("   - Market is fully closed and not tradeable")
    print("   - Need to use REDEEM instead of SELL")
    print("   - Positions are held by exchange, not wallet")
    print("   - Need different API method")
    
    import traceback
    print()
    print("   Full traceback:")
    traceback.print_exc()

conn.close()
