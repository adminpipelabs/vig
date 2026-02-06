# Quick Fix Checklist - Get Bot Trading Now

## The Problem
Bright Data proxy returns 403 Forbidden → Bot can't connect to Polymarket APIs → No live feed, no trading

## Quick Fix (5 minutes)

### Step 1: Check Bright Data Dashboard
Go to: **https://brightdata.com/cp/start**

1. **Login** → Click **"Residential Proxies"**
2. **Find your zone**: `residential_proxy1`
3. **Check these 3 things**:

#### ✅ Zone Status
- Must say **"Active"** (green)
- If "Suspended" → Click "Activate" or contact support

#### ✅ Account Balance  
- Go to **Billing** tab
- Must have **credits/balance** (e.g., $10+)
- If $0 → Add payment method and top up

#### ✅ Access Policy
- Go to **Access Policy** or **Network Access** tab
- **Whitelist** should be empty OR include:
  - `*.polymarket.com`
  - `clob.polymarket.com`
  - `gamma-api.polymarket.com`
- If blocked → Remove from blacklist or add to whitelist

### Step 2: Verify Credentials Match

In Bright Data Dashboard → Your zone → **Overview** tab:

**Username should be**:
```
brd-customer-hl_b4689439-zone-residential_proxy1
```

**Password should be**:
```
5teowbs6s9c9
```

**Host**: `brd.superproxy.io`  
**Port**: `33335` (NOT 22225)

### Step 3: Test Locally (Optional)

From your Mac terminal:
```bash
curl -x "http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335" \
  "https://lumtest.com/myip.json"
```

**Expected**: Returns JSON with IP address  
**If 403**: Credentials wrong or zone blocked

### Step 4: Wait for Railway Deploy

After fixing Bright Data:
- Railway auto-deploys latest code
- Check logs for: `✅ Proxy test: Connected to Bright Data`
- Bot should start trading within 1 hour

---

## If Still 403 After Checking Above

**Contact Bright Data Support**:

**Subject**: "403 Forbidden - Zone: residential_proxy1"

**Message**:
```
My residential proxy zone "residential_proxy1" is returning 403 Forbidden.

Zone: residential_proxy1
Customer ID: hl_b4689439
Status: Active (verified)
Balance: Has credits (verified)

Credentials work from my local machine but fail from Railway hosting.

Please verify:
1. Zone is configured for programmatic/API access
2. Railway IPs are allowed (cloud hosting)
3. No access policy blocking Polymarket domains
4. Account/zone is not restricted

Thank you!
```

---

## What Changed in Code

✅ Removed URL encoding (might have broken auth)  
✅ Simplified proxy URL format  
✅ Added startup proxy test (shows in logs if proxy works)  
✅ All HTTP clients now use proxy automatically

**Code is ready** - just need Bright Data account/zone fixed.
