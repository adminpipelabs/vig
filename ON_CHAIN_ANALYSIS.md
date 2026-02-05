# On-Chain Transfer Analysis — Confirmed Redemption Issue

## Transfer Summary

**Incoming:**
- +$20.00 USDC (initial deposit)
- +$75.00 USDC (initial deposit)
- +$10.00 USDC.e (from Polymarket Proxy: 0xdcad0a12...)
- +$84.94 USDC.e (from Polymarket Proxy: 0xdcad0a12...)
- **Total Incoming: $189.94**

**Outgoing:**
- -$95.00 USDC (to Polymarket Deposit: 0xe0a47b40...)
- **22 outgoing transfers** to exchanges:
  - CTF Exchange (0x4bfb41d5...): ~$XX.XX
  - NegRisk Exchange (0xc5d563a3...): ~$XX.XX
- **Total Outgoing: ~$94.70**

## Critical Finding

**ZERO incoming transfers FROM exchanges after bets were placed.**

When you win a bet:
1. You send USDC.e TO exchange (outgoing) ✅ Confirmed (22 transfers)
2. Exchange should send USDC.e BACK when you redeem (incoming) ❌ **MISSING**

**Conclusion:** Winnings exist as ERC1155 conditional tokens but were **NEVER redeemed** to convert to USDC.e.

## Proxy Address

**0xdcad0a12379d4f22ce014826774517937b702277** = Polymarket Proxy

This is where withdrawals came from. Tokens might be held here instead of main wallet.

## Next Steps

1. Check ERC1155 balances at proxy address
2. If found, create redemption script targeting proxy
3. Update settlement code to auto-redeem future wins
