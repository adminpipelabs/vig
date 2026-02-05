# ERC1155 Balance Check Results

## Finding

All ERC1155 token balances checked show **0.00** for the main wallet address.

## Possible Explanations

1. **Tokens held at proxy address:** The Dev mentioned `0xdcad0a12...` is the Polymarket Proxy (deposit wallet). Tokens might be held there instead of the main wallet.

2. **Token ID format issue:** ERC1155 token IDs might need different formatting or the contract might use a different structure.

3. **Already redeemed:** Some tokens might have been redeemed manually or automatically.

4. **Decimals:** ERC1155 might not use 18 decimals - could be raw integer values.

## Next Steps

1. **Check proxy address:** Query ERC1155 balances at `0xdcad0a12...` (full address from Polygonscan)
2. **Check Polygonscan directly:** Look at the wallet's ERC1155 token holdings tab
3. **Verify token_id format:** Confirm if token_id needs to be converted differently

## On-Chain Evidence

From Dev's analysis:
- ✅ 22 outgoing transfers (bets placed) confirmed
- ❌ 0 incoming transfers (no redemptions) confirmed
- **Conclusion:** Winnings exist as ERC1155 tokens somewhere, just need to find where

## Action Items

1. Get full proxy address from Polygonscan transaction history
2. Check ERC1155 balances at proxy address
3. If found, create redemption script targeting proxy address
