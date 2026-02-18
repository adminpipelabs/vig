# Switch to Legacy CLOB API

Since US API authentication is failing, switch to the legacy CLOB API that worked before.

## Railway Configuration

In Railway → **"vig"** service → **Variables**:

### Remove/Disable US API:
- `USE_US_API` = `false` (or delete it)

### Add Legacy CLOB API Keys:
- `POLYGON_PRIVATE_KEY` = `0xb27a70055604302393a3657e8ce2a7747b99ee93ab590f85ad3cd4fbb86d1ee2`
- `POLYGON_FUNDER_ADDRESS` = `0x...` (your wallet address - derive from private key if needed)

## Derive Wallet Address

If you don't have the wallet address, derive it from the private key:

```python
from eth_account import Account
private_key = "0xb27a70055604302393a3657e8ce2a7747b99ee93ab590f85ad3cd4fbb86d1ee2"
account = Account.from_key(private_key)
print(f"Address: {account.address}")
```

## After Updating Railway

1. Save variables
2. Redeploy service
3. Check logs - should see "Using legacy CLOB API" instead of "Using Polymarket US API"

## Note

Legacy CLOB API uses Polygon network and may have Cloudflare blocking issues, but it should work for placing bets.
