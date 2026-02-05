#!/usr/bin/env python3
"""
Check status of ALL positions to understand the $93 position value
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

# Get ALL bets
all_bets = conn.execute("""
    SELECT id, market_question, market_id, side, result, price, amount, size
    FROM bets 
    WHERE paper=0
    ORDER BY id
""").fetchall()

print("=" * 100)
print(f"CHECKING STATUS OF ALL {len(all_bets)} POSITIONS")
print("=" * 100)
print()

client = httpx.Client(timeout=30)
now = datetime.now(timezone.utc)

active_positions = []
resolved_positions = []
total_active_value = 0
total_resolved_value = 0

for bet in all_bets:
    market_id = bet['market_id']
    shares = bet['size'] / bet['price'] if bet['price'] > 0 else 0
    
    try:
        resp = client.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=10)
        if resp.status_code == 200:
            market = resp.json()
            
            closed = market.get('closed', False)
            active = market.get('active', True)
            accepting_orders = market.get('acceptingOrders', False)
            enable_orderbook = market.get('enableOrderBook', False)
            
            outcome_prices = market.get('outcomePrices', [])
            prices = []
            if outcome_prices:
                if isinstance(outcome_prices, list):
                    prices = [float(p) for p in outcome_prices]
                elif isinstance(outcome_prices, str):
                    if outcome_prices.startswith('['):
                        import json
                        prices = [float(p) for p in json.loads(outcome_prices)]
                    else:
                        prices = [float(p.strip().strip('"')) for p in outcome_prices.split(',')]
            
            # Determine our outcome index
            our_idx = 0 if bet['side'] == 'YES' else 1
            current_price = prices[our_idx] if len(prices) > our_idx else None
            
            # Calculate position value
            if current_price is not None:
                position_value = shares * current_price
            else:
                position_value = shares * 1.0 if bet['result'] == 'won' else 0.0
            
            is_still_active = active and accepting_orders and enable_orderbook and not closed and current_price and 0 < current_price < 1
            
            status_icon = "🔄" if is_still_active else "✅" if closed else "❓"
            
            print(f"{status_icon} Bet {bet['id']}: {bet['side']} {bet['market_question'][:50]}")
            print(f"   DB Status: {bet['result']} | Shares: {shares:.1f} | Entry: ${bet['price']:.2f}")
            print(f"   Market: closed={closed}, active={active}, accepting={accepting_orders}")
            print(f"   Prices: {prices} | Current (our side): {current_price}")
            print(f"   Position Value: ${position_value:.2f}")
            
            if is_still_active:
                print(f"   ⚠️  STILL ACTIVE - Value fluctuating")
                active_positions.append({
                    'bet': bet,
                    'position_value': position_value,
                    'current_price': current_price
                })
                total_active_value += position_value
            else:
                print(f"   ✅ RESOLVED - Final value: ${position_value:.2f}")
                resolved_positions.append({
                    'bet': bet,
                    'position_value': position_value,
                    'current_price': current_price
                })
                total_resolved_value += position_value
            
            print()
    except Exception as e:
        print(f"❌ Bet {bet['id']}: Error - {e}\n")

print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total positions: {len(all_bets)}")
print(f"🔄 Still active (fluctuating): {len(active_positions)} (${total_active_value:.2f})")
print(f"✅ Resolved: {len(resolved_positions)} (${total_resolved_value:.2f})")
print()

if active_positions:
    print("ACTIVE POSITIONS (these contribute to fluctuating $93):")
    for item in active_positions:
        bet = item['bet']
        print(f"  - Bet {bet['id']}: ${item['position_value']:.2f} @ ${item['current_price']:.2f} | {bet['market_question'][:50]}")

if resolved_positions:
    print(f"\nRESOLVED POSITIONS (need redemption if won):")
    won_resolved = [p for p in resolved_positions if p['bet']['result'] == 'won' and p['position_value'] > 0]
    print(f"  Won positions needing redemption: {len(won_resolved)} (${sum(p['position_value'] for p in won_resolved):.2f})")

conn.close()
client.close()
