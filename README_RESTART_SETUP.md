# Railway Bot Restart Setup

This guide helps you safely set up the Railway API variables needed for the bot restart functionality.

## Quick Start

Run the setup script:

```bash
cd /Users/mikaelo/vig
./setup_railway_restart.sh
```

The script will:
- ✅ Check existing variables (won't overwrite unless you confirm)
- ✅ Guide you through getting Railway API token
- ✅ Auto-detect Service ID if possible
- ✅ Show summary before making changes
- ✅ Ask for confirmation before setting variables

## What Gets Set

Two environment variables:
- `RAILWAY_TOKEN` - Your Railway API token (from Railway account)
- `RAILWAY_SERVICE_ID` - Your service ID (from Railway dashboard)

## Safety Features

- **No overwrites**: Won't change existing variables unless you explicitly confirm
- **Validation**: Checks token format before setting
- **Confirmation**: Shows summary and asks before making changes
- **Error handling**: Exits safely if something goes wrong

## Manual Setup (Alternative)

If you prefer to set variables manually:

1. **Get Railway API Token:**
   - Go to https://railway.app/account
   - Scroll to "API Tokens"
   - Click "Create Token"
   - Copy the token

2. **Get Service ID:**
   - Go to Railway dashboard → Your project → Your service
   - Look at URL: `https://railway.app/project/[PROJECT_ID]/service/[SERVICE_ID]`
   - Copy the `SERVICE_ID` part

3. **Set Variables:**
   ```bash
   railway variables set RAILWAY_TOKEN="your_token_here"
   railway variables set RAILWAY_SERVICE_ID="your_service_id_here"
   ```

4. **Restart Service:**
   ```bash
   railway restart
   ```

## After Setup

Once variables are set:
1. Restart Railway service once (to load new variables)
2. Go to dashboard → Bot Control Panel
3. Click "🔄 Restart" button
4. Bot will restart automatically!

## Troubleshooting

**Script says "Railway CLI not found":**
```bash
npm i -g @railway/cli
railway login
```

**Script says "Not logged in":**
```bash
railway login
```

**Can't find Service ID:**
- Use manual setup method above
- Or check Railway dashboard URL

**Restart button shows instructions instead of restarting:**
- Variables might not be loaded yet
- Restart Railway service once: `railway restart`
- Check variables are set: `railway variables`
