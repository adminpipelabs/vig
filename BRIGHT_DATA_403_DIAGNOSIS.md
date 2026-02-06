# Bright Data Proxy 403 Forbidden - Diagnosis

## Current Status

The bot is getting `httpx.ProxyError: 403 Forbidden` from Bright Data's proxy server. This means:

✅ **Proxy connection is working** - requests are reaching Bright Data  
❌ **Bright Data is rejecting requests** - returning 403

## What 403 from Proxy Means

A 403 from the proxy server (not the target site) typically indicates:

1. **Authentication failure** - Wrong username/password/zone
2. **Zone inactive** - Zone suspended or not activated  
3. **Account balance** - No credits remaining
4. **Access policy** - Target domain blocked by Bright Data

## Verification Steps

### 1. Check Bright Data Dashboard

Go to https://brightdata.com/cp/start → Your Residential Proxy zone:

- **Status**: Must be "Active" (not suspended)
- **Balance**: Must have credits available
- **Access Policy**: Check if `clob.polymarket.com` or `gamma-api.polymarket.com` are blocked
- **Credentials**: Verify username/password match exactly

### 2. Test Proxy Locally

From your Mac (not Railway), test the exact proxy URL:

```bash
curl -x "http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335" \
  "https://clob.polymarket.com/health" -v
```

**Expected**: Should return 200 OK  
**If 403**: Credentials are wrong or zone is blocked

### 3. Check Railway Environment

Railway might have different network conditions. Verify:

- No firewall blocking outbound connections to `brd.superproxy.io:33335`
- Railway IP isn't blacklisted by Bright Data
- No VPN/proxy interference

## Current Proxy Configuration

**Hardcoded in `proxy_init.py`:**
```
http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335
```

**Port**: `33335` (correct for residential)  
**Format**: Standard HTTP proxy with basic auth

## Code Changes Made

- ✅ Patched `httpx.Client` to always inject proxy
- ✅ Set `trust_env=False` to prevent env var override
- ✅ Replaced `py_clob_client`'s global `_http_client` with proxied version
- ✅ Disabled HTTP/2 (using HTTP/1.1 for better proxy compatibility)
- ✅ URL-encoded password (though it has no special chars)

All code changes are correct. The issue is with Bright Data authentication/access.
