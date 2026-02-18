# US API Key Format Guide

## Error You're Seeing
```
[vig.auth] ERROR: Failed to load private key: An Ed25519 private key is 32 bytes long
```

## What Format Should the Key Be?

The `POLYMARKET_US_PRIVATE_KEY` environment variable accepts:

### Option 1: Hex Format (64 characters)
```
POLYMARKET_US_PRIVATE_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```
- 64 hex characters (0-9, a-f)
- Represents 32 bytes

### Option 2: Base64 Format (44 characters, no padding)
```
POLYMARKET_US_PRIVATE_KEY=ASNFZ4mrze8BI0VniavN7wEjRWeJq83vASNFZ4mrze8=
```
- 44 base64 characters (or 88 with padding)
- Represents 32 bytes

### Option 3: PEM Format
```
POLYMARKET_US_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIE...
-----END PRIVATE KEY-----
```
- Full PEM format with headers

## How to Check Your Key Format

In Railway → Environment Variables → `POLYMARKET_US_PRIVATE_KEY`:

1. **Check length:**
   - Hex: Should be exactly 64 characters
   - Base64: Should be 44 or 88 characters
   - PEM: Will be longer with `-----BEGIN` and `-----END`

2. **Check characters:**
   - Hex: Only `0-9`, `a-f`, `A-F`
   - Base64: `A-Z`, `a-z`, `0-9`, `+`, `/`, `=`

## Common Issues

1. **Key has extra spaces/newlines** → Remove them
2. **Key is too short** → Check if you copied the full key
3. **Key has wrong format** → Convert to hex or base64

## Fix in Railway

1. Go to Railway → Your Service → Variables
2. Find `POLYMARKET_US_PRIVATE_KEY`
3. Make sure it's:
   - Exactly 64 hex characters, OR
   - Exactly 44 base64 characters, OR
   - Valid PEM format
4. Remove any spaces, newlines, or quotes
5. Redeploy

## Test Locally

```bash
python3 -c "
from auth import PolymarketUSAuth
key = 'YOUR_KEY_HERE'
auth = PolymarketUSAuth('test-key-id', key)
print('✅ Key format is valid')
"
```
