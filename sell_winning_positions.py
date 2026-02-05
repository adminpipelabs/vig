#!/usr/bin/env python3
"""
Sell winning positions to recover cash
Tests both active (SELL) and closed (try SELL first, then investigate REDEEM)
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL
import httpx

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

client = ClobClient(
    'https://clob.polymarket.com',
    key=os.getenv('POLYGON_PRIVATE_KEY'),
    chain_id=137
)
client.set_api_creds(client.create_or_derive_api_creds())

# Get won bets from database
conn = sqlite3.connect('/Users/mikaelo/vig/vig.db')
conn.row_factory = sqlite3.Row
won_bets = conn.execute("""
    SELECT id, market_question, condition_id, token_id, size, price
    FROM bets 
    WHERE paper=0 AND result='won'
    ORDER BY placed_at DESC
""").fetchall()

print("=" * 100)
print(f"ATTEMPTING TO SELL {len(won_bets)} WINNING POSITIONS")
print("=" * 100)
print()

successful_sells = []
failed_sells = []

for bet in won_bets:
    if not bet['token_id']:
        print(f"⚠️  Bet {bet['id']}: Missing token_id - skipping")
        continue
    
    shares = bet['size'] / bet['price'] if bet['price'] > 0 else 0
    position_value = shares * 1.0
    
    print(f"Bet {bet['id']}: {bet['market_question'][:60]}")
    print(f"  Token ID: {bet['token_id']}")
    print(f"  Shares: {shares:.2f}")
    print(f"  Position Value: ${position_value:.2f}")
    
    # Check market status
    market_closed = False
    if bet['condition_id']:
        try:
            r = httpx.get(f'https://clob.polymarket.com/markets/{bet["condition_id"]}', timeout=10)
            if r.status_code == 200:
                market = r.json()
                market_closed = market.get('closed', False)
                print(f"  Market closed: {market_closed}")
        except Exception as e:
            print(f"  ⚠️  Could not check market status: {e}")
    
    # Try to sell
    try:
        # Try selling at 0.99 (should fill at market price ~$1.00 for resolved markets)
        # Use FOK (Fill-or-Kill) for immediate execution
        order = client.create_order(OrderArgs(
            token_id=bet['token_id'],
            price=0.99,
            size=round(shares, 2),
            side=SELL
        ))
        
        print(f"  📤 Attempting to sell {round(shares, 2)} shares at $0.99...")
        response = client.post_order(order, OrderType.FOK)
        
        if isinstance(response, dict):
            order_id = response.get('orderID') or response.get('id')
            if order_id:
                print(f"  ✅ Sell order placed: {order_id}")
                successful_sells.append({
                    'bet_id': bet['id'],
                    'order_id': order_id,
                    'shares': shares,
                    'value': position_value
                })
            else:
                print(f"  ⚠️  Response: {response}")
                failed_sells.append({
                    'bet_id': bet['id'],
                    'reason': f'No order ID in response: {response}',
                    'shares': shares,
                    'value': position_value
                })
        else:
            print(f"  ✅ Response: {response}")
            successful_sells.append({
                'bet_id': bet['id'],
                'order_id': str(response),
                'shares': shares,
                'value': position_value
            })
            
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ Error: {error_msg}")
        failed_sells.append({
            'bet_id': bet['id'],
            'reason': error_msg,
            'shares': shares,
            'value': position_value,
            'market_closed': market_closed
        })
    
    print()

print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total positions: {len(won_bets)}")
print(f"Successfully sold: {len(successful_sells)} (${sum(s['value'] for s in successful_sells):.2f})")
print(f"Failed: {len(failed_sells)} (${sum(f['value'] for f in failed_sells):.2f})")
print()

if successful_sells:
    print("SUCCESSFUL SELLS:")
    for s in successful_sells:
        print(f"  ✅ Bet {s['bet_id']}: {s['shares']:.2f} shares (${s['value']:.2f}) - Order: {s['order_id']}")
    print()

if failed_sells:
    print("FAILED SELLS:")
    for f in failed_sells:
        print(f"  ❌ Bet {f['bet_id']}: {f['shares']:.2f} shares (${f['value']:.2f})")
        print(f"     Reason: {f['reason']}")
        if f.get('market_closed'):
            print(f"     Note: Market is closed - may need redemption instead")
    print()

# Check balance after
print("=" * 100)
print("BALANCE CHECK")
print("=" * 100)
try:
    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
    balance = client.get_balance_allowance(params)
    cash_balance = float(balance.get('balance', 0)) / 1e6
    print(f"Current cash balance: ${cash_balance:.2f} USDC.e")
except Exception as e:
    print(f"Error checking balance: {e}")

conn.close()

print("\n" + "=" * 100)
print("NEXT STEPS")
print("=" * 100)
print("""
1. Check Polymarket.com to see if positions were sold
2. For failed sells on closed markets, check if:
   - Positions auto-settle after a delay
   - There's a manual "Claim" button on Polymarket UI
   - We need to call CTF contract directly
3. Update bet_manager.py to automatically sell after marking as won
""")
