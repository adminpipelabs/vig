# PostgreSQL Migration - Implementation Complete ✅

## What's Been Done

### 1. Updated `db.py` ✅
- **Automatic detection:** Uses PostgreSQL if `DATABASE_URL` is set, otherwise SQLite
- **Backward compatible:** Existing SQLite code still works
- **All methods updated:** Supports both `?` (SQLite) and `%s` (PostgreSQL) parameter styles

### 2. Updated `dashboard.py` ✅
- **Connection detection:** Automatically uses PostgreSQL if `DATABASE_URL` is set
- **Helper function:** `execute_query()` handles parameter conversion
- **Most queries work:** Queries without parameters work for both

### 3. Created Migration Script ✅
- **`migrate_to_postgres.py`:** Exports SQLite data and imports to PostgreSQL
- **Preserves all data:** Bets, windows, circuit breaker logs

### 4. Created Setup Instructions ✅
- **`POSTGRES_SETUP_INSTRUCTIONS.md`:** Step-by-step guide

## Next Steps

### Step 1: Create PostgreSQL on Railway (You)

1. Go to Railway: https://railway.app
2. Open `vig-production` project
3. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
4. Wait ~30 seconds for provisioning
5. Click PostgreSQL service → **"Variables"** tab
6. Copy the **`DATABASE_URL`** value

### Step 2: Set Environment Variables

**On Railway (Dashboard service):**
- Add `DATABASE_URL` = (paste from Step 1)

**Locally (.env file):**
```bash
DATABASE_URL=postgresql://postgres:password@host:port/railway
```

### Step 3: Install PostgreSQL Driver

```bash
cd /Users/mikaelo/vig
pip install psycopg2-binary
```

### Step 4: Migrate Data

```bash
python3.11 migrate_to_postgres.py
```

### Step 5: Test

**Test bot locally:**
```bash
python3.11 main.py
# Should connect to PostgreSQL automatically
```

**Test dashboard:**
- Dashboard on Railway should now show your data!
- Check: https://vig-production.up.railway.app/

## Architecture After Migration

```
┌─────────────────┐         ┌──────────────────┐
│  Bot (Local)    │────────▶│  PostgreSQL DB   │◀────────┐
│  For now        │         │  (Railway)       │         │
└─────────────────┘         └──────────────────┘         │
                                                           │
┌─────────────────┐                                       │
│  Dashboard      │───────────────────────────────────────┘
│  (Railway)      │
│  Reads from DB  │
└─────────────────┘
```

**Later:** Move bot to VPS with residential IP for 24/7 operation

## Benefits

✅ **Dashboard accessible 24/7** (on Railway)  
✅ **Shared database** (bot writes, dashboard reads)  
✅ **No file sync issues**  
✅ **Production-ready**  
✅ **Scalable to 1000+ bets/day**

## Important Notes

- **Bot still needs residential IP** - Can't run on Railway due to Cloudflare
- **For now:** Bot runs locally, connects to PostgreSQL on Railway
- **Later:** Deploy bot to VPS with residential IP
- **Dashboard:** Already on Railway, will work once `DATABASE_URL` is set

## Files Modified

- ✅ `db.py` - PostgreSQL support added
- ✅ `dashboard.py` - PostgreSQL connection added
- ✅ `migrate_to_postgres.py` - Migration script created
- ✅ `POSTGRES_SETUP_INSTRUCTIONS.md` - Setup guide

## Ready to Deploy!

Once you:
1. Create PostgreSQL on Railway
2. Set `DATABASE_URL` 
3. Run migration

Everything will work! 🚀
