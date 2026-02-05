#!/usr/bin/env python3
"""
Check ERC1155 token balances for winning positions
Confirms if winning shares are still held (unredeemed)
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

env_path = Path('/Users/mikaelo/vig/.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Config
ALCHEMY_RPC = "https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
WALLET = "0x989B7F2308924eA72109367467B8F8e4d5ea5A1D"
# Also check funder address if different
FUNDER_ADDRESS = os.getenv("POLYGON_FUNDER_ADDRESS", WALLET)

# ERC1155 balanceOf ABI
ERC1155_ABI = [{
    'inputs': [
        {'name': 'account', 'type': 'address'},
        {'name': 'id', 'type': 'uint256'}
    ],
    'name': 'balanceOf',
    'outputs': [{'name': '', 'type': 'uint256'}],
    'stateMutability': 'view',
    'type': 'function'
}]

w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
ctf = w3.eth.contract(address=Web3.to_checksum_address(CTF_ADDRESS), abi=ERC1155_ABI)

# Get won bets
db = sqlite3.connect('vig.db')
db.row_factory = sqlite3.Row

won_bets = db.execute("""
    SELECT id, market_question, token_id, condition_id, size, payout
    FROM bets 
    WHERE result='won' AND paper=0
    ORDER BY placed_at
""").fetchall()

print("=" * 100)
print("ERC1155 TOKEN BALANCE CHECK — Confirming Unredeemed Winning Shares")
print("=" * 100)
print(f"\nWallet: {WALLET}")
if FUNDER_ADDRESS != WALLET:
    print(f"Funder/Proxy: {FUNDER_ADDRESS}")
print(f"CTF Contract: {CTF_ADDRESS}")
print(f"\nChecking {len(won_bets)} winning positions...\n")

total_unredeemed = 0.0
unredeemed_bets = []

for bet in won_bets:
    token_id = bet['token_id']
    expected_shares = bet['size']
    
    try:
        # Convert token_id to int (it's stored as string)
        token_id_int = int(token_id)
        
        # Check balance in main wallet
        balance = ctf.functions.balanceOf(
            Web3.to_checksum_address(WALLET),
            token_id_int
        ).call()
        
        # Also check funder address if different
        if FUNDER_ADDRESS != WALLET:
            balance_funder = ctf.functions.balanceOf(
                Web3.to_checksum_address(FUNDER_ADDRESS),
                token_id_int
            ).call()
            balance = max(balance, balance_funder)  # Use whichever has balance
        
        balance_formatted = balance / 1e18  # ERC1155 uses 18 decimals
        
        if balance_formatted > 0:
            print(f"✅ Bet #{bet['id']}: {bet['market_question'][:45]}...")
            print(f"   Token ID: {token_id[:30]}...")
            print(f"   Expected shares: {expected_shares:.2f}")
            print(f"   Current balance: {balance_formatted:.2f}")
            print(f"   Value if redeemed: ${balance_formatted:.2f}")
            print()
            
            total_unredeemed += balance_formatted
            unredeemed_bets.append({
                'id': bet['id'],
                'market': bet['market_question'],
                'token_id': token_id,
                'condition_id': bet['condition_id'],
                'shares': balance_formatted,
                'value': balance_formatted
            })
        else:
            print(f"❌ Bet #{bet['id']}: {bet['market_question'][:45]}...")
            print(f"   Balance: 0 (already redeemed or lost)")
            print()
            
    except Exception as e:
        print(f"⚠️  Bet #{bet['id']}: Error checking balance - {e}")
        print()

print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total unredeemed winning shares: {total_unredeemed:.2f}")
print(f"Value if redeemed: ${total_unredeemed:.2f}")
print(f"Unredeemed positions: {len(unredeemed_bets)}")

if unredeemed_bets:
    print("\n" + "=" * 100)
    print("UNREDEEMED POSITIONS (ready for redemption)")
    print("=" * 100)
    for bet in unredeemed_bets:
        print(f"\nBet #{bet['id']}: {bet['market']}")
        print(f"  Condition ID: {bet['condition_id']}")
        print(f"  Token ID: {bet['token_id'][:30]}...")
        print(f"  Shares: {bet['shares']:.2f}")
        print(f"  Value: ${bet['value']:.2f}")

db.close()
