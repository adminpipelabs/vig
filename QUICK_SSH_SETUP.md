# Quick SSH Setup - Passwordless Access

## Option 1: Automated (Recommended)

**Install automation tools:**
```bash
brew install expect sshpass
```

**Then run:**
```bash
cd /Users/mikaelo/vig
bash auto_setup_ssh.sh
```

This will prompt for password once and set everything up automatically.

## Option 2: Manual (One-Time)

**Run this command (enter password when prompted):**
```bash
cat ~/.ssh/id_ed25519.pub | ssh root@5.161.64.209 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && chmod 700 ~/.ssh'
```

**Test it:**
```bash
ssh root@5.161.64.209 "echo '✅ Works!'"
```

## After Setup

**Use helper script for quick commands:**
```bash
cd /Users/mikaelo/vig
./hetzner_commands.sh check-redeem
./hetzner_commands.sh check-bot
./hetzner_commands.sh ssh
```

**Or direct SSH (no password needed):**
```bash
ssh root@5.161.64.209
```

## Your SSH Key

Already generated at: `~/.ssh/id_ed25519.pub`

View it:
```bash
cat ~/.ssh/id_ed25519.pub
```
