# Cloudflare Blocking Solution

## Problem
- Hetzner server in Stockholm, Sweden is being blocked by Cloudflare
- POST requests (order placement) return 403 errors
- GET requests (balance, orderbook) work fine

## Root Cause
According to Reddit discussion:
- Hetzner IPs may be flagged/blocked
- Geographic restrictions (Sweden not Netherlands/Belgium)
- Datacenter IPs are often blocked

## Solutions

### Option 1: Move to Netherlands/Belgium VPS (Recommended)
**Best providers:**
- DigitalOcean (Netherlands)
- AWS (Netherlands/Belgium)
- Contabo (Netherlands)

**Why:** Reddit users confirm these locations work without Cloudflare blocks

### Option 2: Use Proxy
**Free trial options:**
- proxyscrape.com (free trial)
- Bright Data (paid)
- Residential proxy services

**Setup:**
```bash
# Set in .env
HTTP_PROXY=http://username:password@proxy-host:port
HTTPS_PROXY=http://username:password@proxy-host:port
```

**Note:** py-clob-client uses httpx which respects `HTTP_PROXY`/`HTTPS_PROXY` env vars if `trust_env=True` (default)

### Option 3: AWS/DigitalOcean
- AWS works fine according to Reddit
- DigitalOcean Netherlands recommended
- Lower latency to Polymarket servers (London)

## Current Status
- Server: Hetzner, Stockholm, Sweden
- IP: 5.161.64.209
- Issue: Cloudflare 403 on POST requests
- GET requests: ✅ Working
- POST requests: ❌ Blocked

## Next Steps
1. Try setting HTTP_PROXY/HTTPS_PROXY env vars
2. If that doesn't work, move to Netherlands/Belgium VPS
3. Consider AWS or DigitalOcean for better reliability
