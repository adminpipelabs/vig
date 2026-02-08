#!/usr/bin/env python3
"""
Quick script to check if bets are being placed.
Shows recent bets, bot status, and activity.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# Import database
from db import Database
from config import Config

def check_bets():
    """Check bet activity"""
    config = Config()
    database_url = os.getenv("DATABASE_URL")
    db = Database(config.db_path, database_url=database_url)
    
    print("=" * 70)
    print("VIG BOT BET ACTIVITY CHECK")
    print("=" * 70)
    print()
    
    # 1. Check bot status
    print("1️⃣  Bot Status:")
    try:
        status = db.get_bot_status("main")
        if status:
            print(f"   Status: {status.get('status', 'unknown')}")
            print(f"   Current Window: {status.get('current_window', 'N/A')}")
            if status.get('error_message'):
                print(f"   ⚠️  Error: {status.get('error_message')}")
            print(f"   Last Heartbeat: {status.get('last_heartbeat', 'N/A')}")
            print(f"   Scan Count: {status.get('scan_count', 0)}")
        else:
            print("   ⚠️  No bot status found")
    except Exception as e:
        print(f"   ❌ Error checking status: {e}")
    print()
    
    # 2. Check recent bets
    print("2️⃣  Recent Bets (last 10):")
    try:
        recent_bets = db.get_recent_bets(10)
        if recent_bets:
            for bet in recent_bets[:10]:
                result_emoji = "✅" if bet.result == "won" else "❌" if bet.result == "lost" else "⏳"
                paper_str = "PAPER" if bet.paper else "LIVE"
                print(f"   {result_emoji} [{paper_str}] {bet.market_question[:50]}")
                print(f"      ${bet.amount:.2f} @ ${bet.price:.2f} | {bet.result} | {bet.placed_at[:19]}")
        else:
            print("   ⚠️  No resolved bets found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # 3. Check pending bets
    print("3️⃣  Pending Bets:")
    try:
        pending = db.get_all_pending_bets()
        if pending:
            print(f"   Found {len(pending)} pending bet(s):")
            for bet in pending[:5]:
                paper_str = "PAPER" if bet.paper else "LIVE"
                print(f"   ⏳ [{paper_str}] {bet.market_question[:50]}")
                print(f"      ${bet.amount:.2f} @ ${bet.price:.2f} | Placed: {bet.placed_at[:19]}")
            if len(pending) > 5:
                print(f"   ... and {len(pending) - 5} more")
        else:
            print("   ✅ No pending bets")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # 4. Check recent windows
    print("4️⃣  Recent Windows:")
    try:
        windows = db.get_recent_windows(5)
        if windows:
            for w in windows:
                print(f"   Window {w.id}: {w.bets_placed} bets | ${w.deployed:.2f} deployed")
                print(f"      {w.bets_won}W {w.bets_lost}L | Profit: ${w.profit:.2f} | {w.started_at[:19]}")
        else:
            print("   ⚠️  No windows found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # 5. Overall stats
    print("5️⃣  Overall Stats:")
    try:
        stats = db.get_all_stats()
        total = stats.get('total_bets', 0) or 0
        wins = stats.get('wins', 0) or 0
        losses = stats.get('losses', 0) or 0
        pending = stats.get('pending', 0) or 0
        profit = stats.get('total_profit', 0) or 0
        
        resolved = wins + losses
        win_rate = (wins / resolved * 100) if resolved > 0 else 0
        
        print(f"   Total Bets: {total}")
        print(f"   Wins: {wins} | Losses: {losses} | Pending: {pending}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Total Profit: ${profit:.2f}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()
    
    # 6. Check if bot is actively scanning
    print("6️⃣  Activity Check:")
    try:
        # Check for bets placed in last hour
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        
        if db.use_postgres:
            c = db.conn.cursor()
            c.execute("""
                SELECT COUNT(*) FROM bets 
                WHERE placed_at >= %s
            """, (one_hour_ago,))
            recent_count = c.fetchone()[0]
        else:
            c = db.conn.cursor()
            c.execute("""
                SELECT COUNT(*) FROM bets 
                WHERE placed_at >= ?
            """, (one_hour_ago,))
            recent_count = c.fetchone()[0]
        
        if recent_count > 0:
            print(f"   ✅ Active! {recent_count} bet(s) placed in last hour")
        else:
            print(f"   ⚠️  No bets placed in last hour")
            print(f"   Check Railway logs for: 'Scanning Polymarket' or 'Placing bets'")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    print("=" * 70)
    db.close()

if __name__ == "__main__":
    check_bets()
