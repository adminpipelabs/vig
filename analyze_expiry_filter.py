#!/usr/bin/env python3
"""
Analyze if the expiry filter was working correctly when bets were placed
"""
import os
import sqlite3
import httpx
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

conn = sqlite3.connect('/Users/mikaelo/vig/vig.db')
conn.row_factory = sqlite3.Row

# Get ALL bets (not just pending) to see the pattern
all_bets = conn.execute("""
    SELECT id, market_question, market_id, placed_at, amount, result
    FROM bets 
    WHERE paper=0
    ORDER BY placed_at
""").fetchall()

print("=" * 100)
print("ANALYZING EXPIRY FILTER - WHEN BETS WERE PLACED VS EXPIRY")
print("=" * 100)
print()

client = httpx.Client(timeout=30)
now = datetime.now(timezone.utc)

bets_with_expiry_info = []

for bet in all_bets:
    market_id = bet['market_id']
    placed_at = datetime.fromisoformat(bet['placed_at'].replace('Z', '+00:00'))
    
    try:
        resp = client.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=10)
        if resp.status_code == 200:
            market = resp.json()
            end_date_str = market.get('endDate') or market.get('endDateIso', '')
            
            if end_date_str:
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                           "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        end_date = datetime.strptime(end_date_str.replace('Z', ''), fmt.replace('Z', ''))
                        end_date = end_date.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    continue
                
                # Calculate minutes to expiry AT THE TIME THE BET WAS PLACED
                minutes_to_expiry_when_placed = (end_date - placed_at).total_seconds() / 60
                
                bets_with_expiry_info.append({
                    'bet': bet,
                    'end_date': end_date,
                    'minutes_to_expiry_when_placed': minutes_to_expiry_when_placed
                })
    except Exception as e:
        pass  # Skip if can't fetch

# Sort by when placed
bets_with_expiry_info.sort(key=lambda x: x['bet']['placed_at'])

print("BET PLACEMENT vs EXPIRY ANALYSIS")
print("-" * 100)
print()

violations = []
compliant = []

for item in bets_with_expiry_info:
    bet = item['bet']
    minutes = item['minutes_to_expiry_when_placed']
    hours = minutes / 60
    
    status = "✅" if 5 <= minutes <= 60 else "⚠️"
    
    if minutes < 5:
        reason = f"Too soon ({minutes:.1f} min)"
    elif minutes > 60:
        reason = f"Too far ({hours:.1f} hours)"
        violations.append(item)
    else:
        reason = "OK"
        compliant.append(item)
    
    print(f"{status} Bet {bet['id']}: {bet['market_question'][:50]}")
    print(f"   Placed: {bet['placed_at']}")
    print(f"   Expires: {item['end_date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   Minutes to expiry when placed: {minutes:.1f} ({hours:.2f} hours)")
    print(f"   Status: {bet['result']} | Amount: ${bet['amount']:.2f}")
    print(f"   Filter check: {reason}")
    print()

print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total bets analyzed: {len(bets_with_expiry_info)}")
print(f"✅ Compliant (5-60 min): {len(compliant)}")
print(f"⚠️  Violations (> 60 min): {len(violations)}")
print()

if violations:
    print("VIOLATIONS (> 60 minutes to expiry when placed):")
    total_violation_value = 0
    for item in violations:
        bet = item['bet']
        minutes = item['minutes_to_expiry_when_placed']
        hours = minutes / 60
        total_violation_value += bet['amount']
        print(f"  - Bet {bet['id']}: {hours:.1f} hours | ${bet['amount']:.2f} | Status: {bet['result']}")
    print(f"\nTotal value in violations: ${total_violation_value:.2f}")
    print()
    print("These bets were placed on markets expiring > 60 minutes out.")
    print("This confirms the expiry filter bug - bot should only bet on 5-60 min markets.")

conn.close()
client.close()
