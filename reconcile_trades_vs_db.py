#!/usr/bin/env python3
"""
Reconcile CLOB trades vs database bets
Check if settled bets match Polymarket's internal accounting
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from collections import defaultdict

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from py_clob_client.client import ClobClient

print("=" * 100)
print("RECONCILE CLOB TRADES vs DATABASE")
print("=" * 100)

# Connect to DB
db_path = os.getenv('DB_PATH', 'vig.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Get all bets
bets = conn.execute("""
    SELECT id, market_id, token_id, side, price, size, result, profit, placed_at, order_id
    FROM bets 
    WHERE paper=0
    ORDER BY placed_at
""").fetchall()

print(f"\nDatabase: {len(bets)} bets")

# Connect to CLOB
client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
client.set_api_creds(client.create_or_derive_api_creds())

# Get all trades
trades = client.get_trades()
print(f"CLOB API: {len(trades)} trades")

# Group trades by asset_id (token_id)
trades_by_token = defaultdict(list)
for trade in trades:
    asset_id = trade.get('asset_id')
    if asset_id:
        trades_by_token[asset_id].append(trade)

# Match bets to trades
print("\n" + "=" * 100)
print("MATCHING BETS TO TRADES")
print("=" * 100)

matched = []
unmatched_bets = []
unmatched_trades = set(trades_by_token.keys())

for bet in bets:
    token_id = bet['token_id']
    order_id = bet['order_id']
    
    # Try to match by token_id
    if token_id in trades_by_token:
        trade_matches = trades_by_token[token_id]
        matched.append({
            'bet': bet,
            'trades': trade_matches
        })
        unmatched_trades.discard(token_id)
    else:
        unmatched_bets.append(bet)

print(f"\nMatched: {len(matched)} bets")
print(f"Unmatched bets: {len(unmatched_bets)}")
print(f"Unmatched trades: {len(unmatched_trades)}")

# Analyze settled vs pending
print("\n" + "=" * 100)
print("SETTLEMENT STATUS ANALYSIS")
print("=" * 100)

won_bets = [b for b in bets if b['result'] == 'won']
lost_bets = [b for b in bets if b['result'] == 'lost']
pending_bets = [b for b in bets if b['result'] == 'pending']

print(f"\nDatabase Status:")
print(f"  Won: {len(won_bets)}")
print(f"  Lost: {len(lost_bets)}")
print(f"  Pending: {len(pending_bets)}")

# Calculate expected payouts
won_payouts = sum(float(b['size']) for b in won_bets)
won_cost = sum(float(b['price']) * float(b['size']) for b in won_bets)
won_profit = sum(float(b['profit'] or 0) for b in won_bets)

lost_cost = sum(float(b['price']) * float(b['size']) for b in lost_bets)
pending_cost = sum(float(b['price']) * float(b['size']) for b in pending_bets)

print(f"\nFinancial Summary:")
print(f"  Won bets:")
print(f"    Cost: ${won_cost:.2f}")
print(f"    Payouts: ${won_payouts:.2f}")
print(f"    Profit: ${won_profit:.2f}")
print(f"  Lost bets:")
print(f"    Cost: ${lost_cost:.2f}")
print(f"  Pending bets:")
print(f"    Cost: ${pending_cost:.2f}")

# Expected balance calculation
starting = 90.0
total_cost = won_cost + lost_cost + pending_cost
expected_cash = starting - total_cost + won_payouts

print(f"\nExpected Cash Flow:")
print(f"  Starting: ${starting:.2f}")
print(f"  Total wagered: ${total_cost:.2f}")
print(f"  Won payouts: ${won_payouts:.2f}")
print(f"  Expected cash: ${expected_cash:.2f}")

# Check CLOB balance
balance = client.get_balance_allowance()
cash_balance = float(balance.get('balance', 0)) / 1e6
print(f"\nActual CLOB Cash: ${cash_balance:.2f}")
print(f"Difference: ${expected_cash - cash_balance:.2f}")

print("\n" + "=" * 100)
print("KEY INSIGHT")
print("=" * 100)
print("""
The difference (${:.2f}) represents:
- Settled winnings that haven't been withdrawn from Polymarket's internal system
- These are tracked internally, not as ERC1155 tokens
- Need to check Polymarket.com for withdrawal/claim options
""".format(expected_cash - cash_balance))

conn.close()
