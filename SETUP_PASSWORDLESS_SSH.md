# Setup Passwordless SSH to Hetzner

## Quick Setup (One-Time Password Entry)

**Step 1: Copy your SSH key to Hetzner**

Run this command (enter password when prompted):
```bash
cat ~/.ssh/id_ed25519.pub | ssh root@5.161.64.209 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && chmod 700 ~/.ssh'
```

**Step 2: Test passwordless access**
```bash
ssh root@5.161.64.209 "echo '✅ Passwordless SSH works!'"
```

If that works, you're done! No more passwords needed.

## After Setup - Quick Commands

**Check auto-redemption:**
```bash
ssh root@5.161.64.209 "crontab -l | grep redeem"
```

**Check bot logs:**
```bash
ssh root@5.161.64.209 "tail -30 /root/vig/bot.log"
```

**Check redemption logs:**
```bash
ssh root@5.161.64.209 "tail -30 /root/vig/redeem.log"
```

**Or use the helper script:**
```bash
cd /Users/mikaelo/vig
./hetzner_commands.sh check-redeem
./hetzner_commands.sh check-bot
./hetzner_commands.sh ssh  # Opens SSH session
```

## Your SSH Key

Your public key is saved at: `~/.ssh/id_ed25519.pub`

To view it:
```bash
cat ~/.ssh/id_ed25519.pub
```
