# Claim/Redemption Status Report

## Summary

**Problem:** Bot marks bets as "won" but doesn't convert winning shares back to cash. $215.85 locked in positions.

**Root Cause:** No API method exists in `py-clob-client` to redeem/claim winning positions. Positions are tracked internally by Polymarket, not as sellable ERC1155 tokens.

## Findings

### 1. API Method Check
- ✅ Checked all 62 methods in `ClobClient`
- ❌ No `redeem`, `claim`, `settle`, or `withdraw` methods found
- ✅ Only balance-related: `get_balance_allowance`, `update_balance_allowance`

### 2. Sell Attempt Results
- **Total won bets:** 14
- **Total position value:** $215.85
- **Closed markets (12):** $178.00 - Error: "orderbook does not exist"
- **Active markets (2):** $37.85 - Error: "not enough balance / allowance"

### 3. Key Insights

**Closed Markets:**
- Orderbook removed after market closes
- Cannot sell via CLOB API
- Need alternative redemption mechanism

**Active Markets:**
- Even though markets are still open, positions show "not enough balance"
- Confirms positions are tracked internally, not as actual tokens we can sell
- Polymarket's internal accounting system holds the positions

## Current Status

**Available Cash:** $0.24 USDC.e  
**Position Value:** $215.85 (locked)  
**Total Portfolio:** ~$216.09

## Next Steps

### Immediate Actions Required:

1. **Check Polymarket.com UI:**
   - Go to Portfolio page
   - Look for "Claim", "Redeem", or "Withdraw" buttons on winning positions
   - Check Activity tab for auto-settlement transactions
   - Screenshot any relevant UI elements

2. **Investigate Auto-Settlement:**
   - Check if Polymarket auto-settles positions after a delay (24-48 hours)
   - Review Activity tab for any settlement patterns
   - Check if there's a time-based auto-claim mechanism

3. **Alternative Approaches:**
   - **CTF Contract Direct Call:** If positions are on-chain (unlikely based on ERC1155 balance = 0)
   - **Exchange Contract:** Check if exchange has a `settle` or `withdraw` function
   - **Manual Claim:** If UI has claim button, may need to automate via browser automation

### Code Changes Made:

1. ✅ Updated `bet_manager.py` to attempt selling after marking as won
2. ✅ Created `sell_winning_positions.py` script for manual testing
3. ✅ Created `check_won_markets_status.py` to categorize SELL vs REDEEM
4. ✅ Created `check_clob_methods.py` to explore available API methods

### Settlement Logic Update:

The bot now attempts to sell winning positions automatically, but:
- Will fail silently for closed markets (expected)
- Will fail for active markets due to internal accounting (needs investigation)
- Logs warnings but doesn't block settlement

## Questions for Dev:

1. **Does Polymarket auto-settle winning positions after a delay?**
   - If yes, how long? (24h? 48h?)
   - Does it require any action?

2. **Is there a manual claim button on Polymarket.com?**
   - If yes, can we automate it?
   - What's the exact flow?

3. **Are positions held by the exchange contract or our wallet?**
   - If exchange, is there an exchange-level settle function?
   - If wallet, why don't ERC1155 balances show them?

4. **Should we wait for auto-settlement or is manual action required?**

## Files Created:

- `check_clob_methods.py` - Explores all available CLOB API methods
- `check_won_markets_status.py` - Categorizes won bets (SELL vs REDEEM)
- `sell_winning_positions.py` - Attempts to sell all winning positions
- `CLAIM_REDEMPTION_STATUS.md` - This document

## Updated Files:

- `bet_manager.py` - Added `_sell_winning_position()` method that attempts to sell after settlement
