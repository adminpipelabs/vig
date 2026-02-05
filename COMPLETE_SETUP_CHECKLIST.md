# Complete Setup Checklist

## ✅ What's Done

- [x] Code pushed to GitHub
- [x] Railway deployed dashboard
- [x] PostgreSQL support added to code
- [x] Migration script created
- [x] Redemption logic working

## 🔧 What You Need to Do

### Step 1: Get DATABASE_URL from Railway ✅ (You said "done")

1. Railway → `vig-production` project
2. Click PostgreSQL service
3. Variables tab
4. Copy `DATABASE_URL`

### Step 2: Set DATABASE_URL on Railway Dashboard

1. Go to **Dashboard service** (not PostgreSQL)
2. **Variables** tab
3. **+ New Variable**
4. Name: `DATABASE_URL`
5. Value: Paste the DATABASE_URL
6. Railway will auto-restart

### Step 3: Set DATABASE_URL Locally

**Add to `.env` file:**
```bash
DATABASE_URL=postgresql://postgres:password@host:port/railway
```

**Or tell me the DATABASE_URL and I'll add it for you!**

### Step 4: Install Driver & Migrate

```bash
cd /Users/mikaelo/vig
pip3.11 install psycopg2-binary
python3.11 migrate_to_postgres.py
```

### Step 5: Start Bot

```bash
python3.11 main.py
```

## Current Status Check

Run this to check status:
```bash
cd /Users/mikaelo/vig
python3.11 -c "
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv('DATABASE_URL')
if db_url:
    print('✅ DATABASE_URL is set')
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        print('✅ PostgreSQL connection works!')
        conn.close()
    except Exception as e:
        print(f'❌ Connection error: {e}')
else:
    print('⚠️  DATABASE_URL not set')
"
```

## Next Steps

Once DATABASE_URL is set:
1. ✅ Dashboard will connect automatically (on Railway)
2. ✅ Bot will use PostgreSQL (when you start it)
3. ✅ Both will share same database
4. ✅ Ready for 24/7 operation!

**Share the DATABASE_URL and I'll help you set it up!** 🚀
