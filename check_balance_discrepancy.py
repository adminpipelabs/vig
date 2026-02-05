#!/usr/bin/env python3
"""
Check balance discrepancy - find where the missing $56.64 went
"""
import os
import sys
import sqlite3
from dotenv import load_dotenv

load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

# Connect to database
db = sqlite3.connect('vig.db')
db.row_factory = sqlite3.Row

# Connect to CLOB
client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
client.set_api_creds(client.create_or_derive_api_creds())

print("=== CURRENT CLOB BALANCE ===")
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
balance_info = client.get_balance_allowance(params)
current_balance = float(balance_info.get('balance', 0)) / 1e6
print(f"Available: ${current_balance:.2f} USDC.e")

print("\n=== BET SUMMARY ===")
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

print("\n=== EXPECTED vs ACTUAL ===")
starting_balance = 90.0
expected_available = starting_balance + all_stats['profit'] - pending['pending_amount']
print(f"Starting Balance: ${starting_balance:.2f}")
print(f"Total Profit: ${all_stats['profit']:.2f}")
print(f"Pending (locked): ${pending['pending_amount']:.2f}")
print(f"Expected Available: ${expected_available:.2f}")
print(f"Actual Available: ${current_balance:.2f}")
print(f"DISCREPANCY: ${current_balance - expected_available:.2f}")

print("\n=== CHECKING PENDING ORDERS ===")
pending_bets = db.execute("SELECT id, order_id, amount, market_question FROM bets WHERE result='pending'").fetchall()
print(f"Found {len(pending_bets)} pending bets with order IDs")

# Try to check order status
for bet in pending_bets:
    order_id = bet['order_id']
    if order_id and order_id.startswith('0x'):
        print(f"\nBet {bet['id']}: ${bet['amount']:.2f} - Order: {order_id[:20]}...")
        try:
            # Try to get order status
            order = client.get_order(order_id)
            if isinstance(order, dict):
                status = order.get('status', 'unknown')
                filled = order.get('filled', 0)
                size = order.get('size', 0)
                print(f"  Status: {status}, Filled: {filled}/{size}")
            else:
                print(f"  Order response: {order}")
        except Exception as e:
            print(f"  Could not fetch order: {e}")

print("\n=== RECOMMENDATION ===")
print("The discrepancy could be due to:")
print("1. Unfilled orders locking funds")
print("2. Orders that filled but weren't properly recorded")
print("3. Starting balance was different than $90")
print("4. Some bets were placed but orders failed after recording")
print("\nCheck Polymarket.com directly for your wallet's order history and balance.")
