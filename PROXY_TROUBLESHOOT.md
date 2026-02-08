# Proxy Troubleshooting

## Current Issue
**407 Proxy Authentication Required** - even after adding IP

## Check ProxyScrape Dashboard

### Option 1: Verify IP Authentication
1. Go to **"IP authentication"** 
2. Check if `5.161.64.209` shows as **"Active"** or **"Verified"**
3. Some services need you to click "Activate" or "Save" again

### Option 2: Look for Username/Password
Check these sections:
- **"Account"** → Look for "Username" or "API Key"
- **"Settings"** → Authentication credentials
- **"API"** → API credentials
- **"Proxy list"** → Some show username/password next to each proxy

### Option 3: Try Without Proxy First
Since randomization is now enabled, we could test if that helps:
- Remove proxy temporarily
- See if randomization + delays help bypass Cloudflare
- Add proxy back if still blocked

## Quick Test Without Proxy

To test if randomization helps:
```bash
# On Hetzner server
cd /root/vig
# Comment out proxy lines in .env
sed -i 's/^HTTP_PROXY/#HTTP_PROXY/' .env
sed -i 's/^HTTPS_PROXY/#HTTPS_PROXY/' .env
systemctl restart vigbot
```

Then check logs to see if orders place successfully.

## Next Steps

1. **Check ProxyScrape dashboard** for username/password
2. **OR** test without proxy first (randomization might help)
3. **OR** wait longer for IP authentication (some services take 5-10 min)

What do you see in the ProxyScrape dashboard? Any username/password shown?
