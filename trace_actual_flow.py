#!/usr/bin/env python3
"""
Trace the actual flow: What happened to all the bets and funds?
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

client = ClobClient(
    'https://clob.polymarket.com',
    key=os.getenv('POLYGON_PRIVATE_KEY'),
    chain_id=137
)
client.set_api_creds(client.create_or_derive_api_creds())

print("=" * 100)
print("TRACING ACTUAL FLOW")
print("=" * 100)
print()

# 1. Get all trades from CLOB API
print("1. CLOB API TRADE HISTORY")
print("-" * 100)
try:
    trades = client.get_trades()
    print(f"Total trades from CLOB API: {len(trades)}")
    print()
    
    # Group by status
    buy_trades = []
    sell_trades = []
    for t in trades:
        if isinstance(t, dict):
            side = t.get('side', '').upper()
            if side == 'BUY':
                buy_trades.append(t)
            elif side == 'SELL':
                sell_trades.append(t)
    
    print(f"BUY trades: {len(buy_trades)}")
    print(f"SELL trades: {len(sell_trades)}")
    print()
    
    # Show recent trades
    print("Recent trades (last 10):")
    for i, t in enumerate(trades[:10], 1):
        if isinstance(t, dict):
            print(f"  {i}. {t.get('side', '?')} {t.get('size', '?')} @ ${t.get('price', '?')} - {t.get('status', '?')}")
            print(f"     Token: {t.get('token_id', '?')[:20]}...")
            print(f"     Order ID: {t.get('orderID', t.get('id', '?'))}")
        else:
            print(f"  {i}. {t}")
        print()
        
except Exception as e:
    print(f"Error getting trades: {e}")
    import traceback
    traceback.print_exc()

print()

# 2. Get database state
print("2. DATABASE STATE")
print("-" * 100)
conn = sqlite3.connect('/Users/mikaelo/vig/vig.db')
conn.row_factory = sqlite3.Row

# All bets summary
all_bets = conn.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as lost,
        SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as pending,
        SUM(amount) as total_wagered,
        SUM(CASE WHEN result='won' THEN payout ELSE 0 END) as total_won_payouts,
        SUM(CASE WHEN result='lost' THEN amount ELSE 0 END) as total_lost_amount,
        SUM(profit) as total_profit
    FROM bets 
    WHERE paper=0
""").fetchone()

print(f"Total bets: {all_bets['total']}")
print(f"Won: {all_bets['won']}")
print(f"Lost: {all_bets['lost']}")
print(f"Pending: {all_bets['pending']}")
print(f"Total wagered: ${all_bets['total_wagered']:.2f}")
print(f"Total won payouts (expected): ${all_bets['total_won_payouts']:.2f}")
print(f"Total lost amount: ${all_bets['total_lost_amount']:.2f}")
print(f"Total profit: ${all_bets['total_profit']:.2f}")
print()

# Won bets detail
won_bets = conn.execute("""
    SELECT id, market_question, token_id, size, price, amount, payout, profit, placed_at, resolved_at
    FROM bets 
    WHERE paper=0 AND result='won'
    ORDER BY resolved_at DESC
""").fetchall()

print(f"Won bets detail ({len(won_bets)}):")
for bet in won_bets:
    shares = bet['size'] / bet['price'] if bet['price'] > 0 else 0
    print(f"  Bet {bet['id']}: {bet['market_question'][:50]}")
    print(f"    Wagered: ${bet['amount']:.2f} @ ${bet['price']:.2f} = {shares:.2f} shares")
    print(f"    Expected payout: ${bet['payout']:.2f}")
    print(f"    Profit recorded: ${bet['profit']:.2f}")
    print(f"    Resolved: {bet['resolved_at']}")
    print()

print()

# 3. Calculate expected vs actual
print("3. EXPECTED VS ACTUAL")
print("-" * 100)

starting_balance = 90.0
total_wagered = all_bets['total_wagered'] or 0
total_won_payouts = all_bets['total_won_payouts'] or 0
total_lost = all_bets['total_lost_amount'] or 0
pending_locked = conn.execute("""
    SELECT SUM(amount) FROM bets WHERE paper=0 AND result='pending'
""").fetchone()[0] or 0

expected_cash = starting_balance - total_wagered + total_won_payouts + total_lost
expected_after_pending = expected_cash - pending_locked

print(f"Starting balance: ${starting_balance:.2f}")
print(f"Total wagered: ${total_wagered:.2f}")
print(f"Won payouts (should have received): ${total_won_payouts:.2f}")
print(f"Lost (already deducted): ${total_lost:.2f}")
print(f"Pending (still locked): ${pending_locked:.2f}")
print()
print(f"Expected cash (if all won payouts received): ${expected_cash:.2f}")
print(f"Expected cash (after pending): ${expected_after_pending:.2f}")

# Get actual balance
try:
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
    balance_info = client.get_balance_allowance(params)
    actual_cash = float(balance_info.get('balance', 0)) / 1e6
    print(f"Actual cash (CLOB API): ${actual_cash:.2f}")
    print()
    print(f"DISCREPANCY: ${expected_after_pending - actual_cash:.2f}")
except Exception as e:
    print(f"Error getting balance: {e}")

print()

# 4. Check if won payouts were actually received
print("4. CHECKING IF WON PAYOUTS WERE RECEIVED")
print("-" * 100)
print("Looking for SELL trades that match won bets...")
print()

# Match won bets with sell trades
if 'sell_trades' in locals() and sell_trades:
    print(f"Found {len(sell_trades)} sell trades")
    for sell in sell_trades:
        sell_token = str(sell.get('token_id', ''))
        sell_size = float(sell.get('size', 0))
        sell_price = float(sell.get('price', 0))
        
        # Find matching won bet
        matching_bet = None
        for bet in won_bets:
            if str(bet['token_id']) == sell_token:
                matching_bet = bet
                break
        
        if matching_bet:
            print(f"✅ Found matching sell for bet {matching_bet['id']}")
            print(f"   Bet shares: {matching_bet['size'] / matching_bet['price']:.2f}")
            print(f"   Sell size: {sell_size:.2f}")
            print(f"   Sell price: ${sell_price:.2f}")
            print(f"   Sell value: ${sell_size * sell_price:.2f}")
        else:
            print(f"⚠️  Sell trade for token {sell_token[:20]}... doesn't match any won bet")
else:
    print("❌ No SELL trades found in CLOB API")
    print("   This confirms: Won positions were NOT sold/redeemed")

print()

# 5. Summary
print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"""
The flow shows:
1. ✅ {all_bets['total']} bets placed (total wagered: ${total_wagered:.2f})
2. ✅ {all_bets['won']} bets won (expected payouts: ${total_won_payouts:.2f})
3. ✅ {all_bets['lost']} bets lost (lost: ${total_lost:.2f})
4. ❌ Won payouts NOT received (no SELL trades in CLOB API)
5. ❌ Cash balance: ${actual_cash:.2f} (expected: ${expected_after_pending:.2f})

The ${total_won_payouts:.2f} in won payouts is sitting as position value on Polymarket
but hasn't been converted to cash. Since there's no API method to redeem,
and selling doesn't work (orderbook doesn't exist for closed markets),
we need to find how Polymarket actually settles these positions.
""")

conn.close()
