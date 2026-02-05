# Railway Deployment Checklist

## Pre-Deployment

- [ ] Railway account created
- [ ] Residential proxy account created (Bright Data/SmartProxy/etc.)
- [ ] Proxy credentials obtained (host:port + username:password)
- [ ] PostgreSQL service created on Railway (or persistent volume planned)

## Environment Variables

- [ ] `RESIDENTIAL_PROXY_URL` set (format: `http://user:pass@host:port`)
- [ ] `POLYGON_PRIVATE_KEY` set
- [ ] `DATABASE_URL` set (if using PostgreSQL) OR `DB_PATH=/data/vig.db` (if using volume)
- [ ] `PAPER_MODE` set to `true` for initial testing
- [ ] Optional: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for notifications

## Code Files

- [ ] `clob_proxy.py` exists (proxy wrapper)
- [ ] `main.py` updated (uses proxy)
- [ ] `Procfile` exists (or `railway.toml` has startCommand)
- [ ] `railway.toml` updated (if using)
- [ ] `requirements.txt` has all dependencies

## Database Setup

### If Using PostgreSQL:
- [ ] PostgreSQL service created on Railway
- [ ] `DATABASE_URL` auto-set by Railway
- [ ] Connection tested: `psql "$DATABASE_URL" -c "SELECT 1;"`
- [ ] Migration run: `python3 migrate_to_postgres.py`
- [ ] Migration verified: Check row counts match SQLite

### If Using SQLite + Volume:
- [ ] Persistent volume created
- [ ] Volume mounted at `/data`
- [ ] `DB_PATH=/data/vig.db` set in env vars

## Deployment

- [ ] Repository connected to Railway
- [ ] Build successful (check Railway logs)
- [ ] Both processes starting (dashboard + bot)
- [ ] Dashboard accessible at Railway URL
- [ ] Bot logs showing "Vig v1 Starting"

## Verification

- [ ] Dashboard loads and shows data
- [ ] Bot logs show "CLOB client initialized with residential proxy"
- [ ] Bot logs show "Scanning Polymarket..."
- [ ] Test bet placed (if `PAPER_MODE=true`)
- [ ] Database storing bets correctly

## Go Live

- [ ] Tested with `PAPER_MODE=true` for at least 1 window
- [ ] Verified proxy is working (check proxy dashboard for traffic)
- [ ] Set `PAPER_MODE=false`
- [ ] Monitor first live window
- [ ] Set up alerts/notifications

## Post-Deployment

- [ ] Monitor Railway metrics (CPU, memory)
- [ ] Check proxy usage/costs
- [ ] Review bot logs daily
- [ ] Verify database backups (if using PostgreSQL)
