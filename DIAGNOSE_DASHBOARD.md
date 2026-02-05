# Dashboard Diagnosis - What's Happening

## Current Status

**Dashboard URL:** https://vig-production.up.railway.app/  
**Status:** ✅ Dashboard loads  
**Issue:** ⚠️ Shows no data (empty)

## What This Means

### Most Likely: Fresh Database (Normal)

**The dashboard is working correctly, but the database is empty because:**

1. ✅ **Deployment successful** - Dashboard is accessible
2. ✅ **Database connection working** - No connection errors
3. ⏳ **Bot hasn't run yet** - Takes ~1 hour for first scan cycle
4. 📊 **No data to show** - Database is empty (expected for fresh deployment)

**This is normal!** The bot runs on a schedule (default: every hour). After the first window completes, data will appear.

### Timeline

| Time | What's Happening |
|------|------------------|
| **Now** | Dashboard deployed, database empty |
| **~60 min** | Bot runs first scan cycle |
| **~61 min** | First window created (if markets found) |
| **~62 min** | Dashboard shows data |

## How to Verify What's Happening

### Step 1: Check Railway Logs

**Railway Dashboard → Your Service → Logs**

**Look for these messages:**

✅ **Good signs:**
```
✓ PostgreSQL connected (or SQLite)
=== Vig v1 Starting (PAPER/LIVE mode) ===
📂 Reading from SQLite: vig.db (or PostgreSQL)
```

❌ **Problems:**
```
Failed to init CLOB client
DATABASE_URL not found
Connection timeout
```

### Step 2: Check if Bot is Running

**In Railway logs, look for:**
```
WINDOW 1
Scanning Polymarket for expiring markets...
```

**If you see this:** Bot is running, just waiting for first scan cycle.

**If you DON'T see this:** Bot may not be running (check for errors).

### Step 3: Test Database Connection

**From your Mac:**
```bash
# Get DATABASE_URL from Railway → Variables
export DATABASE_URL="postgresql://..."

# Check if database has data
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
```

**Expected results:**
- Fresh deployment: Both return `0` (empty - this is normal!)
- After bot runs: Counts > 0

### Step 4: Test Dashboard API

**Open browser console** (F12) on dashboard page, or test directly:

```bash
curl https://vig-production.up.railway.app/api/stats
curl https://vig-production.up.railway.app/api/bets
curl https://vig-production.up.railway.app/api/windows
```

**Expected:**
- Empty database: `{"bets": [], "windows": []}` or empty arrays
- Has data: JSON objects with bet/window data

## Possible Scenarios

### Scenario 1: Fresh Deployment (Most Likely) ✅

**What's happening:**
- Dashboard deployed successfully
- Database is empty (fresh start)
- Bot is running but hasn't completed first window yet

**What to do:**
- ✅ Everything is working correctly
- ⏳ Wait ~1 hour for first scan cycle
- 📊 Data will appear after first window

**To speed up:** Set `SCAN_INTERVAL_SECONDS=300` (5 minutes) temporarily

### Scenario 2: Bot Not Running ❌

**What's happening:**
- Dashboard works
- Database empty
- Bot process crashed or not started

**How to check:**
- Railway logs show errors
- No "Vig v1 Starting" message
- No window activity

**What to do:**
- Check logs for errors
- Verify environment variables
- Check if bot process is running

### Scenario 3: Database Connection Issue ❌

**What's happening:**
- Dashboard can't read from database
- Shows empty even if data exists

**How to check:**
- Railway logs show database errors
- API endpoints return errors
- Database queries fail

**What to do:**
- Verify `DATABASE_URL` is set correctly
- Test database connection manually
- Check PostgreSQL service status

### Scenario 4: Wrong Database ❌

**What's happening:**
- Bot writing to one database
- Dashboard reading from different database

**How to check:**
- Compare `DATABASE_URL` values
- Check if bot and dashboard use same database

**What to do:**
- Ensure both use same `DATABASE_URL`
- Verify database path matches

## Quick Diagnostic Commands

### Check Railway Service Status

```bash
# If Railway CLI installed
railway status
railway logs
```

### Test Database

```bash
# PostgreSQL
psql "$DATABASE_URL" << EOF
SELECT 'windows' as table, COUNT(*) FROM windows
UNION ALL
SELECT 'bets', COUNT(*) FROM bets;
EOF
```

### Test Dashboard API

```bash
RAILWAY_URL="https://vig-production.up.railway.app"

# Test endpoints
curl "$RAILWAY_URL/api/stats" | jq
curl "$RAILWAY_URL/api/bets?limit=5" | jq
curl "$RAILWAY_URL/api/windows?limit=5" | jq
```

## Most Likely Answer

**Based on the dashboard loading successfully:**

✅ **Dashboard is working**  
✅ **Database connection is working**  
✅ **Bot is likely running**  
⏳ **Just waiting for first data** (takes ~1 hour)

**This is normal for a fresh deployment!**

## What to Do Now

1. ✅ **Check Railway logs** - Verify bot is running
2. ⏳ **Wait for first window** - Default: 1 hour
3. 📊 **Monitor dashboard** - Data will appear automatically
4. 🔍 **Or speed up testing** - Set `SCAN_INTERVAL_SECONDS=300` (5 min)

## Expected Next Steps

1. **Within 1 hour:** Bot runs first scan
2. **If markets found:** Bot places bets, creates window
3. **Dashboard updates:** Shows first window/bets
4. **Continuous:** Bot runs every hour, dashboard updates

**If after 2 hours still no data:**
- Check Railway logs for errors
- Verify bot is running
- Test database connection
- Check environment variables
