# How to Redeem Winning Positions

## Current Situation

- **14 won bets** with **$215.85** in winning shares
- Positions are **resolved** (markets closed, final prices set)
- Shares need to be **redeemed** to convert to cash

## Redemption Options

### Option 1: Direct CTF Contract Call (Recommended)

We have a script `redeem_winnings.py` that calls the CTF contract's `redeemPositions` function directly.

**How it works:**
1. Calls the Conditional Token Framework (CTF) contract on Polygon
2. Uses `redeemPositions()` function to convert winning shares to USDC.e
3. One redemption per `condition_id` covers all positions in that market

**To run:**
```bash
cd /Users/mikaelo/vig
python3.11 redeem_winnings.py
```

**What it does:**
- Gets all won bets with `condition_id` from database
- Groups by unique `condition_id` (one redemption per market)
- Calls CTF contract `redeemPositions()` for each condition
- Converts winning shares to USDC.e collateral

**Requirements:**
- POL balance for gas (~0.01 POL per redemption)
- Valid `condition_id` for each won bet
- Markets must be fully resolved (closed)

### Option 2: Check Polymarket UI

1. Go to https://polymarket.com
2. Connect wallet
3. Go to Portfolio → Positions
4. Look for "Redeem" or "Claim" buttons on winning positions
5. Click to redeem manually

**Note:** If UI has redeem buttons, use those - they're safer and handle edge cases.

### Option 3: CLOB API (Not Available)

The CLOB API doesn't have a direct redemption method. We checked all 62 methods - no `redeem`, `claim`, or `settle` methods exist.

## Current Script Status

**File:** `redeem_winnings.py`

**Features:**
- ✅ Gets won bets from database
- ✅ Groups by condition_id
- ✅ Calls CTF contract directly
- ✅ Handles gas estimation
- ✅ Waits for confirmations

**What to check before running:**
1. POL balance (need ~0.01 POL per redemption)
2. All won bets have `condition_id` populated
3. Markets are fully resolved (closed = True)

## Expected Result

After redemption:
- Winning shares converted to USDC.e
- Cash balance increases by ~$215.85
- Positions removed from Polymarket UI
- Funds available for new bets

## Next Steps

1. **Check POL balance:**
   ```bash
   python3.11 -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm')); print(f'POL: {w3.from_wei(w3.eth.get_balance(\"0x989B7F2308924eA72109367467B8F8e4d5ea5A1D\"), \"ether\"):.4f}')"
   ```

2. **Verify condition_ids:**
   ```bash
   sqlite3 vig.db "SELECT COUNT(*) FROM bets WHERE paper=0 AND result='won' AND condition_id IS NOT NULL AND condition_id != ''"
   ```

3. **Run redemption:**
   ```bash
   python3.11 redeem_winnings.py
   ```

4. **Check balance after:**
   ```bash
   python3.11 -c "from py_clob_client.client import ClobClient; from py_clob_client.clob_types import BalanceAllowanceParams, AssetType; import os; from dotenv import load_dotenv; load_dotenv(); client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137); client.set_api_creds(client.create_or_derive_api_creds()); params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0); bal = client.get_balance_allowance(params); print(f'Balance: \${float(bal.get(\"balance\", 0)) / 1e6:.2f}')"
   ```

## Important Notes

- **One redemption per condition_id** - covers all positions in that market
- **Gas cost:** ~0.01 POL per redemption (14 redemptions = ~0.14 POL)
- **On-chain transaction** - visible on Polygonscan
- **Irreversible** - make sure markets are fully resolved before redeeming

## Troubleshooting

**If redemption fails:**
1. Check if markets are fully resolved (closed = True)
2. Verify condition_id format (must be 32 bytes hex)
3. Check POL balance for gas
4. Check contract address is correct (CTF: 0x4D97DCd97eC945f40cF65F87097ACe5EA0476045)

**If positions don't show up:**
- Positions might be tracked internally by Polymarket
- May need to wait for auto-settlement
- Check Polymarket UI for manual redemption buttons
