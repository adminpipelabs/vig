"""
Vig v1 — USDC.e Deposit Script
Deposits USDC.e into Polymarket's CLOB exchange contract so the bot can place orders.

Usage: python3.11 deposit_to_clob.py
"""

import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType

load_dotenv()

# --- Configuration ---
PRIVATE_KEY = os.getenv("POLYGON_PRIVATE_KEY")
FUNDER_ADDRESS = os.getenv("POLYGON_FUNDER_ADDRESS")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", "0"))
CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

# Amount to deposit (in USDC.e)
DEPOSIT_AMOUNT = 93.0  # Adjust this to whatever is in your wallet


def main():
    if not PRIVATE_KEY:
        print("❌ POLYGON_PRIVATE_KEY not found in .env")
        return

    if not FUNDER_ADDRESS:
        print("❌ POLYGON_FUNDER_ADDRESS not found in .env")
        return

    deposit_amount = DEPOSIT_AMOUNT
    
    print(f"🔗 Connecting to Polymarket CLOB...")
    print(f"🔑 Wallet: {FUNDER_ADDRESS}")
    print(f"💰 Deposit amount: ${deposit_amount} USDC.e")
    print()

    # --- Step 1: Initialize CLOB client ---
    client = ClobClient(
        host=CLOB_HOST,
        key=PRIVATE_KEY,
        chain_id=CHAIN_ID,
        signature_type=SIGNATURE_TYPE,
        funder=FUNDER_ADDRESS,
    )

    # --- Step 2: Set API credentials (needed for authenticated calls) ---
    print("🔐 Deriving API credentials...")
    try:
        client.set_api_creds(client.create_or_derive_api_creds())
        print("   ✅ API credentials set")
    except Exception as e:
        print(f"   ⚠️  API creds error: {e}")
        print("   Trying to continue...")
    print()

    # --- Step 3: Check current CLOB balance ---
    print("📊 Checking current CLOB exchange balance...")
    try:
        params = BalanceAllowanceParams(
            asset_type=AssetType.COLLATERAL,
            signature_type=SIGNATURE_TYPE
        )
        balance_info = client.get_balance_allowance(params)
        current_balance = float(balance_info.get('balance', 0)) / 1e6  # USDC.e has 6 decimals
        print(f"   Current balance: ${current_balance:.2f} USDC.e")
    except Exception as e:
        print(f"   ⚠️  Could not check balance: {e}")
        print("   Continuing with deposit anyway...")
    print()

    # --- Step 4: Check wallet USDC.e balance first ---
    print("💼 Checking wallet USDC.e balance...")
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider("https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"))
        USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        erc20_abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}]
        usdc_e = w3.eth.contract(address=USDC_E, abi=erc20_abi)
        wallet_balance = usdc_e.functions.balanceOf(FUNDER_ADDRESS).call() / 1e6
        print(f"   Wallet USDC.e balance: ${wallet_balance:.2f}")
        
        if wallet_balance < deposit_amount:
            print(f"   ⚠️  Warning: Wallet has ${wallet_balance:.2f}, trying to deposit ${deposit_amount}")
            deposit_amount = wallet_balance
            print(f"   Adjusting deposit amount to ${deposit_amount:.2f}")
    except Exception as e:
        print(f"   ⚠️  Could not check wallet balance: {e}")
    print()

    # --- Step 5: Deposit USDC.e to CLOB exchange ---
    print(f"📤 Depositing ${deposit_amount} USDC.e to CLOB exchange...")
    try:
        # Check if deposit method exists
        if hasattr(client, 'deposit'):
            result = client.deposit(deposit_amount)
            print(f"   ✅ Deposit successful!")
            print(f"   Result: {result}")
        else:
            print("   ❌ CLOB client does not have a 'deposit' method")
            print("   Checking available methods...")
            methods = [m for m in dir(client) if 'deposit' in m.lower() or 'fund' in m.lower()]
            if methods:
                print(f"   Found similar methods: {methods}")
            else:
                print("   💡 You may need to deposit via Polymarket UI or use a different method")
                print("   Check Polymarket CLOB documentation for deposit flow")
            return
    except Exception as e:
        print(f"   ❌ Deposit failed: {e}")
        print()
        print("   Possible reasons:")
        print("   1. USDC.e is not in the raw wallet (still in Polymarket UI proxy)")
        print("      → Withdraw from Polymarket UI first, then re-run this script")
        print("   2. Insufficient USDC.e balance")
        print("      → Check wallet on polygonscan for USDC.e token balance")
        print("   3. Approval not set for USDC.e")
        print("      → Run approve_tokens_correct.py to approve USDC.e")
        return
    print()

    # --- Step 6: Verify new balance ---
    print("📊 Verifying new CLOB exchange balance...")
    try:
        params = BalanceAllowanceParams(
            asset_type=AssetType.COLLATERAL,
            signature_type=SIGNATURE_TYPE
        )
        balance_info = client.get_balance_allowance(params)
        new_balance = float(balance_info.get('balance', 0)) / 1e6
        print(f"   New balance: ${new_balance:.2f} USDC.e")
        print()
        print(f"{'='*50}")
        print("🎉 Deposit complete! The bot can now place live orders.")
        print("Run: python3.11 main.py")
        print(f"{'='*50}")
    except Exception as e:
        print(f"   ⚠️  Could not verify balance: {e}")
        print("   Check polymarket.com to confirm deposit went through")


if __name__ == "__main__":
    main()
