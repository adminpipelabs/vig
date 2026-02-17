# Deployment Guide

## Railway Deployment (Recommended)

Railway will auto-deploy when you push to GitHub.

### Setup

1. **Push code to GitHub** (requires git auth):
   ```bash
   git push origin main
   ```

2. **Set Environment Variables in Railway**:
   ```
   USE_US_API=true
   POLYMARKET_US_KEY_ID=your-key-id
   POLYMARKET_US_PRIVATE_KEY=your-private-key
   PROFIT_TARGET_PCT=0.15
   FORCE_EXIT_MINUTES=10
   DATABASE_URL=postgresql://...
   DB_PATH=vig.db
   PAPER_MODE=false
   ```

3. **Railway will automatically**:
   - Build Docker image
   - Install dependencies (including cryptography)
   - Run both dashboard (web) and bot (worker)

### Railway Services

Railway will run:
- **Web service**: `python3 dashboard.py` (port 8080)
- **Worker service**: `python3 main.py` (bot)

## Hetzner Deployment

### Option 1: Direct Git Clone

```bash
# SSH into Hetzner server
ssh user@your-hetzner-ip

# Clone repo
git clone https://github.com/adminpipelabs/vig.git
cd vig

# Install dependencies
pip3 install -r requirements.txt
pip3 install cryptography httpx

# Set environment variables
export USE_US_API=true
export POLYMARKET_US_KEY_ID=...
export POLYMARKET_US_PRIVATE_KEY=...
export DATABASE_URL=postgresql://...
export PAPER_MODE=false

# Run bot
python3 main.py

# Run dashboard (separate terminal or screen)
python3 dashboard.py
```

### Option 2: Docker on Hetzner

```bash
# Build image
docker build -t vig-bot .

# Run bot
docker run -d \
  --name vig-bot \
  -e USE_US_API=true \
  -e POLYMARKET_US_KEY_ID=... \
  -e POLYMARKET_US_PRIVATE_KEY=... \
  -e DATABASE_URL=... \
  -e PAPER_MODE=false \
  vig-bot python3 main.py

# Run dashboard
docker run -d \
  --name vig-dashboard \
  -p 8080:8080 \
  -e DATABASE_URL=... \
  vig-bot python3 dashboard.py
```

### Option 3: Systemd Services (Hetzner)

Create `/etc/systemd/system/vig-bot.service`:
```ini
[Unit]
Description=Vig Trading Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/vig
Environment="USE_US_API=true"
Environment="POLYMARKET_US_KEY_ID=..."
Environment="POLYMARKET_US_PRIVATE_KEY=..."
Environment="DATABASE_URL=..."
Environment="PAPER_MODE=false"
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/vig-dashboard.service`:
```ini
[Unit]
Description=Vig Dashboard
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/vig
Environment="DATABASE_URL=..."
ExecStart=/usr/bin/python3 dashboard.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable vig-bot vig-dashboard
sudo systemctl start vig-bot vig-dashboard
sudo systemctl status vig-bot vig-dashboard
```

## Environment Variables Checklist

### Required for US API
- `USE_US_API=true`
- `POLYMARKET_US_KEY_ID` (UUID from Polymarket developer portal)
- `POLYMARKET_US_PRIVATE_KEY` (Ed25519 private key)

### Required for Database
- `DATABASE_URL` (PostgreSQL connection string)

### Optional
- `PROFIT_TARGET_PCT=0.15` (default: 15%)
- `FORCE_EXIT_MINUTES=10` (default: 10 minutes before expiry)
- `PAPER_MODE=false` (set to true for testing)
- `POLL_INTERVAL_SECONDS=5` (default: 5 seconds)
- `MAX_BETS_PER_WINDOW=500` (default: 500)

## Verification

After deployment, check:

1. **Bot logs**:
   ```bash
   # Railway: View logs in dashboard
   # Hetzner: journalctl -u vig-bot -f
   ```

2. **Dashboard**: Visit `http://your-server:8080`

3. **API health**: `curl http://your-server:8080/api/health`

4. **Bot status**: `curl http://your-server:8080/api/bot-status`

## Troubleshooting

### Authentication Errors
- Verify `POLYMARKET_US_KEY_ID` is correct UUID
- Verify `POLYMARKET_US_PRIVATE_KEY` is correct Ed25519 key
- Check key format (base64, hex, or PEM)

### Import Errors
- Ensure `cryptography` is installed: `pip install cryptography`
- Check Python version (3.9+ required)

### Database Errors
- Verify `DATABASE_URL` is correct
- Check PostgreSQL is accessible
- Verify tables exist (run migrations if needed)

### Port Issues
- Dashboard defaults to port 8080
- Change via `PORT` environment variable if needed
- Ensure firewall allows port 8080
