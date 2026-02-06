# Proxy Port Fix - Bright Data Residential Proxy

## Issue
Proxy authentication was failing with `403 Forbidden` because the wrong port was configured.

## Root Cause
Railway environment variable `RESIDENTIAL_PROXY_URL` was using port `22225` instead of the correct port `33335`.

## Correct Configuration

### Bright Data Residential Proxy Ports
- **Residential Proxy**: Port `33335` ✅
- **Datacenter Proxy**: Port `22225` ❌ (wrong for residential)

### Correct Proxy URL Format
```
http://brd-customer-{customer_id}-zone-{zone_name}:{password}@brd.superproxy.io:33335
```

### Example (with actual credentials)
```
http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335
```

## Fix Steps

1. **Railway Dashboard** → **vig-bot** service → **Variables**
2. Find `RESIDENTIAL_PROXY_URL`
3. Update port from `22225` to `33335`
4. **Save** (triggers auto-redeploy)

## Verification

After redeploy, check logs for:
```
✅ PROXY ACTIVE: httpx patched with brd.superproxy.io:33335
🌐 HTTPX Request #1: POST https://clob.polymarket.com/auth/api-key... (proxy: True)
```

If you see `(proxy: True)` and no `403 Forbidden` errors, the proxy is working correctly.

## Prevention

The code now includes validation that warns if port `22225` is detected for Bright Data residential proxies.
