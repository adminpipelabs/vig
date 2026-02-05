# Next Steps: Complete PostgreSQL Setup on Railway

## ✅ What's Done

- ✅ Code pushed to GitHub
- ✅ Railway auto-deployed dashboard
- ✅ PostgreSQL support added to code
- ✅ `psycopg2-binary` added to requirements.txt

## 🔧 What You Need to Do Now

### Step 1: Create PostgreSQL Database on Railway

1. Go to Railway: https://railway.app
2. Open your `vig-production` project
3. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
4. Wait ~30 seconds for provisioning
5. Click on the PostgreSQL service
6. Go to **"Variables"** tab
7. Copy the **`DATABASE_URL`** value
   - Format: `postgresql://postgres:password@host:port/railway`

### Step 2: Set DATABASE_URL on Railway Dashboard

1. Go to your **Dashboard service** (not PostgreSQL)
2. Click **"Variables"** tab
3. Click **"+ New Variable"**
4. Name: `DATABASE_URL`
5. Value: Paste the `DATABASE_URL` from PostgreSQL service
6. Click **"Add"**
7. Railway will auto-restart the dashboard

### Step 3: Migrate Data (Optional - if you want existing data)

**On your local machine:**
```bash
cd /Users/mikaelo/vig

# Add DATABASE_URL to .env (temporarily for migration)
echo "DATABASE_URL=postgresql://postgres:password@host:port/railway" >> .env
# (Replace with actual DATABASE_URL from Railway)

# Install driver
pip install psycopg2-binary

# Run migration
python3.11 migrate_to_postgres.py
```

### Step 4: Verify Dashboard Works

1. Go to: https://vig-production.up.railway.app/
2. Dashboard should now connect to PostgreSQL
3. If you migrated data, you should see your bets/windows
4. If no data migrated, dashboard will be empty (ready for new bets)

## 🎯 Current Architecture

```
┌─────────────────┐         ┌──────────────────┐
│  Bot (Local)    │────────▶│  PostgreSQL DB   │◀────────┐
│  For now        │         │  (Railway)       │         │
└─────────────────┘         └──────────────────┘         │
                                                           │
┌─────────────────┐                                       │
│  Dashboard      │───────────────────────────────────────┘
│  (Railway)      │
│  Connected! ✅  │
└─────────────────┘
```

## ✅ Checklist

- [ ] PostgreSQL database created on Railway
- [ ] `DATABASE_URL` copied from PostgreSQL service
- [ ] `DATABASE_URL` set on Dashboard service
- [ ] Dashboard restarted (automatic)
- [ ] Dashboard accessible at https://vig-production.up.railway.app/
- [ ] (Optional) Data migrated from SQLite

## 🚀 After Setup

**Bot will:**
- Connect to PostgreSQL when `DATABASE_URL` is set locally
- Write all bets/windows to PostgreSQL
- Dashboard will show data in real-time

**Dashboard will:**
- Read from PostgreSQL
- Show all data from bot
- Accessible 24/7 on Railway

## 🔍 Troubleshooting

**Dashboard shows empty:**
- Check `DATABASE_URL` is set on Railway dashboard service
- Check Railway logs for connection errors
- Verify PostgreSQL is running

**Bot can't connect:**
- Make sure `DATABASE_URL` is in local `.env` file
- Run: `pip install psycopg2-binary`
- Check connection string format

**Migration fails:**
- Verify `DATABASE_URL` is correct
- Check PostgreSQL is accessible
- Backup SQLite first: `cp vig.db vig.db.backup`

## Next: Deploy Bot to VPS

Once PostgreSQL is working:
1. Find VPS with residential IP
2. Deploy bot to VPS
3. Set `DATABASE_URL` on VPS
4. Bot runs 24/7, dashboard stays on Railway
5. Scale to 1000+ bets/day! 🚀
