# Implementation Plan - Vig Bot Enhancements

## ✅ What We Can Do While Migration Runs

### 1. Set Railway Dashboard DATABASE_URL
**Status:** Ready to do now
- Railway Dashboard → Variables → Add `DATABASE_URL` (internal URL)
- This will fix "No data" issue once migration completes

### 2. Add Wallet Balance Display (Quick Win)
**Status:** Partially implemented - needs UI enhancement
- ✅ API endpoint exists (`/api/stats` returns `current_cash`)
- ✅ Balance calculation logic exists
- ⚠️ Need to add prominent wallet balance display in dashboard header

---

## Feature Implementation Priority

### Phase 1: Core Wallet Features (Week 1) 🚀

#### 1.1 Wallet Balance Display ✅ (90% done)
**What exists:**
- Balance fetching from CLOB API
- Locked funds calculation from pending bets
- Displayed in stats API

**What to add:**
- Prominent wallet balance card in dashboard header
- Real-time balance updates
- Available vs Locked breakdown

**Files to modify:**
- `dashboard.py` - Add `/api/wallet/balance` endpoint (DONE ✅)
- `dashboard.py` - Update HTML to show balance prominently
- Add auto-refresh for balance

**Estimated time:** 30 minutes

---

#### 1.2 Multi-Wallet Support 🔄
**What to add:**
- Wallet management table in DB
- Wallet selection/switching
- Per-wallet stats

**Database schema:**
```sql
CREATE TABLE wallets (
    id SERIAL PRIMARY KEY,
    name TEXT,
    address TEXT UNIQUE,
    private_key_encrypted TEXT,  -- Encrypted!
    active BOOLEAN DEFAULT TRUE,
    created_at TEXT
);
```

**API endpoints:**
- `POST /api/wallet/add` - Add wallet
- `GET /api/wallet/list` - List wallets
- `POST /api/wallet/{id}/activate` - Switch active wallet
- `GET /api/wallet/{id}/balance` - Get wallet balance

**Files to create/modify:**
- `db.py` - Add wallet table creation
- `dashboard.py` - Add wallet management endpoints
- `config.py` - Support wallet selection
- `main.py` - Use selected wallet

**Estimated time:** 2-3 hours

---

### Phase 2: Bot Management (Week 2)

#### 2.1 Multi-Bot Support
**Database schema:**
```sql
CREATE TABLE bots (
    id SERIAL PRIMARY KEY,
    name TEXT,
    wallet_id INTEGER REFERENCES wallets(id),
    config_json TEXT,  -- JSON config
    status TEXT DEFAULT 'stopped',  -- running, stopped, paused
    created_at TEXT,
    updated_at TEXT
);
```

**API endpoints:**
- `POST /api/bot/create` - Create bot
- `GET /api/bot/list` - List bots
- `POST /api/bot/{id}/start` - Start bot
- `POST /api/bot/{id}/stop` - Stop bot
- `GET /api/bot/{id}/stats` - Bot stats

**Estimated time:** 4-5 hours

---

#### 2.2 Bot Configuration Editor
**Features:**
- Edit bot parameters via UI
- Config presets
- Real-time updates

**API endpoints:**
- `GET /api/bot/{id}/config` - Get config
- `PUT /api/bot/{id}/config` - Update config
- `GET /api/bot/config/presets` - Get preset configs

**Estimated time:** 3-4 hours

---

### Phase 3: Market Features (Week 3)

#### 3.1 Market Browser/Listing
**Features:**
- Browse Polymarket markets
- Filter by category, expiry, volume
- Market details view

**API endpoints:**
- `GET /api/markets/list` - List markets with filters
- `GET /api/markets/{id}` - Market details
- `GET /api/markets/categories` - Get categories

**Implementation:**
- Use Polymarket Gamma API
- Cache market data
- Add market browser UI

**Estimated time:** 4-5 hours

---

#### 3.2 Category-Based Scanning
**Features:**
- Scan specific categories
- Category filters in scanner
- Category performance tracking

**Database schema:**
```sql
ALTER TABLE bets ADD COLUMN category TEXT;
ALTER TABLE markets ADD COLUMN category TEXT;
```

**Files to modify:**
- `scanner.py` - Add category filter
- `config.py` - Add category config
- `dashboard.py` - Category stats

**Estimated time:** 2-3 hours

---

#### 3.3 Time-Based Scanning
**Features:**
- Filter by market creation time
- Filter by expiry time
- Scheduled scans

**Files to modify:**
- `scanner.py` - Add time filters
- `config.py` - Add time-based config
- `main.py` - Scheduled scans

**Estimated time:** 2-3 hours

---

## Quick Wins (Do Now)

### 1. Add Wallet Balance to Dashboard Header ⏱️ 15 min
**Update dashboard HTML to show:**
```html
<div class="wallet-balance">
  <div>Available: $X.XX</div>
  <div>Locked: $X.XX</div>
  <div>Total: $X.XX</div>
</div>
```

### 2. Set Railway DATABASE_URL ⏱️ 2 min
- Railway Dashboard → Variables
- Add: `DATABASE_URL=postgresql://postgres:...@postgres.railway.internal:5432/railway`

### 3. Add Balance Auto-Refresh ⏱️ 10 min
- Add JavaScript to refresh balance every 30 seconds
- Update dashboard balance display

---

## Implementation Order

**Today (while migration runs):**
1. ✅ Set Railway DATABASE_URL
2. ✅ Add wallet balance endpoint
3. ⏳ Add wallet balance to dashboard UI
4. ⏳ Add balance auto-refresh

**This Week:**
5. Multi-wallet support
6. Market browser

**Next Week:**
7. Multi-bot management
8. Bot config editor

**Following Week:**
9. Category scanning
10. Time-based scanning

---

## Technical Notes

### Security
- **Private keys:** Must be encrypted at rest
- Use `cryptography` library for encryption
- Never log private keys
- API authentication for wallet management

### Database Migrations
- Create migration scripts for schema changes
- Test migrations on dev database first
- Backup before migrations

### API Design
- RESTful endpoints
- JSON responses
- Error handling
- Rate limiting

---

## Next Steps

1. **Right now:** Set Railway DATABASE_URL
2. **Next:** Add wallet balance display to dashboard
3. **Then:** Start Phase 1 features
