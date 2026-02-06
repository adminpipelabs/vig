# Cloudflare Blocking Fix Guide

**Issue:** Bot getting 403 errors from Cloudflare when placing orders  
**Error:** `PolyApiException[status_code=403, error_message=<!DOCTYPE html>...Cloudflare blocking page...]`

---

## 🔍 **Root Cause**

Cloudflare is blocking requests from Railway's datacenter IP (`162.220.232.57`). This happens because:
1. Railway uses datacenter IPs (not residential)
2. Cloudflare detects datacenter IPs and blocks them
3. Even with `RESIDENTIAL_PROXY_URL` set, if the proxy isn't working, requests go direct → blocked

---

## ✅ **Solution: Verify Proxy Configuration**

### **Step 1: Check Proxy URL Format**

**In Railway Dashboard → Service → Variables:**

The `RESIDENTIAL_PROXY_URL` should be:
```
http://username:password@proxy-host.example.com:22225
```

**Common Issues:**
- ❌ `http://user:pass@host:port` (placeholder values)
- ❌ Missing port number
- ❌ Wrong format (should have `http://` prefix)
- ❌ Extra spaces/newlines

**Fix:** Ensure it's a real proxy URL from your proxy provider (Bright Data, Smartproxy, etc.)

---

### **Step 2: Verify Proxy is Working**

**Test the proxy manually:**

```bash
# Replace with your actual proxy URL
export RESIDENTIAL_PROXY_URL="http://user:pass@proxy-host:port"

# Test if proxy works
curl -x "$RESIDENTIAL_PROXY_URL" https://clob.polymarket.com/health
```

**Expected:**
- ✅ Returns JSON response (proxy works)
- ❌ Returns Cloudflare blocking page (proxy not working)

---

### **Step 3: Check Railway Logs**

**After next deploy, check logs for:**

**✅ Good (proxy working):**
```
✅ Residential proxy configured: http://user:pass@...
HTTPS_PROXY env var is set (length: 45 chars)
ClobClient created - proxy should be active for all HTTP requests
✅ CLOB client initialized with residential proxy
```

**❌ Bad (proxy not working):**
```
⚠️  Proxy initialization failed: Invalid port: 'port'
⚠️  Direct connection failed: 403 Forbidden
❌ CLOUDflare BLOCKING DETECTED
```

---

## 🔧 **If Proxy Still Not Working**

### **Option 1: Use Paper Mode (Temporary)**

Set `PAPER_MODE=true` in Railway to test without placing real bets:
- Bot will scan markets ✅
- Bot will simulate bets ✅
- No Cloudflare blocking (doesn't call CLOB API) ✅

### **Option 2: Get a Working Residential Proxy**

**Recommended Providers:**
- **Bright Data** (formerly Luminati) - https://brightdata.com
- **Smartproxy** - https://smartproxy.com
- **Oxylabs** - https://oxylabs.io

**What you need:**
- Residential proxy (not datacenter)
- HTTP/HTTPS support
- Format: `http://username:password@proxy-host:port`

### **Option 3: Check Proxy Provider Dashboard**

1. Log into your proxy provider dashboard
2. Check if proxy is active/enabled
3. Verify IP rotation is working
4. Check for any IP blocks or restrictions
5. Test proxy from a different location

---

## 📋 **Current Status**

**From logs:**
- ✅ Bot is running (scanning markets)
- ✅ Database heartbeat working
- ✅ Bot resilient (doesn't crash on errors)
- ❌ CLOB API blocked by Cloudflare
- ❌ Proxy may not be configured correctly

**What's happening:**
1. Bot scans markets ✅
2. Bot finds candidates ✅
3. Bot tries to place bets ❌
4. Cloudflare blocks request (403) ❌
5. Bot logs error and continues ✅

---

## 🎯 **Next Steps**

1. **Check Railway Variables:**
   - Go to Railway → Service → Variables
   - Verify `RESIDENTIAL_PROXY_URL` is set correctly
   - Remove any placeholder values

2. **Test Proxy:**
   - Use curl command above to test proxy
   - If proxy doesn't work, contact proxy provider

3. **Monitor Logs:**
   - After fixing proxy, check Railway logs
   - Look for "✅ CLOB client initialized with residential proxy"
   - If still blocked, proxy URL might be wrong

4. **Alternative:**
   - Use `PAPER_MODE=true` for testing
   - Fix proxy configuration
   - Switch back to `PAPER_MODE=false` for live trading

---

## ⚠️ **Important Notes**

- **Proxy is REQUIRED for live trading** on Railway (datacenter IPs are blocked)
- **Paper mode doesn't need proxy** (simulates bets, doesn't call CLOB API)
- **Bot will continue running** even if proxy fails (scan-only mode)
- **Dashboard will show bot status** even if bets fail (shows "offline" or "error")

---

## 🔍 **Debugging Commands**

**Check if proxy env var is set:**
```bash
railway variables | grep RESIDENTIAL_PROXY
```

**Check bot logs for proxy status:**
```bash
railway logs | grep -i proxy
```

**Check for Cloudflare errors:**
```bash
railway logs | grep -i "403\|cloudflare\|blocked"
```

---

**After fixing proxy, bot should automatically start placing bets!** 🚀
