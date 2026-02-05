#!/usr/bin/env python3
"""
Check CLOB internal balance and positions
Polymarket uses internal accounting, not direct ERC1155 custody
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

print("=" * 100)
print("CLOB INTERNAL BALANCE CHECK")
print("=" * 100)

client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
client.set_api_creds(client.create_or_derive_api_creds())

# Check balance
print("\n1. CLOB BALANCE (Collateral)")
print("-" * 100)
try:
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
    balance = client.get_balance_allowance(params)
    print(f"Balance: {balance}")
    cash_balance = float(balance.get('balance', 0)) / 1e6
    print(f"Available Cash: ${cash_balance:.2f} USDC.e")
except Exception as e:
    print(f"Error: {e}")

# Check all available methods
print("\n2. AVAILABLE METHODS")
print("-" * 100)
methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
position_methods = [m for m in methods if any(word in m.lower() for word in ['position', 'portfolio', 'balance', 'trade', 'order'])]
print("Methods related to positions/portfolio/trades:")
for m in sorted(position_methods):
    print(f"  - {m}")

# Try to get positions/portfolio
print("\n3. ATTEMPTING TO GET POSITIONS/PORTFOLIO")
print("-" * 100)
for method_name in ['get_positions', 'get_portfolio', 'get_balances', 'get_user_positions']:
    if hasattr(client, method_name):
        try:
            print(f"\nTrying {method_name}():")
            result = getattr(client, method_name)()
            print(f"  Result: {result}")
        except Exception as e:
            print(f"  Error: {e}")

# Check recent trades
print("\n4. RECENT TRADES")
print("-" * 100)
try:
    trades = client.get_trades()
    if isinstance(trades, list):
        print(f"Found {len(trades)} trades")
        print("\nFirst 5 trades:")
        for i, t in enumerate(trades[:5], 1):
            print(f"  {i}. {t}")
    else:
        print(f"Trades response: {trades}")
except Exception as e:
    print(f"Error getting trades: {e}")

# Check open orders
print("\n5. OPEN ORDERS")
print("-" * 100)
try:
    from py_clob_client.clob_types import OpenOrderParams
    orders = client.get_orders(OpenOrderParams())
    if isinstance(orders, list):
        print(f"Found {len(orders)} open orders")
        if orders:
            print("\nFirst 3 orders:")
            for i, o in enumerate(orders[:3], 1):
                print(f"  {i}. {o}")
    else:
        print(f"Orders response: {orders}")
except Exception as e:
    print(f"Error getting orders: {e}")

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print("""
Polymarket CLOB uses INTERNAL ACCOUNTING:
- Positions tracked internally (not ERC1155 in wallet)
- Balance shown via get_balance_allowance() = available cash
- Position value shown on Polymarket.com = total equity

The $97.10 on Polymarket.com includes:
- Available cash: $0.24 (what CLOB API shows)
- Position value: $96.86 (internal tracking)

To access the $96.86:
1. Positions need to settle/close
2. Then withdraw from Polymarket internal balance
3. This triggers on-chain transfer to wallet
""")
