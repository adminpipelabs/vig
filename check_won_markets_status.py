#!/usr/bin/env python3
"""
Check which won markets are still tradeable vs fully closed
This determines if we need to SELL (active) or REDEEM (closed)
"""
import os
import sqlite3
import httpx
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

conn = sqlite3.connect('/Users/mikaelo/vig/vig.db')
conn.row_factory = sqlite3.Row
won_bets = conn.execute("""
    SELECT id, market_question, condition_id, token_id, size, price, amount
    FROM bets 
    WHERE paper=0 AND result='won'
    ORDER BY placed_at DESC
""").fetchall()

print("=" * 100)
print(f"CHECKING {len(won_bets)} WON BETS")
print("=" * 100)
print()

sell_list = []
redeem_list = []

for bet in won_bets:
    condition_id = bet['condition_id']
    if not condition_id:
        print(f"⚠️  Bet {bet['id']}: {bet['market_question'][:50]}...")
        print(f"   Missing condition_id - skipping")
        print()
        continue
    
    try:
        r = httpx.get(f'https://clob.polymarket.com/markets/{condition_id}', timeout=10)
        if r.status_code != 200:
            print(f"❌ Bet {bet['id']}: {bet['market_question'][:50]}...")
            print(f"   API error: {r.status_code}")
            print()
            continue
            
        market = r.json()
        
        closed = market.get('closed', False)
        active = market.get('active', True)  # Default to True if not specified
        
        # Check outcome prices to see if resolved
        outcome_prices = market.get('outcomePrices', [])
        resolved = False
        if outcome_prices:
            prices = [float(p) for p in outcome_prices]
            resolved = any(p >= 0.95 or p <= 0.05 for p in prices)
        
        shares = bet['size'] / bet['price'] if bet['price'] > 0 else 0
        position_value = shares * 1.0  # Assuming $1 per share when won
        
        print(f"Bet {bet['id']}: {bet['market_question'][:60]}")
        print(f"  Condition ID: {condition_id}")
        print(f"  Token ID: {bet['token_id']}")
        print(f"  Shares: {shares:.2f}")
        print(f"  Position Value: ${position_value:.2f}")
        print(f"  closed={closed}, active={active}, resolved={resolved}")
        
        if closed or not active:
            action = "REDEEM"
            redeem_list.append({
                'bet': bet,
                'shares': shares,
                'position_value': position_value,
                'market': market
            })
        else:
            action = "SELL"
            sell_list.append({
                'bet': bet,
                'shares': shares,
                'position_value': position_value,
                'market': market
            })
        
        print(f"  → Action: {action}")
        print()
        
    except Exception as e:
        print(f"❌ Bet {bet['id']}: {bet['market_question'][:50]}...")
        print(f"   Error: {e}")
        print()

print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total won bets: {len(won_bets)}")
print(f"Need to SELL: {len(sell_list)} (${sum(s['position_value'] for s in sell_list):.2f})")
print(f"Need to REDEEM: {len(redeem_list)} (${sum(r['position_value'] for r in redeem_list):.2f})")
print()

if sell_list:
    print("SELL LIST:")
    for item in sell_list:
        print(f"  - Bet {item['bet']['id']}: {item['bet']['market_question'][:50]}... (${item['position_value']:.2f})")
    print()

if redeem_list:
    print("REDEEM LIST:")
    for item in redeem_list:
        print(f"  - Bet {item['bet']['id']}: {item['bet']['market_question'][:50]}... (${item['position_value']:.2f})")
    print()

conn.close()
