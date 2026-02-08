# Proxy Authentication Setup

## Current Issue
Proxy returns: **407 Proxy Authentication Required**

## ProxyScrape Authentication Options

### Option 1: IP Authentication (Recommended)
1. Go to **"IP authentication"** in ProxyScrape dashboard
2. Add your Hetzner server IP: `5.161.64.209`
3. Save
4. Wait a few minutes for activation
5. Then use proxy without username/password

### Option 2: Username/Password Authentication
If ProxyScrape provides username/password:
1. Format: `http://username:password@ip:port`
2. Update `.env`:
   ```bash
   HTTP_PROXY=http://username:password@216.26.237.15:3129
   HTTPS_PROXY=http://username:password@216.26.237.15:3129
   ```

## Check ProxyScrape Dashboard

**Look for:**
- **"IP authentication"** section - add `5.161.64.209`
- **"Authentication"** section - might show username/password
- **"Account"** section - might have API credentials

## After Setup

Restart bot:
```bash
systemctl restart vigbot
```

Check logs:
```bash
tail -50 /root/vig/bot.log | grep -E 'order|Placed|ERROR|407'
```
