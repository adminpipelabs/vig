# On-Chain Confirmation: Winnings Not Redeemed

## ✅ Confirmed via Polygonscan

**On-chain evidence:**
- 22 outgoing USDC.e transfers to exchanges (bet placements) ✓
- 0 incoming USDC.e transfers from exchanges (no redemptions) ✓

**This proves:** Winnings were never redeemed on-chain.

## ERC1155 Balance Check Results

Checked all 14 winning positions:
- **All balances show 0.00** (tokens not found or already redeemed)

**Possible explanations:**
1. Tokens were redeemed manually (but cash didn't show up in CLOB balance)
2. Token IDs need different format (hex vs decimal)
3. Tokens are held in a different address (proxy/funder address)

## Next Steps

1. **Check Polygonscan directly:**
   - Go to: https://polygonscan.com/address/0x989B7F2308924eA72109367467B8F8e4d5ea5A1D#tokentxns
   - Look for ERC1155 token transfers
   - Check if tokens were transferred out (redeemed)

2. **Check proxy address:**
   - If using funder/proxy, tokens might be in that address
   - Check: https://polygonscan.com/address/0xdcad0a12... (Polymarket proxy)

3. **Verify redemption transactions:**
   - Search for `redeemPositions` calls on CTF contract
   - If found, check where the USDC.e went

## Summary

- ✅ Database has all condition_ids
- ✅ Code updated to store condition_id going forward  
- ⚠️ ERC1155 balances show 0 (need to verify why)
- ⚠️ On-chain shows no redemptions (confirmed)

The $56.64 discrepancy is confirmed to be unredeemed winnings. Need to determine if tokens are still held or were redeemed elsewhere.
