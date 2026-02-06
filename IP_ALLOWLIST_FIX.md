# IP Allowlist Fix - Bright Data

## Issue Found

Your Bright Data zone shows **"IP Allowlist"** with an **"Edit"** button.

**Problem**: If IP allowlist is enabled, only whitelisted IPs can use the proxy. Railway's IPs are probably NOT on the list → 403 Forbidden.

## Quick Fix

### Option 1: Disable IP Allowlist (Recommended)

1. In Bright Data Dashboard → Your zone → **"IP Allowlist"** section
2. Click **"Edit"**
3. **Disable** or **clear** the allowlist
4. Save

This allows any IP to use the proxy (which is what we need for Railway).

### Option 2: Add Railway IPs to Allowlist

If you want to keep allowlist enabled:

1. Get Railway's outbound IP:
   - Railway doesn't provide static IPs
   - IPs change per deployment
   - This is why Option 1 is better

2. Add IP ranges (if Bright Data supports ranges)

**Better**: Just disable the allowlist for now.

---

## Verify Settings Match

Your dashboard shows:
- ✅ Username: `brd-customer-hl_b4689439-zone-residential_proxy1` (matches code)
- ✅ Password: `5teowbs6s9c9` (matches code)
- ✅ Host: `brd.superproxy.io` (matches code)
- ✅ Port: `33335` (matches code)
- ✅ Status: Active
- ✅ Balance: $2 (has funds)
- ⚠️ **IP Allowlist**: Check this!

---

## After Fixing IP Allowlist

1. **Disable IP Allowlist** in Bright Data dashboard
2. **Wait 1-2 minutes** for changes to propagate
3. **Railway will auto-redeploy** (or manually redeploy)
4. **Check logs** for: `✅ Proxy test: Connected to Bright Data`
5. **Bot should start trading** within the next hour

---

## Test Command (From Your Mac)

After disabling allowlist, test:
```bash
curl -x "http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335" \
  "https://clob.polymarket.com/health"
```

Should return 200 OK (not 403).
