# Railway Production Deployment Guide

**Date:** February 5, 2026  
**Status:** Ready for deployment

---

## Overview

This guide covers deploying Vig v1 to Railway with:
1. **Residential proxy** for CLOB API (bypasses Cloudflare blocking)
2. **PostgreSQL** for persistent data storage
3. **Both bot and dashboard** running in one Railway service

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Railway Project: Vig                            │
│                                                  │
│  ┌──────────────────────┐  ┌──────────────────┐ │
│  │  Vig Service          │  │  PostgreSQL      │ │
│  │  (Python)              │  │  (Railway addon)│ │
│  │                       │  │                  │ │
│  │  main.py (bot loop)   │──│  bets            │ │
│  │  dashboard.py (API)   │  │  windows         │ │
│  │                       │  │  circuit_breaker │ │
│  └───────┬───────────────┘  └──────────────────┘ │
│          │                                        │
│          │  CLOB API calls                        │
│          ▼                                        │
│  ┌──────────────────┐                            │
│  │ Residential Proxy │                            │
│  │ (Bright Data)     │                            │
│  └────────┬─────────┘                            │
│           │                                       │
└───────────┼───────────────────────────────────────┘
            ▼
   Polymarket CLOB API
   (sees residential IP → no Cloudflare block)
```

---

## Prerequisites

1. **Railway account** (free tier works, but paid PostgreSQL recommended)
2. **Residential proxy account** (Bright Data, SmartProxy, or similar)
3. **PostgreSQL service** on Railway (or use persistent volume + SQLite)

---

## Step 1: Set Up Residential Proxy

### 1.1 Sign Up for Proxy Service

**Recommended:** Bright Data (best Cloudflare bypass)
- Sign up: https://brightdata.com
- Free trial available
- Create a "Residential Proxy" zone

**Alternative:** SmartProxy, Oxylabs, IPRoyal

### 1.2 Get Proxy Credentials

From your proxy dashboard, get:
- Proxy host:port (e.g., `zproxy.lum-superproxy.io:22225`)
- Username:password (from your account)

**Format:** `http://username:password@host:port`

Example:
```
http://brd-customer-USERNAME-zone-ZONE:PASSWORD@zproxy.lum-superproxy.io:22225
```

### 1.3 Add to Railway Environment Variables

Railway Dashboard → Your Project → Variables → Add:

```
RESIDENTIAL_PROXY_URL=http://username:password@host:port
```

**Important:** Keep this secret! Railway encrypts env vars.

---

## Step 2: Set Up Database

### Option A: PostgreSQL (Recommended)

#### 2.1 Create PostgreSQL Service

1. Railway Dashboard → New → Database → Add PostgreSQL
2. Copy the `DATABASE_URL` (Railway sets this automatically)
3. Verify it's set: Railway → Variables → Check `DATABASE_URL`

#### 2.2 Test Connection

```bash
# From your local Mac (better connection)
psql "$DATABASE_URL" -c "SELECT 1;"
```

If this times out, try:
- Restart PostgreSQL service in Railway
- Upgrade to paid tier ($5/mo)
- Create a new PostgreSQL instance

#### 2.3 Run Migration

Once PostgreSQL is accessible:

```bash
# Set environment variables
export DATABASE_URL="postgresql://..."
export SQLITE_PATH=vig.db  # or path to your SQLite file

# Run migration
python3 migrate_to_postgres.py
```

Migration should complete in <5 minutes with batched inserts.

### Option B: SQLite on Persistent Volume (Fallback)

If PostgreSQL keeps timing out:

#### 2.1 Create Persistent Volume

1. Railway Dashboard → Vig Service → Settings → Volumes
2. Add volume, mount at `/data`
3. Set environment variable: `DB_PATH=/data/vig.db`

#### 2.2 Update Code

`db.py` already supports `DB_PATH` env var - no code changes needed!

**Note:** SQLite works fine for bot-only. If you add a dashboard that reads the same file, consider PostgreSQL for concurrent access.

---

## Step 3: Configure Railway Environment Variables

Railway Dashboard → Your Project → Variables → Add:

### Required Variables

```
# Trading
POLYGON_PRIVATE_KEY=your_private_key_here
PAPER_MODE=false  # Set to true for testing

# Proxy (for CLOB API)
RESIDENTIAL_PROXY_URL=http://username:password@host:port

# Database
DATABASE_URL=postgresql://...  # Auto-set by Railway if using PostgreSQL addon
# OR
DB_PATH=/data/vig.db  # If using persistent volume + SQLite

# Optional
SCAN_INTERVAL_SECONDS=3600
MIN_FAVORITE_PRICE=0.70
MAX_FAVORITE_PRICE=0.90
TELEGRAM_BOT_TOKEN=...  # For notifications
TELEGRAM_CHAT_ID=...
```

### Optional Configuration

See `config.py` for all available options.

---

## Step 4: Deploy to Railway

### 4.1 Connect Repository

1. Railway Dashboard → New Project → Deploy from GitHub
2. Select your `vig` repository
3. Railway will auto-detect `Procfile` or `railway.toml`

### 4.2 Verify Deployment Files

**Procfile** (created):
```
web: uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8000} & python3 main.py & wait
```

**railway.toml** (updated):
```toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8000} & python3 main.py & wait"
```

### 4.3 Deploy

Railway will:
1. Build from `requirements.txt`
2. Run `startCommand` from `railway.toml`
3. Start both dashboard (port 8000) and bot (background)

---

## Step 5: Verify Deployment

### 5.1 Check Logs

Railway Dashboard → Deployments → Latest → View Logs

Look for:
```
✓ PostgreSQL connected (or SQLite if using volume)
CLOB client initialized with residential proxy
=== Vig v1 Starting (LIVE mode) ===
```

### 5.2 Test Dashboard

Open Railway-provided URL (e.g., `https://vig-production.up.railway.app`)

Should show:
- Bot stats
- Recent bets
- Window history

### 5.3 Test Bot

Check logs for:
```
WINDOW 1
Scanning Polymarket for expiring markets...
Placing bets on X markets...
```

---

## Troubleshooting

### CLOB API Still Blocked?

1. **Verify proxy is set:**
   ```bash
   # In Railway logs, look for:
   "Using residential proxy for CLOB API"
   ```

2. **Test proxy manually:**
   ```bash
   curl -x http://username:password@host:port https://clob.polymarket.com/health
   ```

3. **Check proxy dashboard:** Verify traffic is flowing through proxy

### PostgreSQL Timeouts?

1. **Restart PostgreSQL service** in Railway
2. **Upgrade to paid tier** ($5/mo) - free tier has aggressive limits
3. **Check metrics:** Railway → PostgreSQL → Metrics tab
4. **Create new instance:** Sometimes a fresh instance performs better

### Bot Not Starting?

1. **Check logs** for error messages
2. **Verify env vars:** All required variables set?
3. **Check `PAPER_MODE`:** Set to `true` for testing (no CLOB needed)
4. **Verify `requirements.txt`:** All dependencies listed?

### Dashboard Not Accessible?

1. **Check Railway URL:** Should be auto-generated
2. **Verify port:** Railway sets `PORT` env var automatically
3. **Check healthcheck:** Railway → Settings → Healthcheck path should be `/`

---

## Monitoring

### Railway Dashboard

- **Metrics:** CPU, memory, network
- **Logs:** Real-time log streaming
- **Deployments:** Deployment history

### Bot Logs

Check Railway logs for:
- Window summaries
- Bet placements
- Settlement results
- Circuit breaker alerts

### Database

PostgreSQL:
```sql
-- Check recent bets
SELECT * FROM bets ORDER BY id DESC LIMIT 10;

-- Check windows
SELECT * FROM windows ORDER BY id DESC LIMIT 10;
```

SQLite (if using volume):
```bash
# SSH into Railway (if available) or use Railway CLI
sqlite3 /data/vig.db "SELECT * FROM bets ORDER BY id DESC LIMIT 10;"
```

---

## Cost Estimate

| Service | Cost |
|---------|------|
| Railway (Hobby) | $5/mo |
| PostgreSQL (Hobby) | $5/mo |
| Residential Proxy | ~$1-5/mo (depends on usage) |
| **Total** | **~$11-15/mo** |

**Bandwidth estimate:** ~500 KB/day through proxy = ~15 MB/month = pennies

---

## Next Steps

1. ✅ Deploy to Railway
2. ✅ Test with `PAPER_MODE=true` first
3. ✅ Verify proxy is working (check logs)
4. ✅ Switch to `PAPER_MODE=false` for live trading
5. ✅ Monitor first few windows
6. ✅ Set up Telegram notifications (optional)

---

## Files Created/Updated

- ✅ `clob_proxy.py` - Proxy wrapper for CLOB API
- ✅ `main.py` - Updated to use proxy
- ✅ `Procfile` - Railway process file
- ✅ `railway.toml` - Updated deployment config
- ✅ `RAILWAY_DEPLOYMENT_GUIDE.md` - This guide

---

## Support

If issues persist:
1. Check Railway logs
2. Verify all environment variables
3. Test proxy connection manually
4. Check PostgreSQL metrics
5. Review `migration.log` if migration failed
