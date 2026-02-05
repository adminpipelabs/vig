# Dashboard Connection Issue

## Problem

**Dashboard on Railway:** https://vig-production.up.railway.app/  
**Bot running:** Locally on Mac  
**Issue:** Dashboard shows "No windows yet", "No bets yet" - not connected

## Root Cause

The dashboard reads from SQLite database file (`vig.db`):
- **Local bot:** Creates/updates `vig.db` on your Mac
- **Railway dashboard:** Looks for `vig.db` on Railway's filesystem
- **Result:** Railway can't access your local database file → shows empty data

## Solutions

### Option 1: Run Dashboard Locally (Easiest)

**Run dashboard on same machine as bot:**

```bash
cd /Users/mikaelo/vig
python3.11 dashboard.py
```

Then access: `http://localhost:8000` (or whatever port it uses)

**Pros:**
- ✅ Works immediately
- ✅ Shares same database file
- ✅ No connection issues

**Cons:**
- ❌ Only accessible from your Mac
- ❌ Not accessible remotely

---

### Option 2: Shared Database (PostgreSQL on Railway)

**Move from SQLite to PostgreSQL:**

1. Create PostgreSQL database on Railway
2. Update bot to use PostgreSQL connection string
3. Update dashboard to use same PostgreSQL connection
4. Both connect to same database

**Pros:**
- ✅ Dashboard accessible 24/7 from anywhere
- ✅ Bot and dashboard share same data
- ✅ Production-ready

**Cons:**
- ⚠️ Requires code changes (SQLite → PostgreSQL)
- ⚠️ Need to migrate existing data

---

### Option 3: Bot Exposes API (More Complex)

**Make bot expose REST API:**

1. Bot runs locally, exposes API endpoint
2. Dashboard on Railway calls bot's API
3. Use ngrok/Tailscale to expose bot API

**Pros:**
- ✅ Dashboard accessible remotely
- ✅ Real-time data

**Cons:**
- ❌ Complex setup
- ❌ Requires network tunneling
- ❌ Bot must stay online

---

### Option 4: Sync Database File (Not Recommended)

**Sync `vig.db` file to Railway:**

- Use file sync service
- Or mount shared volume

**Pros:**
- ✅ Minimal code changes

**Cons:**
- ❌ File sync is unreliable
- ❌ Race conditions possible
- ❌ Not production-ready

---

## Recommendation

**For now:** Run dashboard locally alongside bot
- Both access same `vig.db` file
- Works immediately
- No changes needed

**Later:** Move to PostgreSQL on Railway
- Production-ready solution
- Dashboard accessible 24/7
- Requires migration but worth it

---

## Quick Fix: Run Dashboard Locally

```bash
# In terminal (same directory as bot)
cd /Users/mikaelo/vig
python3.11 dashboard.py

# Then open browser:
# http://localhost:8000
```

This will show real-time data from your local database.
