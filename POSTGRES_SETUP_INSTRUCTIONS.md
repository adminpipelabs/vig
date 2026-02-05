# PostgreSQL Setup Instructions

## Step 1: Create PostgreSQL Database on Railway

1. Go to Railway dashboard: https://railway.app
2. Open your `vig-production` project
3. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
4. Wait for it to provision (~30 seconds)
5. Click on the PostgreSQL service
6. Go to **"Variables"** tab
7. Copy the **`DATABASE_URL`** value
   - Format: `postgresql://postgres:password@host:port/railway`

## Step 2: Set Environment Variables

### On Railway (Dashboard):
1. Go to your dashboard service
2. **Variables** tab
3. Add: `DATABASE_URL` = (paste the PostgreSQL URL from Step 1)

### Locally (for bot):
Add to `/Users/mikaelo/vig/.env`:
```bash
DATABASE_URL=postgresql://postgres:password@host:port/railway
```

## Step 3: Install PostgreSQL Driver

```bash
cd /Users/mikaelo/vig
pip install psycopg2-binary
```

## Step 4: Migrate Data

```bash
python3.11 migrate_to_postgres.py
```

This will:
- Export all data from SQLite (`vig.db`)
- Import to PostgreSQL
- Verify migration

## Step 5: Update Code

The code is already set up to use PostgreSQL automatically when `DATABASE_URL` is set!

**How it works:**
- If `DATABASE_URL` exists → uses PostgreSQL
- If not → falls back to SQLite (backward compatible)

**Files updated:**
- `db.py` - Now supports both SQLite and PostgreSQL
- `dashboard.py` - Will use PostgreSQL if `DATABASE_URL` is set
- `main.py` - Uses `db.py` which handles both

## Step 6: Test

### Test Bot Locally:
```bash
# Make sure DATABASE_URL is in .env
python3.11 main.py
```

### Test Dashboard on Railway:
1. Dashboard should automatically use PostgreSQL
2. Check: https://vig-production.up.railway.app/
3. Should show your data!

## Step 7: Deploy Bot to VPS

Once PostgreSQL is working:

1. **Find VPS with residential IP**
   - Contabo, Vultr, or similar
   - Check IP type before buying

2. **Deploy bot:**
   ```bash
   # On VPS
   git clone https://github.com/adminpipelabs/vig.git
   cd vig
   pip install -r requirements.txt psycopg2-binary
   # Set DATABASE_URL in .env
   python3.11 main.py
   ```

3. **Run 24/7:**
   ```bash
   # Use systemd or screen/tmux
   screen -S vig
   python3.11 main.py
   # Ctrl+A+D to detach
   ```

## Architecture After Migration

```
┌─────────────────┐         ┌──────────────────┐
│  Bot (VPS)      │────────▶│  PostgreSQL DB   │◀────────┐
│  Residential IP │         │  (Railway)       │         │
│  Runs 24/7      │         │  Shared Database │         │
└─────────────────┘         └──────────────────┘         │
                                                           │
┌─────────────────┐                                       │
│  Dashboard      │───────────────────────────────────────┘
│  (Railway)      │
│  Reads from DB  │
└─────────────────┘
```

## Troubleshooting

**Connection errors:**
- Check `DATABASE_URL` format
- Verify Railway PostgreSQL is running
- Check firewall/network access

**Migration issues:**
- Backup SQLite first: `cp vig.db vig.db.backup`
- Check data counts match
- Verify schema created correctly

**Dashboard shows empty:**
- Check Railway dashboard has `DATABASE_URL` set
- Restart Railway service
- Check logs for connection errors

## Next Steps After Migration

1. ✅ Test bot locally with PostgreSQL
2. ✅ Verify dashboard shows data
3. ✅ Find VPS with residential IP
4. ✅ Deploy bot to VPS
5. ✅ Scale to 1000+ bets/day!
