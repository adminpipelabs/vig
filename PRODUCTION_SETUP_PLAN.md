# Production Setup Plan - PostgreSQL Migration

## Target Architecture

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

## Why This Setup?

1. **Bot on VPS with Residential IP:**
   - ✅ 24/7 uptime (no sleep issues)
   - ✅ Bypasses Cloudflare (residential IP)
   - ✅ Can handle 1000+ bets/day
   - ✅ Production-ready

2. **PostgreSQL on Railway:**
   - ✅ Shared database (bot writes, dashboard reads)
   - ✅ Reliable, scalable
   - ✅ Dashboard accessible 24/7
   - ✅ No file sync issues

3. **Dashboard on Railway:**
   - ✅ Already deployed
   - ✅ Accessible from anywhere
   - ✅ Reads from PostgreSQL

## Migration Steps

### Phase 1: Set Up PostgreSQL on Railway

1. **Create PostgreSQL database on Railway:**
   - Go to Railway dashboard
   - Add new service → PostgreSQL
   - Copy connection string

2. **Get connection details:**
   - `DATABASE_URL` from Railway
   - Format: `postgresql://user:pass@host:port/dbname`

### Phase 2: Update Code for PostgreSQL

**Files to modify:**
- `db.py` - Change from SQLite to PostgreSQL
- `config.py` - Add `DATABASE_URL` environment variable
- `dashboard.py` - Update database connection

**Libraries needed:**
- `psycopg2` or `psycopg2-binary` (PostgreSQL adapter)

### Phase 3: Migrate Existing Data

**Export from SQLite:**
```bash
sqlite3 vig.db .dump > backup.sql
```

**Import to PostgreSQL:**
- Convert SQLite schema to PostgreSQL
- Import data

### Phase 4: Deploy Bot to VPS

**VPS Requirements:**
- Residential IP (not datacenter)
- Python 3.11+
- 24/7 uptime

**Providers to check:**
- Contabo (some regions have residential IPs)
- Vultr (check IP type)
- Or use residential proxy service

## Implementation Plan

### Step 1: PostgreSQL Setup (Today)
- [ ] Create PostgreSQL on Railway
- [ ] Get connection string
- [ ] Test connection

### Step 2: Code Migration (Today)
- [ ] Update `db.py` for PostgreSQL
- [ ] Update `config.py` for `DATABASE_URL`
- [ ] Update `dashboard.py` for PostgreSQL
- [ ] Test locally with PostgreSQL

### Step 3: Data Migration (Today)
- [ ] Export SQLite data
- [ ] Convert schema
- [ ] Import to PostgreSQL
- [ ] Verify data integrity

### Step 4: Deploy (This Week)
- [ ] Find VPS with residential IP
- [ ] Deploy bot to VPS
- [ ] Update dashboard on Railway
- [ ] Test end-to-end

## Current Status

**What works:**
- ✅ Bot logic (betting, settlement, redemption)
- ✅ Dashboard UI
- ✅ Database schema

**What needs work:**
- ⚠️ Database connection (SQLite → PostgreSQL)
- ⚠️ Bot deployment (local → VPS)
- ⚠️ 24/7 infrastructure

## Next Steps

1. **I'll help you:**
   - Create PostgreSQL migration code
   - Update `db.py` for PostgreSQL
   - Update `dashboard.py` for PostgreSQL
   - Create migration script

2. **You'll need to:**
   - Create PostgreSQL on Railway
   - Get connection string
   - Find VPS with residential IP (or we can test with local first)

Ready to start the migration?
