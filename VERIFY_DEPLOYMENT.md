# Verify Railway Deployment - Step by Step

## 🎯 What to Expect After Deployment

### Immediate (First 5 minutes)

1. **Railway Build Completes**
   - Check Railway Dashboard → Deployments → Latest
   - Should show "Build successful" or "Deployed"
   - Build time: ~2-5 minutes

2. **Service Starts**
   - Both dashboard and bot should start
   - Check Railway → Logs tab

3. **Dashboard Accessible**
   - Railway provides a public URL (e.g., `https://vig-production.up.railway.app`)
   - Should load dashboard homepage

---

## ✅ Verification Checklist

### 1. Check Railway Logs

**Railway Dashboard → Your Service → Logs**

Look for these success messages:

```
✓ PostgreSQL connected (or SQLite if using volume)
CLOB client initialized with residential proxy
=== Vig v1 Starting (PAPER/LIVE mode) ===
📂 Reading from SQLite: vig.db (or PostgreSQL connection)
```

**Red flags to watch for:**
- ❌ `Failed to init CLOB client` - Check `POLYGON_PRIVATE_KEY`
- ❌ `DATABASE_URL not found` - Check database setup
- ❌ `Connection timeout` - PostgreSQL issue
- ❌ `403 Forbidden` from CLOB API - Proxy not working

---

### 2. Test Dashboard

**Open Railway URL** (e.g., `https://vig-production.up.railway.app`)

**What you should see:**
- ✅ Dashboard loads (no 502/503 errors)
- ✅ Shows bot statistics
- ✅ Recent bets table (may be empty if fresh deployment)
- ✅ Window history

**If dashboard doesn't load:**
- Check Railway → Settings → Healthcheck
- Verify `PORT` env var is set (Railway sets this automatically)
- Check logs for uvicorn errors

---

### 3. Verify Bot is Running

**Check Railway Logs** for bot activity:

```
WINDOW 1
Scanning Polymarket for expiring markets...
```

**Expected behavior:**
- Bot scans every hour (or `SCAN_INTERVAL_SECONDS`)
- Logs show market scanning activity
- If markets found, shows bet placement

**If bot not running:**
- Check logs for errors
- Verify `PAPER_MODE` is set correctly
- Check if bot process crashed (Railway will restart it)

---

### 4. Test Proxy (CLOB API)

**Check logs for proxy confirmation:**

```
Residential proxy configured: http://username@...
CLOB API calls will route through residential proxy
```

**Test with a live bet** (if `PAPER_MODE=false`):
- Bot should place orders successfully
- Check proxy dashboard (Bright Data/etc.) for traffic
- Verify no 403 errors from CLOB API

**If proxy not working:**
- Verify `RESIDENTIAL_PROXY_URL` is set correctly
- Check proxy credentials in proxy provider dashboard
- Test proxy manually: `curl -x $RESIDENTIAL_PROXY_URL https://clob.polymarket.com/health`

---

### 5. Verify Database

**PostgreSQL (if using):**

```bash
# From your local Mac (better connection)
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
```

**SQLite (if using volume):**
- Check Railway → Volumes → Verify volume is mounted
- Check logs for database file creation

**What to check:**
- ✅ Tables exist (bets, windows, circuit_breaker_log)
- ✅ Data persists after restart
- ✅ New bets are being stored

---

### 6. Test First Window

**Wait for first scan cycle** (default: 1 hour, or check `SCAN_INTERVAL_SECONDS`)

**Expected logs:**
```
WINDOW 1
Scanning Polymarket for expiring markets...
Gamma API returned X markets in expiry window
Placing bets on Y markets...
PAPER/LIVE: YES/NO Market Name @ $0.XX -- $XX.XX
```

**If no markets found:**
- Normal if no markets expiring in next hour
- Check `EXPIRY_WINDOW_MINUTES` setting
- Verify Gamma API is accessible (should work from Railway)

---

### 7. Monitor Metrics

**Railway Dashboard → Metrics Tab**

**Check:**
- ✅ CPU usage (should be low, <20% for bot)
- ✅ Memory usage (should be stable)
- ✅ Network traffic (proxy traffic should show)
- ✅ No error spikes

**Red flags:**
- ❌ CPU >80% constantly - Bot may be stuck in loop
- ❌ Memory growing continuously - Memory leak
- ❌ No network traffic - Bot not making API calls

---

## 🔍 Detailed Verification Steps

### Step 1: Check Service Status

```bash
# Railway CLI (if installed)
railway status

# Or check Railway Dashboard
# Service should show "Active" or "Running"
```

### Step 2: View Real-Time Logs

**Railway Dashboard → Logs Tab**

**What to look for:**
- Continuous log output (bot is running)
- No repeated error messages
- Window summaries appearing hourly

### Step 3: Test Dashboard Endpoints

**Open browser console** (F12) on dashboard page

**Check for:**
- ✅ No JavaScript errors
- ✅ API calls returning 200 OK
- ✅ Data loading correctly

**Or test API directly:**
```bash
curl https://your-railway-url.up.railway.app/api/stats
curl https://your-railway-url.up.railway.app/api/bets
```

### Step 4: Verify Environment Variables

**Railway Dashboard → Variables Tab**

**Required:**
- ✅ `RESIDENTIAL_PROXY_URL` (if using proxy)
- ✅ `POLYGON_PRIVATE_KEY` (for live mode)
- ✅ `DATABASE_URL` OR `DB_PATH` (database config)
- ✅ `PAPER_MODE` (set to `true` or `false`)

**Optional but recommended:**
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (notifications)
- `SCAN_INTERVAL_SECONDS` (default: 3600)
- `MIN_FAVORITE_PRICE` and `MAX_FAVORITE_PRICE`

### Step 5: Test Database Connection

**If using PostgreSQL:**

```bash
# From your Mac
export DATABASE_URL="postgresql://..."  # From Railway
psql "$DATABASE_URL" -c "\dt"  # List tables
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
```

**If using SQLite:**
- Check Railway → Volumes → Verify `/data/vig.db` exists
- Check file size is growing (new bets being stored)

---

## 🚨 Troubleshooting Common Issues

### Issue: Dashboard Returns 502/503

**Check:**
1. Service is running (Railway → Status)
2. Healthcheck is passing (Railway → Settings)
3. Port is correct (Railway sets `PORT` automatically)
4. Logs show uvicorn started successfully

**Fix:**
- Restart service in Railway
- Check logs for Python errors
- Verify `requirements.txt` has all dependencies

---

### Issue: Bot Not Scanning Markets

**Check:**
1. Bot process is running (check logs)
2. `SCAN_INTERVAL_SECONDS` is set correctly
3. No errors in logs
4. Gamma API is accessible (should work from Railway)

**Fix:**
- Check logs for "Scanning Polymarket..." messages
- Verify bot didn't crash (Railway auto-restarts)
- Check if `PAPER_MODE` is blocking execution

---

### Issue: CLOB API Returns 403

**This means proxy isn't working**

**Check:**
1. `RESIDENTIAL_PROXY_URL` is set correctly
2. Proxy credentials are valid
3. Proxy dashboard shows traffic
4. Logs show "Residential proxy configured"

**Fix:**
- Test proxy manually: `curl -x $RESIDENTIAL_PROXY_URL https://clob.polymarket.com/health`
- Verify proxy URL format: `http://username:password@host:port`
- Check proxy provider dashboard for blocked IPs

---

### Issue: Database Not Saving Data

**PostgreSQL:**
- Check connection string is correct
- Verify tables exist: `psql "$DATABASE_URL" -c "\dt"`
- Check for connection timeouts in logs

**SQLite:**
- Verify volume is mounted at `/data`
- Check `DB_PATH=/data/vig.db` is set
- Check file permissions

---

### Issue: Bot Crashes Repeatedly

**Check logs for:**
- Python errors/tracebacks
- Missing environment variables
- Import errors
- Database connection failures

**Fix:**
- Review error messages in logs
- Verify all required env vars are set
- Check `requirements.txt` dependencies
- Railway will auto-restart (up to 3 times by default)

---

## 📊 Success Indicators

### ✅ Everything Working:

1. **Dashboard loads** - No errors, shows stats
2. **Bot logs show activity** - Scanning markets every hour
3. **Bets being placed** - See bet logs in dashboard/logs
4. **Database storing data** - Row counts increasing
5. **No errors in logs** - Clean, continuous operation
6. **Proxy working** - No 403 errors from CLOB API
7. **Metrics stable** - CPU/memory within normal ranges

### ⚠️ Partial Success:

- Dashboard works but bot not running → Check bot process
- Bot running but no bets → Normal if no qualifying markets
- Proxy working but slow → Check proxy provider performance

### ❌ Issues:

- Dashboard 502/503 → Service not starting
- Bot crashes repeatedly → Check logs for errors
- CLOB API 403 → Proxy not configured correctly
- Database timeouts → PostgreSQL connection issue

---

## 🎯 Quick Verification Commands

### From Railway Dashboard:

1. **Check Status:** Service → Overview → Status should be "Active"
2. **View Logs:** Service → Logs → Should see continuous output
3. **Check Metrics:** Service → Metrics → CPU/Memory should be stable
4. **Test URL:** Copy Railway URL → Open in browser → Should see dashboard

### From Your Mac (if Railway CLI installed):

```bash
# Check status
railway status

# View logs
railway logs

# Check variables
railway variables
```

### Manual API Tests:

```bash
# Get Railway URL from dashboard
RAILWAY_URL="https://your-service.up.railway.app"

# Test dashboard
curl "$RAILWAY_URL/"

# Test API endpoints
curl "$RAILWAY_URL/api/stats"
curl "$RAILWAY_URL/api/bets?limit=10"
```

---

## 📝 What to Monitor Daily

1. **Railway Logs** - Check for errors
2. **Dashboard** - Verify stats updating
3. **Proxy Usage** - Check proxy provider dashboard for costs
4. **Database Growth** - Verify data is persisting
5. **Bot Activity** - Should see window summaries hourly
6. **Railway Metrics** - CPU/memory should be stable

---

## 🎉 Deployment Successful When:

- ✅ Dashboard accessible and showing data
- ✅ Bot running and scanning markets
- ✅ Bets being placed (if markets qualify)
- ✅ Database storing data correctly
- ✅ No errors in logs
- ✅ Proxy working (no 403 errors)
- ✅ Metrics stable

**If all checked, you're good to go! 🚀**
