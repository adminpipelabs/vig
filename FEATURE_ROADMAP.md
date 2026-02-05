# Vig Bot Feature Roadmap

## Current Status
- ✅ Basic bot functionality (scan, bet, settle)
- ✅ PostgreSQL database migration
- ✅ Dashboard with basic stats
- ⏳ Migration in progress

## Proposed Features

### 1. 💰 Wallet Management
**Priority: HIGH**

**Features:**
- Display wallet balance (available funds)
- Show locked funds (in pending bets)
- Real-time balance updates
- Multiple wallet support
- Balance history/charts

**Implementation:**
- Add `/api/wallet/balance` endpoint
- Query CLOB API for cash balance
- Calculate locked funds from pending bets
- Display in dashboard header/sidebar

---

### 2. 🔐 Wallet Connection / Multi-Wallet Support
**Priority: HIGH**

**Features:**
- Connect wallet via private key
- Support multiple wallets
- Wallet switching
- Wallet-specific stats/P&L
- Wallet management UI

**Implementation:**
- Add wallet management table in DB
- Wallet selection in config
- Multi-wallet dashboard views
- Secure key storage (encrypted)

---

### 3. 🤖 Multi-Bot Management
**Priority: MEDIUM**

**Features:**
- Create multiple bot instances
- Different configs per bot
- Bot start/stop/pause
- Bot-specific dashboards
- Bot performance comparison

**Implementation:**
- Bot management API
- Bot config storage in DB
- Bot lifecycle management
- Multi-bot dashboard

---

### 4. ✏️ Bot Configuration Editor
**Priority: MEDIUM**

**Features:**
- Edit bot parameters via UI
- Real-time config updates
- Config presets/templates
- Config validation
- Config history/rollback

**Implementation:**
- Config editor UI component
- API endpoints for config updates
- Config validation logic
- Hot-reload capability

---

### 5. 📊 Market Discovery & Listing
**Priority: HIGH**

**Features:**
- Browse Polymarket markets
- Filter by category, expiry, volume
- Market details view
- Favorite markets
- Market alerts/notifications

**Implementation:**
- Market browser UI
- Polymarket API integration
- Market filtering/search
- Market detail pages

---

### 6. 🏷️ Category-Based Scanning
**Priority: MEDIUM**

**Features:**
- Scan specific categories (Crypto, Sports, Politics, etc.)
- Category filters in scanner
- Category-specific betting strategies
- Category performance tracking

**Implementation:**
- Add category field to markets
- Category filter in scanner
- Category stats in dashboard
- Category-based configs

---

### 7. ⏰ Time-Based Scanning
**Priority: MEDIUM**

**Features:**
- Scan by market creation time
- Scan by market expiry time
- Time-based filters
- Scheduled scans
- Market lifecycle tracking

**Implementation:**
- Add time filters to scanner
- Market creation/expiry tracking
- Time-based scan schedules
- Market timeline view

---

## Implementation Priority

### Phase 1: Core Enhancements (Week 1)
1. ✅ Wallet balance display
2. ✅ Multi-wallet support
3. ✅ Market browser/listing

### Phase 2: Bot Management (Week 2)
4. ✅ Multi-bot management
5. ✅ Bot config editor

### Phase 3: Advanced Features (Week 3)
6. ✅ Category-based scanning
7. ✅ Time-based scanning

---

## Technical Considerations

### Database Schema Updates
- `wallets` table (id, address, private_key_encrypted, name, active)
- `bots` table (id, name, config_json, wallet_id, status)
- `markets` table (id, market_id, category, created_at, expires_at, cached_data)
- `bot_configs` table (id, bot_id, config_json, created_at, active)

### API Endpoints Needed
- `/api/wallet/balance` - Get wallet balance
- `/api/wallet/list` - List all wallets
- `/api/wallet/add` - Add new wallet
- `/api/bot/list` - List all bots
- `/api/bot/create` - Create bot
- `/api/bot/{id}/config` - Get/update bot config
- `/api/markets/list` - Browse markets
- `/api/markets/{id}` - Market details
- `/api/scanner/categories` - Get categories
- `/api/scanner/filters` - Update scan filters

### Security
- Encrypt private keys at rest
- Secure key management
- API authentication
- Rate limiting

---

## Next Steps

1. **While migration runs:** Set up Railway dashboard DATABASE_URL
2. **After migration:** Start implementing Phase 1 features
3. **Priority:** Wallet balance display (quick win, high value)
