# Verify Auto-Redemption Setup

## Quick Check Commands

**SSH into Hetzner:**
```bash
ssh root@5.161.64.209
```

**Then run these commands:**

### 1. Check if cron job exists:
```bash
crontab -l | grep redeem
```

**Expected output:**
```
0 */2 * * * cd /root/vig && /root/vig/venv/bin/python3 redeem_winnings.py >> /root/vig/redeem.log 2>&1
```

### 2. Check if redemption log exists and shows recent activity:
```bash
ls -lh /root/vig/redeem.log
tail -30 /root/vig/redeem.log
```

### 3. Check when cron will run next:
```bash
# Shows next 5 scheduled runs
crontab -l | grep redeem | awk '{print "Next runs:"}'
# Or check system cron logs
grep CRON /var/log/syslog | grep redeem | tail -5
```

### 4. Test redemption manually (to verify it works):
```bash
cd /root/vig
source venv/bin/activate
python3 redeem_winnings.py
```

## If Auto-Redemption is NOT Set Up

**Run the setup script:**
```bash
cd /root/vig
bash setup_auto_redeem.sh
```

**Or manually add to crontab:**
```bash
crontab -e
# Add this line:
0 */2 * * * cd /root/vig && /root/vig/venv/bin/python3 redeem_winnings.py >> /root/vig/redeem.log 2>&1
# Save and exit (Ctrl+X, then Y, then Enter)
```

## Verification Checklist

- [ ] Cron job exists (`crontab -l | grep redeem` shows the job)
- [ ] Script exists (`ls /root/vig/redeem_winnings.py`)
- [ ] Virtual environment exists (`ls /root/vig/venv/bin/python3`)
- [ ] Log file exists or will be created (`/root/vig/redeem.log`)
- [ ] Manual test works (`python3 redeem_winnings.py` runs successfully)

## Schedule

Auto-redemption runs every 2 hours at:
- 00:00 UTC
- 02:00 UTC
- 04:00 UTC
- 06:00 UTC
- 08:00 UTC
- 10:00 UTC
- 12:00 UTC
- 14:00 UTC
- 16:00 UTC
- 18:00 UTC
- 20:00 UTC
- 22:00 UTC

## What It Does

1. Connects to Polygon via Alchemy
2. Queries database for won bets with `condition_id`
3. Groups by `condition_id` (one redemption per market)
4. Calls `redeemPositions()` on ConditionalTokens contract
5. Logs results to `/root/vig/redeem.log`

## Troubleshooting

**If cron job exists but not running:**
- Check cron service: `systemctl status cron` (should be active)
- Check logs: `grep CRON /var/log/syslog | tail -20`
- Verify script path is correct
- Check Python path in cron: `/root/vig/venv/bin/python3`

**If manual test fails:**
- Check `.env` file has `POLYGON_PRIVATE_KEY`
- Check `DATABASE_URL` is set
- Verify database connection works
- Check POL balance (needs ~0.01 POL for gas)
