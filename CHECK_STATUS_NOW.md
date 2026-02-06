# Quick Status Check - Dashboard Shows "No Data"

## Current Situation

**Dashboard:** https://vig-production.up.railway.app/  
**Status:** Shows "No data"  
**Last Updated:** 1:39:52 PM (dashboard is refreshing)

## What This Means

The dashboard is **working correctly** but showing no data because:

1. ✅ Dashboard is running (updates every minute)
2. ✅ Database connection is working
3. ⚠️ Database is empty (no windows/bets yet)

## Immediate Checks Needed

### 1. Is Bot Running?

**Check Railway Logs:**
- Railway Dashboard → Your Service → Logs
- Look for: `=== Vig v1 Starting ===`
- Look for: `WINDOW 1` or `Scanning Polymarket...`

**If you see bot activity:** ✅ Bot is running, just waiting for data  
**If you DON'T see bot activity:** ❌ Bot may not be running

### 2. Check Database

**From your Mac:**
```bash
# Get DATABASE_URL from Railway → Variables
export DATABASE_URL="postgresql://..."

# Check if database has any data
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
```

**Expected:**
- `0` = Empty database (normal for fresh deployment)
- `> 0` = Has data (should show in dashboard)

### 3. Test Dashboard API

**Open browser console** (F12) on dashboard page, or:

```bash
curl https://vig-production.up.railway.app/api/stats
curl https://vig-production.up.railway.app/api/bets
curl https://vig-production.up.railway.app/api/windows
```

**What you'll see:**
- Empty: `[]` or `{"bets": [], "windows": []}`
- Has data: JSON objects with bet/window data

## Most Likely Scenarios

### Scenario A: Bot Not Running Yet ⏳

**What's happening:**
- Dashboard deployed ✅
- Database empty ✅
- Bot hasn't started first scan yet ⏳

**What to do:**
- Check Railway logs for bot startup
- Wait for first scan cycle (~1 hour default)
- Or reduce `SCAN_INTERVAL_SECONDS` to test faster

### Scenario B: Bot Running But No Markets Found ✅

**What's happening:**
- Bot is scanning ✅
- No markets qualify (price/expiry filters) ✅
- No windows created (normal if no markets)

**What to do:**
- Check logs for "No qualifying markets found"
- Adjust `MIN_FAVORITE_PRICE` / `MAX_FAVORITE_PRICE` if too restrictive
- Check `EXPIRY_WINDOW_MINUTES` setting

### Scenario C: Database Connection Issue ❌

**What's happening:**
- Dashboard can't read database
- Shows empty even if data exists

**What to do:**
- Check Railway logs for database errors
- Verify `DATABASE_URL` is set correctly
- Test database connection manually

## Quick Actions

### Action 1: Check Railway Logs Right Now

**Go to:** Railway Dashboard → Your Service → Logs

**Look for:**
```
✓ PostgreSQL connected
=== Vig v1 Starting ===
WINDOW 1
Scanning Polymarket...
```

**Share what you see** - this will tell us exactly what's happening.

### Action 2: Speed Up Testing (Optional)

**To see data faster, temporarily reduce scan interval:**

Railway Dashboard → Variables → Add/Edit:
```
SCAN_INTERVAL_SECONDS=300
```

This makes bot scan every 5 minutes instead of 1 hour.

### Action 3: Verify Environment Variables

**Railway Dashboard → Variables**

**Check these are set:**
- ✅ `DATABASE_URL` (if using PostgreSQL)
- ✅ `POLYGON_PRIVATE_KEY` (for live mode)
- ✅ `PAPER_MODE` (should be `true` or `false`)
- ✅ `RESIDENTIAL_PROXY_URL` (if using proxy)

## What to Do Next

1. **Check Railway logs** - See if bot is running
2. **Share log output** - So we can diagnose
3. **Wait or speed up** - Either wait ~1 hour or reduce scan interval
4. **Monitor dashboard** - Data will appear after first window

## Expected Timeline

| Time | What Should Happen |
|------|---------------------|
| **Now** | Dashboard shows "No data" (normal) |
| **~60 min** | Bot runs first scan |
| **~61 min** | First window created (if markets found) |
| **~62 min** | Dashboard shows data |

**If after 2 hours still no data:**
- Check logs for errors
- Verify bot is running
- Test database connection
- Check environment variables
