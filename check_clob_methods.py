#!/usr/bin/env python3
"""
Check all available methods in ClobClient to find claim/redeem functionality
"""
import os
import inspect
from pathlib import Path
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

print("=" * 100)
print("CLOB CLIENT METHOD EXPLORATION")
print("=" * 100)
print()

# List all methods
methods = [m for m in dir(ClobClient) if not m.startswith('_')]
print(f"Total methods: {len(methods)}\n")
print("All available methods:")
for m in sorted(methods):
    print(f"  - {m}")

print("\n" + "=" * 100)
print("METHODS RELATED TO REDEMPTION/CLAIMING")
print("=" * 100)
print()

# Look for redemption-related methods
redemption_keywords = ['redeem', 'claim', 'settle', 'withdraw', 'close', 'position', 'balance']
relevant_methods = []
for m in methods:
    if any(keyword in m.lower() for keyword in redemption_keywords):
        relevant_methods.append(m)
        print(f"✅ Found: {m}")
        # Try to get signature
        try:
            method = getattr(ClobClient, m)
            sig = inspect.signature(method)
            print(f"   Signature: {sig}")
        except:
            pass

if not relevant_methods:
    print("❌ No obvious redemption/claim methods found")

print("\n" + "=" * 100)
print("TESTING CLIENT INSTANCE")
print("=" * 100)
print()

# Create client instance and test
client = ClobClient(
    'https://clob.polymarket.com',
    key=os.getenv('POLYGON_PRIVATE_KEY'),
    chain_id=137
)
client.set_api_creds(client.create_or_derive_api_creds())

# Test methods that might exist
test_methods = [
    'redeem',
    'redeem_positions', 
    'claim',
    'claim_winnings',
    'settle',
    'settle_positions',
    'close_position',
    'withdraw',
    'get_claimable',
    'get_redeemable',
    'get_positions',
    'get_portfolio',
    'get_balances'
]

print("Testing for existence of potential methods:")
for method_name in test_methods:
    if hasattr(client, method_name):
        print(f"✅ Found: client.{method_name}")
        try:
            method = getattr(client, method_name)
            sig = inspect.signature(method)
            print(f"   Signature: {sig}")
        except:
            pass
    else:
        print(f"❌ Not found: {method_name}")

print("\n" + "=" * 100)
print("BALANCE CHECK")
print("=" * 100)
print()

try:
    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
    balance = client.get_balance_allowance(params)
    print(f"Collateral balance: {balance}")
except Exception as e:
    print(f"Error checking balance: {e}")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print("""
Next steps:
1. Check Polymarket UI for Claim/Redeem buttons on winning positions
2. If no API method exists, may need to:
   - Sell positions back to market (if still tradeable)
   - Wait for auto-settlement (if Polymarket does this)
   - Call CTF contract directly (if positions are on-chain)
""")
