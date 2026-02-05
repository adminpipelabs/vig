# Quick Start: PostgreSQL Migration

## TL;DR

1. **Create PostgreSQL on Railway** → Get `DATABASE_URL`
2. **Set `DATABASE_URL`** in Railway dashboard + local `.env`
3. **Install driver:** `pip install psycopg2-binary`
4. **Migrate data:** `python3.11 migrate_to_postgres.py`
5. **Done!** Bot and dashboard now share PostgreSQL database

## Detailed Steps

### 1. Create PostgreSQL Database

**On Railway:**
1. Go to https://railway.app
2. Open `vig-production` project
3. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
4. Wait ~30 seconds
5. Click PostgreSQL service → **"Variables"** tab
6. Copy `DATABASE_URL` (format: `postgresql://postgres:pass@host:port/railway`)

### 2. Set Environment Variables

**Railway Dashboard Service:**
- Variables tab → Add `DATABASE_URL` = (paste from step 1)

**Local `.env` file:**
```bash
# Add this line:
DATABASE_URL=postgresql://postgres:password@host:port/railway
```

### 3. Install PostgreSQL Driver

```bash
cd /Users/mikaelo/vig
pip install psycopg2-binary
```

### 4. Migrate Existing Data

```bash
python3.11 migrate_to_postgres.py
```

This will:
- Export all data from SQLite (`vig.db`)
- Import to PostgreSQL
- Verify migration

### 5. Test

**Test bot:**
```bash
python3.11 main.py
# Should connect to PostgreSQL automatically
```

**Test dashboard:**
- Check https://vig-production.up.railway.app/
- Should now show your data!

## What Happens Next

**Current Setup:**
- ✅ Bot runs locally → Writes to PostgreSQL on Railway
- ✅ Dashboard on Railway → Reads from PostgreSQL on Railway
- ✅ Both share same database!

**Future (for 1000+ bets/day):**
- Bot moves to VPS with residential IP (24/7, bypasses Cloudflare)
- Still connects to PostgreSQL on Railway
- Dashboard stays on Railway
- Everything scales!

## Troubleshooting

**"psycopg2 not found":**
```bash
pip install psycopg2-binary
```

**"Connection refused":**
- Check `DATABASE_URL` format
- Verify PostgreSQL is running on Railway
- Check Railway logs

**Dashboard shows empty:**
- Make sure `DATABASE_URL` is set on Railway
- Restart Railway dashboard service
- Check Railway logs for errors

**Migration fails:**
- Backup SQLite first: `cp vig.db vig.db.backup`
- Check `DATABASE_URL` is correct
- Verify PostgreSQL is accessible

## Architecture

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
└─────────────────┘
```

## Benefits

✅ **Dashboard accessible 24/7** (on Railway)  
✅ **Shared database** (no file sync issues)  
✅ **Production-ready** (scalable)  
✅ **Backward compatible** (still works with SQLite if no DATABASE_URL)

## Next Steps After Migration

1. ✅ Test everything works
2. ✅ Find VPS with residential IP
3. ✅ Deploy bot to VPS for 24/7 operation
4. ✅ Scale to 1000+ bets/day!

Ready to migrate? Start with Step 1! 🚀
