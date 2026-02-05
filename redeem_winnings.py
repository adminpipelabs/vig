#!/usr/bin/env python3
"""
Redeem winning positions from resolved Polymarket markets
Works for EOA wallets (signature_type=0)

IMPORTANT: Check Polymarket.com first to see if manual redemption is available.
If you see "Redeem" buttons, use those instead - they're safer.
"""
import os
import sqlite3
from web3 import Web3
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Config
ALCHEMY_RPC = "https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"
PRIVATE_KEY = os.getenv("POLYGON_PRIVATE_KEY")
DB_PATH = "vig.db"

if not PRIVATE_KEY:
    print("❌ POLYGON_PRIVATE_KEY not found in .env")
    exit(1)

# Contracts
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
HASH_ZERO = "0x0000000000000000000000000000000000000000000000000000000000000000"

# CTF ABI for redeemPositions
CTF_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def get_won_bets_with_condition_ids():
    """Get all won bets that need redemption"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    bets = conn.execute("""
        SELECT id, market_question, condition_id, token_id, size, profit
        FROM bets 
        WHERE paper=0 AND result='won' AND condition_id IS NOT NULL AND condition_id != ''
        ORDER BY placed_at
    """).fetchall()
    
    conn.close()
    return [dict(b) for b in bets]

def redeem_position(w3, ctf, wallet, condition_id):
    """Redeem a single position"""
    print(f"  Redeeming condition: {condition_id[:20]}...")
    
    try:
        # Convert condition_id to bytes32
        if condition_id.startswith('0x'):
            condition_bytes = bytes.fromhex(condition_id[2:])
        else:
            condition_bytes = bytes.fromhex(condition_id)
        
        # Ensure it's exactly 32 bytes
        if len(condition_bytes) != 32:
            print(f"  ❌ Invalid condition_id length: {len(condition_bytes)} bytes (need 32)")
            return False
        
        # Build transaction
        # Get fresh nonce and increase gas price to avoid replacement issues
        nonce = w3.eth.get_transaction_count(wallet, 'pending')  # Include pending transactions
        gas_price = int(w3.eth.gas_price * 1.2)  # Increase by 20% to avoid replacement issues
        
        tx = ctf.functions.redeemPositions(
            Web3.to_checksum_address(USDC_E),  # collateralToken
            bytes.fromhex(HASH_ZERO[2:]),       # parentCollectionId (always 0x00...00)
            condition_bytes,                    # conditionId
            [1, 2]                              # indexSets for binary markets (YES=1, NO=2)
        ).build_transaction({
            'chainId': 137,
            'from': wallet,
            'nonce': nonce,
            'gasPrice': gas_price,
        })
        
        # Estimate gas
        try:
            gas_estimate = w3.eth.estimate_gas(tx)
            tx['gas'] = int(gas_estimate * 1.2)  # Add 20% buffer
        except Exception as e:
            print(f"  ⚠️  Gas estimation failed: {e}, using default")
            tx['gas'] = 200_000
        
        # Sign and send
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  📤 Tx sent: https://polygonscan.com/tx/{tx_hash.hex()}")
        
        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            print(f"  ✅ Redeemed successfully (gas: {receipt['gasUsed']})")
            return True
        else:
            print(f"  ❌ Transaction reverted")
            return False
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Setup
    w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
    
    if not w3.is_connected():
        print("❌ Cannot connect to Polygon via Alchemy")
        exit(1)
    
    wallet = w3.eth.account.from_key(PRIVATE_KEY).address
    ctf = w3.eth.contract(address=Web3.to_checksum_address(CTF_ADDRESS), abi=CTF_ABI)
    
    print("=" * 80)
    print("REDEEM WINNING POSITIONS")
    print("=" * 80)
    print(f"🔑 Wallet: {wallet}")
    
    balance_pol = w3.eth.get_balance(wallet)
    print(f"⛽ POL balance: {w3.from_wei(balance_pol, 'ether'):.4f} POL")
    
    if balance_pol < w3.to_wei(0.01, 'ether'):
        print("⚠️  Low POL balance — you need ~0.01 POL per redemption")
        print("   Continue anyway? (y/n): ", end='')
        # For automation, continue anyway
        print("y (auto)")
    
    print()
    
    # Get won bets
    won_bets = get_won_bets_with_condition_ids()
    print(f"📊 Found {len(won_bets)} won bets with condition_id")
    print()
    
    if not won_bets:
        print("No won bets to redeem")
        return
    
    # Show summary
    total_payout = sum(b['size'] for b in won_bets)
    print(f"Total value to redeem: ${total_payout:.2f}")
    print()
    
    # Get unique condition_ids (one redemption per condition covers all positions)
    condition_ids = {}
    for bet in won_bets:
        cid = bet['condition_id']
        if cid not in condition_ids:
            condition_ids[cid] = []
        condition_ids[cid].append(bet)
    
    print(f"📋 Unique conditions to redeem: {len(condition_ids)}")
    print("   (One redemption per condition covers all positions in that market)")
    print()
    
    # Confirm
    print("⚠️  WARNING: This will redeem ALL winning positions for these conditions.")
    print("   Make sure you want to proceed.")
    print()
    
    # Redeem each unique condition
    successful = 0
    failed = 0
    
    for i, (cid, bets_list) in enumerate(condition_ids.items(), 1):
        print(f"[{i}/{len(condition_ids)}] Condition: {cid[:20]}...")
        print(f"   Covers {len(bets_list)} winning bet(s)")
        for bet in bets_list:
            print(f"     - Bet #{bet['id']}: {bet['market_question'][:50]}... (${bet['size']:.2f})")
        
        if redeem_position(w3, ctf, wallet, cid):
            successful += 1
        else:
            failed += 1
        
        print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully redeemed: {successful}/{len(condition_ids)}")
    print(f"❌ Failed: {failed}/{len(condition_ids)}")
    print()
    print("After redemption, check your CLOB balance:")
    print("  python3.11 -c \"from py_clob_client.client import ClobClient; from py_clob_client.clob_types import BalanceAllowanceParams, AssetType; import os; from dotenv import load_dotenv; load_dotenv(); client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137); client.set_api_creds(client.create_or_derive_api_creds()); params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0); bal = client.get_balance_allowance(params); print(f'Balance: ${float(bal.get(\"balance\", 0)) / 1e6:.2f}')\"")

if __name__ == "__main__":
    main()
