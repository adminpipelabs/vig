#!/usr/bin/env python3
"""
Check if "won" bets are actually resolved or still active positions
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

won_bets = conn.execute("""
    SELECT id, market_question, market_id, condition_id, size, price, amount, resolved_at
    FROM bets 
    WHERE paper=0 AND result='won'
    ORDER BY resolved_at DESC
""").fetchall()

print("=" * 100)
print(f"CHECKING STATUS OF {len(won_bets)} 'WON' BETS")
print("=" * 100)
print()

client = httpx.Client(timeout=30)
now = datetime.now(timezone.utc)

still_active = []
resolved = []
total_active_value = 0

for bet in won_bets:
    market_id = bet['market_id']
    shares = bet['size'] / bet['price'] if bet['price'] > 0 else 0
    
    try:
        resp = client.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=10)
        if resp.status_code == 200:
            market = resp.json()
            
            closed = market.get('closed', False)
            active = market.get('active', True)
            outcome_prices = market.get('outcomePrices', [])
            
            # Parse prices
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
            
            # Check if market is still tradeable
            accepting_orders = market.get('acceptingOrders', False)
            enable_orderbook = market.get('enableOrderBook', False)
            
            is_still_active = active and accepting_orders and enable_orderbook and not closed
            
            position_value = shares * 1.0  # Assuming $1 per share if won
            
            if prices:
                # Use current price if available
                our_index = 0  # Assuming YES side
                current_price = prices[our_index] if len(prices) > our_index else 1.0
                position_value = shares * current_price
            
            print(f"Bet {bet['id']}: {bet['market_question'][:50]}")
            print(f"  Shares: {shares:.2f} | Position value: ${position_value:.2f}")
            print(f"  Closed: {closed} | Active: {active} | Accepting orders: {accepting_orders}")
            print(f"  Outcome prices: {prices}")
            
            if is_still_active:
                print(f"  ⚠️  STILL ACTIVE - Market hasn't fully closed yet")
                still_active.append({
                    'bet': bet,
                    'position_value': position_value,
                    'prices': prices
                })
                total_active_value += position_value
            else:
                print(f"  ✅ RESOLVED - Market is closed")
                resolved.append({
                    'bet': bet,
                    'position_value': position_value
                })
            
            print()
    except Exception as e:
        print(f"Bet {bet['id']}: Error - {e}\n")

print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total 'won' bets: {len(won_bets)}")
print(f"Still active positions: {len(still_active)} (${total_active_value:.2f})")
print(f"Fully resolved: {len(resolved)}")
print()

if still_active:
    print("STILL ACTIVE POSITIONS (these are the fluctuating $93):")
    for item in still_active:
        bet = item['bet']
        print(f"  - Bet {bet['id']}: ${item['position_value']:.2f} | Prices: {item['prices']}")
    print()
    print("These positions are still on active markets, so their value fluctuates.")
    print("They need to wait for markets to fully close before they can be redeemed.")

conn.close()
client.close()
