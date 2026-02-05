# Setup PostgreSQL Now - Step by Step

## Current Status
- ✅ Bot code ready for PostgreSQL
- ✅ Dashboard code ready for PostgreSQL  
- ✅ Migration script ready
- ⚠️  PostgreSQL database needs to be created
- ⚠️  DATABASE_URL needs to be set

## Step-by-Step Setup

### Step 1: Create PostgreSQL on Railway (2 minutes)

1. **Go to Railway:** https://railway.app
2. **Open project:** `vig-production`
3. **Click:** "+ New" button
4. **Select:** "Database" → "Add PostgreSQL"
5. **Wait:** ~30 seconds for provisioning
6. **Click:** PostgreSQL service (newly created)
7. **Go to:** "Variables" tab
8. **Copy:** `DATABASE_URL` value
   - Format: `postgresql://postgres:password@host:port/railway`
   - **IMPORTANT:** Copy this entire string!

### Step 2: Set DATABASE_URL on Dashboard (1 minute)

1. **Go back to:** Dashboard service (not PostgreSQL)
2. **Click:** "Variables" tab
3. **Click:** "+ New Variable"
4. **Name:** `DATABASE_URL`
5. **Value:** Paste the `DATABASE_URL` from Step 1
6. **Click:** "Add"
7. **Railway will:** Auto-restart dashboard

### Step 3: Set DATABASE_URL Locally (for bot) (1 minute)

**Add to `/Users/mikaelo/vig/.env`:**
```bash
DATABASE_URL=postgresql://postgres:password@host:port/railway
```
(Replace with actual DATABASE_URL from Railway)

### Step 4: Install PostgreSQL Driver (1 minute)

```bash
cd /Users/mikaelo/vig
pip install psycopg2-binary
```

### Step 5: Migrate Existing Data (2 minutes)

```bash
cd /Users/mikaelo/vig
python3.11 migrate_to_postgres.py
```

This will:
- Export all data from SQLite
- Import to PostgreSQL
- Verify migration

### Step 6: Restart Bot (if running)

If bot is running, restart it:
```bash
# Stop current bot (if running)
pkill -f "python.*main.py"

# Start bot (will now use PostgreSQL)
cd /Users/mikaelo/vig
python3.11 main.py
```

## Verification

### Check Dashboard:
- Go to: https://vig-production.up.railway.app/
- Should show your data from PostgreSQL

### Check Bot:
- Bot logs should show PostgreSQL connection
- New bets will be written to PostgreSQL
- Dashboard will show them in real-time

## Architecture After Setup

```
┌─────────────────┐         ┌──────────────────┐
│  Bot (Local)    │────────▶│  PostgreSQL DB   │◀────────┐
│  Writes data    │         │  (Railway)       │         │
└─────────────────┘         └──────────────────┘         │
                                                           │
┌─────────────────┐                                       │
│  Dashboard      │───────────────────────────────────────┘
│  (Railway)      │
│  Reads data     │
│  ✅ Connected!  │
└─────────────────┘
```

## Troubleshooting

**Dashboard shows empty:**
- Check `DATABASE_URL` is set on Railway dashboard service
- Check Railway logs for connection errors
- Restart dashboard service

**Bot can't connect:**
- Verify `DATABASE_URL` in `.env` file
- Run: `pip install psycopg2-binary`
- Check connection string format

**Migration fails:**
- Verify `DATABASE_URL` is correct
- Check PostgreSQL is running on Railway
- Backup SQLite first: `cp vig.db vig.db.backup`

## Ready to Go!

Once PostgreSQL is set up:
- ✅ Bot writes to PostgreSQL
- ✅ Dashboard reads from PostgreSQL  
- ✅ Both share same database
- ✅ Dashboard accessible 24/7
- ✅ Ready to scale!
