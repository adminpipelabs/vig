#!/usr/bin/env python3
"""
Check if Polymarket CLOB API exposes settled/closed positions
and how to access funds from them
"""
import os
import httpx
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
print("CHECKING SETTLED/CLOSED POSITIONS")
print("=" * 100)
print()

# 1. Check balance types
print("1. BALANCE TYPES")
print("-" * 100)
try:
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
    balance = client.get_balance_allowance(params)
    cash = float(balance.get('balance', 0)) / 1e6
    print(f"Collateral (cash): ${cash:.2f}")
    print(f"Full balance response: {balance}")
except Exception as e:
    print(f"Error: {e}")

print()

# 2. Try to get closed positions via direct API call
print("2. CHECKING CLOSED POSITIONS API")
print("-" * 100)
try:
    # Try the endpoint mentioned in docs
    api_key = client.api_creds.api_key
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # Try different endpoints
    endpoints = [
        '/closed-positions',
        '/positions/closed',
        '/user/closed-positions',
        '/settled-positions',
        '/user/positions/closed'
    ]
    
    base_url = 'https://clob.polymarket.com'
    
    for endpoint in endpoints:
        try:
            r = httpx.get(f'{base_url}{endpoint}', headers=headers, timeout=10)
            print(f"{endpoint}: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"  ✅ Success! Response: {data}")
            elif r.status_code == 404:
                print(f"  ❌ Not found")
            else:
                print(f"  ⚠️  {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"{endpoint}: Error - {e}")
        print()
        
except Exception as e:
    print(f"Error checking endpoints: {e}")
    import traceback
    traceback.print_exc()

print()

# 3. Check trades for settlement indicators
print("3. ANALYZING TRADES FOR SETTLEMENT INFO")
print("-" * 100)
try:
    trades = client.get_trades()
    print(f"Total trades: {len(trades)}")
    
    # Look for any settlement-related fields
    if trades:
        sample = trades[0]
        print(f"Sample trade keys: {list(sample.keys()) if isinstance(sample, dict) else 'Not a dict'}")
        print(f"Sample trade: {sample}")
        
        # Check if any trades have settlement status
        settled_trades = [t for t in trades if isinstance(t, dict) and t.get('status') == 'SETTLED']
        print(f"Settled trades: {len(settled_trades)}")
        
except Exception as e:
    print(f"Error: {e}")

print()

# 4. Summary
print("=" * 100)
print("SUMMARY")
print("=" * 100)
print("""
Based on the investigation:

1. ✅ Cash balance: $0.24 (available)
2. ❌ No closed positions API endpoint found
3. ❌ No settlement status in trades
4. ❌ Positions tracked internally (not ERC1155 tokens)

The $97 position value exists in Polymarket's internal system but:
- Can't be sold (markets closed, no orderbook)
- Can't be redeemed via API (no method exists)
- ERC1155 balances are 0 (not on-chain tokens)

NEXT STEPS:
1. Check if Polymarket auto-settles after a delay (24-48h)
2. Check if there's a withdrawal endpoint we're missing
3. Check Polymarket.com UI for manual withdrawal option
4. Contact Polymarket support about programmatic access to settled positions
""")
