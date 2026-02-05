#!/usr/bin/env python3
"""
Manually settle the 5 expired pending bets
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from bet_manager import BetManager
from config import Config
from db import Database
from snowball import Snowball

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

config = Config()
db = Database(config.db_path)
snowball = Snowball(config)

# CLOB client for live mode
clob_client = None
if not config.paper_mode:
    try:
        from py_clob_client.client import ClobClient
        clob_client = ClobClient(config.clob_url, key=config.private_key, chain_id=config.chain_id)
        creds = clob_client.create_or_derive_api_creds()
        clob_client.set_api_creds(creds)
    except Exception as e:
        print(f"Error initializing CLOB client: {e}")
        exit(1)

bet_mgr = BetManager(config, db, snowball, clob_client)

# Get expired pending bets
pending_bets = db.get_all_pending_bets()

print("=" * 100)
print(f"SETTLING {len(pending_bets)} PENDING BETS")
print("=" * 100)
print()

settled_count = 0
for bet in pending_bets:
    print(f"Checking bet {bet.id}: {bet.market_question[:60]}")
    
    try:
        if config.paper_mode:
            result, payout = bet_mgr._simulate_settlement(bet)
        else:
            result, payout = bet_mgr._check_live_settlement(bet)
        
        if result != "pending":
            profit = payout - bet.amount if result == "won" else -bet.amount
            db.update_bet_result(bet.id, result, payout, profit)
            
            emoji = "W" if result == "won" else "L"
            print(f"  ✅ [{emoji}] Settled: {result} | Payout: ${payout:.2f} | Profit: ${profit:.2f}")
            settled_count += 1
            
            # Try to sell if won
            if result == "won" and not config.paper_mode and clob_client:
                sell_success = bet_mgr._sell_winning_position(bet)
                if sell_success:
                    print(f"  ✅ Position sold")
                else:
                    print(f"  ⚠️  Could not sell position (may need manual redemption)")
        else:
            print(f"  ⏳ Still pending")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()

print("=" * 100)
print(f"SUMMARY: Settled {settled_count}/{len(pending_bets)} bets")
print("=" * 100)
