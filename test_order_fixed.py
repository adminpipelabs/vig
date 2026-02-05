"""
Test a $1 order to confirm everything works
Uses correct EOA client initialization
"""
import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from scanner import Scanner
from config import Config

load_dotenv()

# EOA initialization — note: no funder, no signature_type for direct EOA
client = ClobClient(
    "https://clob.polymarket.com",
    key=os.getenv("POLYGON_PRIVATE_KEY"),
    chain_id=137,
)

client.set_api_creds(client.create_or_derive_api_creds())

# Check balance
print("Checking balance...")
try:
    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
    balance_info = client.get_balance_allowance(params)
    balance = float(balance_info.get('balance', 0)) / 1e6
    print(f"✅ CLOB Balance: ${balance:.2f} USDC.e")
except Exception as e:
    print(f"Balance check: {e}")
print()

# Get a token_id from scanner
print("Finding a market...")
config = Config()
scanner = Scanner(config)
candidates = scanner.scan()

if not candidates:
    print("❌ No markets found")
    exit(1)

m = candidates[0]
TOKEN_ID = m.fav_token_id
fav_price = m.fav_price

print(f"Market: {m.question[:70]}")
print(f"Token ID: {TOKEN_ID}")
print(f"Price: ${fav_price:.2f}")
print(f"Side: {m.fav_side}")
print()

# Test order
print(f"Placing test order: $1 at ${fav_price:.2f}")
print(f"Size: {1.0 / fav_price:.4f} shares")
print()

try:
    order_args = OrderArgs(
        price=fav_price,
        size=1.0 / fav_price,  # $1 worth
        side=BUY,
        token_id=TOKEN_ID,
    )

    signed_order = client.create_order(order_args)
    resp = client.post_order(signed_order, OrderType.GTC)
    print("✅ Order successful!")
    print("Order response:", resp)
except Exception as e:
    print("❌ Order failed:")
    import traceback
    traceback.print_exc()
