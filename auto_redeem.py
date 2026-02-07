#!/usr/bin/env python3
"""
Automated redemption script for Vig bot
Runs periodically to redeem winning positions and keep funds available for trading.

Usage:
  python3.11 auto_redeem.py          # Run once
  python3.11 auto_redeem.py --loop   # Run continuously (every 2 hours)
"""
import os
import sys
import time
import signal
from pathlib import Path
from datetime import datetime, timezone
from web3 import Web3
from dotenv import load_dotenv

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from db import Database

# Config
ALCHEMY_RPC = "https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"
PRIVATE_KEY = os.getenv("POLYGON_PRIVATE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = os.getenv("DB_PATH", "vig.db")

# Redemption interval (default: 2 hours = 7200 seconds)
REDEMPTION_INTERVAL_SECONDS = int(os.getenv("REDEMPTION_INTERVAL_SECONDS", "7200"))

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

running = True


def signal_handler(sig, frame):
    global running
    print("\n🛑 Shutdown signal received. Finishing current redemption...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def get_won_bets_with_condition_ids(db):
    """Get all won bets that need redemption"""
    c = db.conn.cursor()
    
    # PostgreSQL uses boolean, SQLite uses integer for paper column
    if db.use_postgres:
        query = """
            SELECT id, market_question, condition_id, token_id, size, profit, placed_at
            FROM bets 
            WHERE paper=false AND result='won' AND condition_id IS NOT NULL AND condition_id != ''
            ORDER BY placed_at
        """
    else:
        query = """
            SELECT id, market_question, condition_id, token_id, size, profit, placed_at
            FROM bets 
            WHERE paper=0 AND result='won' AND condition_id IS NOT NULL AND condition_id != ''
            ORDER BY placed_at
        """
    
    c.execute(query)
    rows = c.fetchall()
    
    # Convert to dict format (works for both SQLite Row and PostgreSQL RealDictCursor)
    if rows and isinstance(rows[0], dict):
        return rows
    else:
        return [dict(row) for row in rows]


def redeem_position(w3, ctf, wallet, condition_id):
    """Redeem a single position"""
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
        nonce = w3.eth.get_transaction_count(wallet, 'pending')
        gas_price = int(w3.eth.gas_price * 1.2)
        
        tx = ctf.functions.redeemPositions(
            Web3.to_checksum_address(USDC_E),
            bytes.fromhex(HASH_ZERO[2:]),
            condition_bytes,
            [1, 2]  # indexSets for binary markets
        ).build_transaction({
            'chainId': 137,
            'from': wallet,
            'nonce': nonce,
            'gasPrice': gas_price,
        })
        
        # Estimate gas
        try:
            gas_estimate = w3.eth.estimate_gas(tx)
            tx['gas'] = int(gas_estimate * 1.2)
        except Exception as e:
            print(f"  ⚠️  Gas estimation failed: {e}, using default")
            tx['gas'] = 200_000
        
        # Sign and send
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  📤 Tx: https://polygonscan.com/tx/{tx_hash.hex()}")
        
        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            print(f"  ✅ Redeemed (gas: {receipt['gasUsed']})")
            return True
        else:
            print(f"  ❌ Transaction reverted")
            return False
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def run_redemption():
    """Run one redemption cycle"""
    print("=" * 80)
    print(f"🔄 AUTO-REDEMPTION CYCLE - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    
    # Setup
    w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
    if not w3.is_connected():
        print("❌ Cannot connect to Polygon")
        return False
    
    wallet = w3.eth.account.from_key(PRIVATE_KEY).address
    ctf = w3.eth.contract(address=Web3.to_checksum_address(CTF_ADDRESS), abi=CTF_ABI)
    
    # Check POL balance
    balance_pol = w3.eth.get_balance(wallet)
    if balance_pol < w3.to_wei(0.01, 'ether'):
        print(f"⚠️  Low POL balance: {w3.from_wei(balance_pol, 'ether'):.4f} POL")
        print("   Need ~0.01 POL for redemption transactions")
        return False
    
    # Get database connection
    db = Database(DB_PATH, database_url=DATABASE_URL)
    
    # Get won bets
    won_bets = get_won_bets_with_condition_ids(db)
    
    if not won_bets:
        print("✅ No won bets to redeem")
        db.close()
        return True
    
    print(f"📊 Found {len(won_bets)} won bet(s) needing redemption")
    
    # Group by condition_id (one redemption per condition)
    condition_ids = {}
    for bet in won_bets:
        cid = bet['condition_id']
        if cid not in condition_ids:
            condition_ids[cid] = []
        condition_ids[cid].append(bet)
    
    total_value = sum(b['size'] for b in won_bets)
    print(f"💰 Total value: ${total_value:.2f}")
    print(f"📋 Unique conditions: {len(condition_ids)}")
    print()
    
    # Redeem each condition
    successful = 0
    failed = 0
    
    for i, (cid, bets_list) in enumerate(condition_ids.items(), 1):
        print(f"[{i}/{len(condition_ids)}] Condition: {cid[:20]}...")
        print(f"   Covers {len(bets_list)} bet(s), ${sum(b['size'] for b in bets_list):.2f}")
        
        if redeem_position(w3, ctf, wallet, cid):
            successful += 1
        else:
            failed += 1
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Redeemed: {successful}/{len(condition_ids)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(condition_ids)}")
    print()
    
    db.close()
    return successful > 0


def main():
    global running
    
    if not PRIVATE_KEY:
        print("❌ POLYGON_PRIVATE_KEY not found in .env")
        sys.exit(1)
    
    # Check if running in loop mode
    loop_mode = "--loop" in sys.argv or os.getenv("REDEMPTION_LOOP", "false").lower() == "true"
    
    if loop_mode:
        print("🔄 Starting auto-redemption service (loop mode)")
        print(f"   Interval: {REDEMPTION_INTERVAL_SECONDS} seconds ({REDEMPTION_INTERVAL_SECONDS/3600:.1f} hours)")
        print("   Press Ctrl+C to stop")
        print()
        
        while running:
            try:
                run_redemption()
            except Exception as e:
                print(f"❌ Error in redemption cycle: {e}")
                import traceback
                traceback.print_exc()
            
            if running:
                print(f"⏳ Sleeping {REDEMPTION_INTERVAL_SECONDS}s until next redemption...")
                print()
                
                # Sleep in chunks to allow graceful shutdown
                remaining = REDEMPTION_INTERVAL_SECONDS
                while remaining > 0 and running:
                    sleep_chunk = min(remaining, 60)
                    time.sleep(sleep_chunk)
                    remaining -= sleep_chunk
        
        print("🛑 Auto-redemption service stopped")
    else:
        # Run once
        try:
            success = run_redemption()
            sys.exit(0 if success else 1)
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
