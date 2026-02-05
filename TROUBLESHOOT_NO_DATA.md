# Troubleshooting: Dashboard Shows No Data

## Issue
Dashboard at https://vig-production.up.railway.app/ loads but shows:
- "No windows yet"
- "No bets yet"
- All values are "--" or empty
- "Loading..." in tables

## Possible Causes

### 1. Fresh Database (Most Likely)
**If this is a fresh deployment, the database is empty.**
- ✅ Dashboard is working correctly
- ✅ Database connection is working
- ⚠️ Just needs data from bot

**Solution:** Wait for bot to run first window (default: 1 hour), or trigger manually.

### 2. Database Connection Issue
**Dashboard can't read from database.**

**Check Railway Logs for:**
```
Error connecting to database
DATABASE_URL not found
psycopg2.OperationalError
```

**Solution:**
- Verify `DATABASE_URL` is set in Railway → Variables
- Check PostgreSQL service is running
- Test connection: `psql "$DATABASE_URL" -c "SELECT 1;"`

### 3. Bot Not Running
**Bot hasn't created any windows/bets yet.**

**Check Railway Logs for:**
- Bot process running?
- "Vig v1 Starting" message?
- Any window activity?

**Solution:**
- Verify bot is running (check logs)
- Wait for first scan cycle (default: 1 hour)
- Or manually trigger scan if dashboard has "Scan Now" button

### 4. Wrong Database
**Dashboard reading from different database than bot.**

**Check:**
- Bot using PostgreSQL but dashboard using SQLite (or vice versa)
- Different `DATABASE_URL` values
- Database path mismatch

**Solution:**
- Verify both bot and dashboard use same `DATABASE_URL`
- Check Railway → Variables → `DATABASE_URL`

## Quick Diagnostic Steps

### Step 1: Check Railway Logs

**Railway Dashboard → Your Service → Logs**

Look for:
```
✓ PostgreSQL connected
=== Vig v1 Starting ===
WINDOW 1
```

**If you see errors:**
- Database connection errors → Fix `DATABASE_URL`
- Bot not starting → Check environment variables
- Import errors → Check `requirements.txt`

### Step 2: Test Database Connection

**From your Mac:**
```bash
# Get DATABASE_URL from Railway → Variables
export DATABASE_URL="postgresql://..."

# Test connection
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
```

**Expected:**
- If fresh deployment: Both return `0` (empty database)
- If has data: Should show row counts

### Step 3: Check Bot Status

**Railway Logs should show:**
```
WINDOW 1
Scanning Polymarket for expiring markets...
```

**If no window activity:**
- Bot may not have run yet (wait 1 hour)
- Or bot crashed (check for errors)

### Step 4: Verify Environment Variables

**Railway Dashboard → Variables**

**Required:**
- ✅ `DATABASE_URL` (if using PostgreSQL)
- ✅ `DB_PATH` (if using SQLite volume)
- ✅ `POLYGON_PRIVATE_KEY` (for live mode)
- ✅ `PAPER_MODE` (set to `true` or `false`)

## Solutions by Scenario

### Scenario A: Fresh Deployment (Empty Database)

**This is normal!** The database is empty because:
- Bot hasn't run yet (takes ~1 hour for first scan)
- No windows/bets created yet

**What to do:**
1. ✅ Dashboard is working correctly
2. ⏳ Wait for bot to run first window (check logs)
3. ✅ Data will appear after first window completes

**To speed up testing:**
- Set `SCAN_INTERVAL_SECONDS=300` (5 minutes) temporarily
- Or use dashboard "Scan Now" button if available

### Scenario B: Database Connection Failed

**Dashboard can't connect to database.**

**Fix:**
1. Check `DATABASE_URL` in Railway → Variables
2. Verify PostgreSQL service is running
3. Test connection manually
4. Check logs for connection errors

**If PostgreSQL keeps timing out:**
- Restart PostgreSQL service
- Upgrade to paid tier ($5/mo)
- Or switch to SQLite + persistent volume

### Scenario C: Bot Not Running

**Bot process crashed or not started.**

**Check logs for:**
- Python errors/tracebacks
- Missing environment variables
- Import errors

**Fix:**
- Review error messages
- Verify all required env vars set
- Check `requirements.txt` dependencies
- Railway will auto-restart (check if it keeps crashing)

### Scenario D: Data Exists But Not Showing

**Database has data but dashboard shows empty.**

**Check:**
1. Dashboard and bot using same database?
2. Database queries working? (test manually)
3. API endpoints returning data? (check browser console)

**Fix:**
- Verify `DATABASE_URL` matches in both services
- Check dashboard API endpoints: `/api/stats`, `/api/bets`
- Review dashboard logs for query errors

## Quick Test Commands

### Test Dashboard API Directly

```bash
# Replace with your Railway URL
RAILWAY_URL="https://vig-production.up.railway.app"

# Test stats endpoint
curl "$RAILWAY_URL/api/stats"

# Test bets endpoint
curl "$RAILWAY_URL/api/bets?limit=10"

# Test windows endpoint
curl "$RAILWAY_URL/api/windows?limit=10"
```

**Expected:**
- If empty: `{"bets": [], "windows": []}` or empty arrays
- If has data: JSON with bet/window objects

### Test Database Directly

```bash
# PostgreSQL
psql "$DATABASE_URL" << EOF
SELECT 'windows' as table_name, COUNT(*) FROM windows
UNION ALL
SELECT 'bets', COUNT(*) FROM bets
UNION ALL
SELECT 'circuit_breaker_log', COUNT(*) FROM circuit_breaker_log;
EOF
```

**Expected:**
- Fresh deployment: All counts = 0
- After bot runs: Counts > 0

## Most Likely Cause: Fresh Database

**If this is a fresh Railway deployment, the database is empty because:**

1. ✅ Dashboard deployed successfully
2. ✅ Database connection working
3. ✅ Bot deployed successfully
4. ⏳ Bot hasn't run first window yet (takes ~1 hour)

**This is normal!** The bot runs on a schedule (default: every hour). After the first window completes, you'll see:
- Window records in dashboard
- Bets placed (if markets qualify)
- Statistics updating

## What to Do Now

1. ✅ **Verify bot is running** - Check Railway logs for "Vig v1 Starting"
2. ⏳ **Wait for first window** - Default scan interval is 1 hour
3. 📊 **Check logs** - Should see "WINDOW 1" after first scan
4. 🔍 **Monitor dashboard** - Data will appear after first window

**To speed up testing:**
- Temporarily set `SCAN_INTERVAL_SECONDS=300` (5 minutes)
- Or manually trigger scan if dashboard has button

## Expected Timeline

| Time | What Happens |
|------|--------------|
| **0 min** | Deployment completes |
| **0-5 min** | Bot starts, connects to database |
| **~60 min** | First scan cycle runs |
| **~61 min** | First window created (if markets found) |
| **~62 min** | Dashboard shows first window/bets |

**If you want faster testing, reduce `SCAN_INTERVAL_SECONDS` temporarily.**
