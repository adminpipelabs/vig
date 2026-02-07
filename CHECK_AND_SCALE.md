# Check Auto-Redemption & Scale to $100 Bets

## Step 1: Verify Auto-Redemption is Running

**SSH into Hetzner and run:**
```bash
ssh root@5.161.64.209
cd /root/vig
bash quick_check_redeem.sh
```

**Or quick one-liner:**
```bash
crontab -l | grep redeem && echo "✅ Auto-redemption is configured" || echo "❌ Not configured - run: bash setup_auto_redeem.sh"
```

**Expected output if configured:**
```
0 */2 * * * cd /root/vig && /root/vig/venv/bin/python3 redeem_winnings.py >> /root/vig/redeem.log 2>&1
✅ Auto-redemption is configured
```

## Step 2: Check Recent Redemption Activity

```bash
tail -30 /root/vig/redeem.log
```

**Look for:**
- Recent redemption runs
- "✅ Redeemed successfully" messages
- Transaction hashes

## Step 3: Scale to $100 Bets Per Window

**If auto-redemption is confirmed working, update `.env` on Hetzner:**

```bash
cd /root/vig
nano .env
```

**Change:**
```
STARTING_CLIP=100.0
MAX_CLIP=100.0
```

**Or set via environment variable on Hetzner:**
```bash
# Add to .env file
echo "STARTING_CLIP=100.0" >> /root/vig/.env
echo "MAX_CLIP=100.0" >> /root/vig/.env
```

**Then restart the bot:**
```bash
systemctl restart vigbot
# Or if using nohup:
pkill -f main.py
cd /root/vig && source venv/bin/activate
nohup python3 main.py > bot.log 2>&1 & disown
```

## Current Configuration

- **Starting Clip:** $10 (from `STARTING_CLIP` env var, defaults to 10.0)
- **Max Clip:** $100 (from `MAX_CLIP` env var, defaults to 100.0)
- **Snowball:** Grows from $10 → $100 based on wins

## Scaling Strategy

**Option 1: Start at $100 immediately**
- Set `STARTING_CLIP=100.0`
- Bot will place $100 bets from the start
- Requires sufficient balance (~$1000+ recommended)

**Option 2: Let snowball grow naturally**
- Keep `STARTING_CLIP=10.0`
- Bot grows clip size after wins
- More conservative, safer approach

## Balance Requirements

**For $100 bets per window:**
- Need ~$1000+ available balance
- Auto-redemption ensures winnings are freed up every 2 hours
- With 10 bets per window = $1000 deployed per hour

## Verification Checklist

- [ ] Auto-redemption cron job exists
- [ ] Recent redemption logs show activity
- [ ] Balance is sufficient for $100 bets
- [ ] `.env` updated with `STARTING_CLIP=100.0`
- [ ] Bot restarted with new config
