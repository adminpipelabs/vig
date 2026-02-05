#!/usr/bin/env python3
"""
Diagnose Balance Discrepancy — Find missing $56.64
Run this to check for stuck orders, compare DB vs CLOB state, and get cash flow analysis.
"""
import os
import sys
import sqlite3
from dotenv import load_dotenv

load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType, OpenOrderParams

# Connect to database
db = sqlite3.connect('vig.db')
db.row_factory = sqlite3.Row

# Connect to CLOB
print("Connecting to CLOB...")
client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
client.set_api_creds(client.create_or_derive_api_creds())

print("✅ Connected\n")

# ─── 1. Check Current Balance ──────────────────────────────────────
print("=" * 80)
print("1. CURRENT CLOB BALANCE")
print("=" * 80)
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
balance_info = client.get_balance_allowance(params)
current_balance = float(balance_info.get('balance', 0)) / 1e6
print(f"Available Balance: ${current_balance:.2f} USDC.e\n")

# ─── 2. Check Open Orders ──────────────────────────────────────────
print("=" * 80)
print("2. OPEN ORDERS (Potentially Stuck)")
print("=" * 80)
try:
    open_orders = client.get_orders(OpenOrderParams())
    if isinstance(open_orders, list):
        print(f"Found {len(open_orders)} open orders:\n")
        total_locked = 0.0
        for i, order in enumerate(open_orders, 1):
            order_id = order.get('orderID') or order.get('id', 'unknown')
            status = order.get('status', 'unknown')
            size = float(order.get('size', 0))
            filled = float(order.get('filled', 0))
            price = float(order.get('price', 0))
            token_id = order.get('tokenID', 'unknown')
            locked = (size - filled) * price if price > 0 else 0
            
            print(f"  Order {i}:")
            print(f"    ID: {order_id[:30]}...")
            print(f"    Status: {status}")
            print(f"    Size: {size} (Filled: {filled})")
            print(f"    Price: ${price:.4f}")
            print(f"    Locked: ${locked:.2f}")
            print(f"    Token: {token_id[:30]}...")
            print()
            total_locked += locked
        
        if total_locked > 0:
            print(f"⚠️  TOTAL FUNDS LOCKED IN OPEN ORDERS: ${total_locked:.2f}\n")
        else:
            print("✅ No funds locked in open orders\n")
    else:
        print(f"Response: {open_orders}\n")
except Exception as e:
    print(f"⚠️  Could not fetch open orders: {e}\n")

# ─── 3. Database Summary ────────────────────────────────────────────
print("=" * 80)
print("3. DATABASE SUMMARY")
print("=" * 80)
stats = db.execute("""
    SELECT 
        result,
        COUNT(*) as count,
        SUM(amount) as total_amount,
        SUM(profit) as total_profit,
        SUM(payout) as total_payout
    FROM bets 
    GROUP BY result
""").fetchall()

for row in stats:
    print(f"{row['result']:8s}: {row['count']:2d} bets | Deployed: ${row['total_amount']:8.2f} | Profit: ${row['total_profit']:8.2f}")

all_stats = db.execute("SELECT SUM(amount) as deployed, SUM(profit) as profit FROM bets").fetchone()
pending = db.execute("SELECT SUM(amount) as pending_amount FROM bets WHERE result='pending'").fetchone()

print(f"\nTotal Deployed: ${all_stats['deployed']:.2f}")
print(f"Total Profit: ${all_stats['profit']:.2f}")
print(f"Pending Amount: ${pending['pending_amount']:.2f}")

# ─── 4. Expected vs Actual Balance ────────────────────────────────
print("\n" + "=" * 80)
print("4. EXPECTED vs ACTUAL BALANCE")
print("=" * 80)
starting_balance = 90.0
expected_available = starting_balance + all_stats['profit'] - pending['pending_amount']
print(f"Starting Balance: ${starting_balance:.2f}")
print(f"Total Profit: ${all_stats['profit']:.2f}")
print(f"Pending (locked): ${pending['pending_amount']:.2f}")
print(f"Expected Available: ${expected_available:.2f}")
print(f"Actual Available: ${current_balance:.2f}")
discrepancy = current_balance - expected_available
print(f"\n{'⚠️  DISCREPANCY:' if abs(discrepancy) > 1 else '✅ Balance OK:'} ${discrepancy:.2f}")

# ─── 5. Pending Bets Details ────────────────────────────────────────
print("\n" + "=" * 80)
print("5. PENDING BETS (Check Settlement Status)")
print("=" * 80)
pending_bets = db.execute("""
    SELECT id, order_id, amount, market_question, placed_at 
    FROM bets 
    WHERE result='pending' 
    ORDER BY placed_at DESC
""").fetchall()

if pending_bets:
    print(f"Found {len(pending_bets)} pending bets:\n")
    for bet in pending_bets:
        order_id = bet['order_id']
        print(f"  Bet {bet['id']}: ${bet['amount']:.2f}")
        print(f"    Market: {bet['market_question'][:60]}")
        print(f"    Order ID: {order_id[:40] if order_id else 'N/A'}...")
        print(f"    Placed: {bet['placed_at'][:19]}")
        
        # Try to check order status
        if order_id and order_id.startswith('0x'):
            try:
                order = client.get_order(order_id)
                if isinstance(order, dict):
                    status = order.get('status', 'unknown')
                    filled = order.get('filled', 0)
                    size = order.get('size', 0)
                    print(f"    Order Status: {status} (Filled: {filled}/{size})")
                else:
                    print(f"    Order Status: {order}")
            except Exception as e:
                print(f"    Order Status: Could not fetch ({e})")
        print()
else:
    print("✅ No pending bets\n")

# ─── 6. Recommendations ──────────────────────────────────────────────
print("=" * 80)
print("6. RECOMMENDATIONS")
print("=" * 80)
print("""
1. Check Polymarket.com directly:
   - Go to polymarket.com and connect wallet (0x989B...5A1D)
   - Check Portfolio balance
   - Check Open Orders tab
   - Review Activity history for all fills/settlements

2. Compare against database:
   - Database shows all bets placed
   - Some orders may have failed to fill
   - Some orders may be stuck in "MATCHED" but not filled

3. If you find stuck orders:
   - Cancel them on Polymarket.com directly, OR
   - Run: python3.11 -c "
     from py_clob_client.client import ClobClient
     import os
     from dotenv import load_dotenv
     load_dotenv()
     client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
     client.set_api_creds(client.create_or_derive_api_creds())
     client.cancel_all()
     print('All orders cancelled')
   "

4. The $56.64 discrepancy is likely:
   - $31.99 in pending bets (not yet resolved)
   - $24.65 in stuck/unfilled orders (need to cancel)
""")

db.close()
