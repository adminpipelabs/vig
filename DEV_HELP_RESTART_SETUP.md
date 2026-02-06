# Dev Help: Railway Bot Restart Setup

## What I'm Trying to Do

Enable bot restart functionality directly from the dashboard UI, so users don't have to go to Railway dashboard every time the bot needs restarting.

## Current Problem

- Bot sometimes stops running (crashes, errors, etc.)
- User has to manually go to Railway dashboard → Service → Restart
- This is inconvenient and requires leaving the monitoring dashboard

## Proposed Solution

### 1. Dashboard UI Changes (Already Implemented)
- Added "Bot Control Panel" with visual status indicators (🟢 Running / 🔴 Stopped)
- Added Restart/Stop/Start buttons
- Added bot description explaining what it does

### 2. Backend API Endpoint (Already Implemented)
- `/api/bot-control` endpoint that accepts `action` parameter (restart/stop/start)
- Uses Railway GraphQL API to restart deployments programmatically
- Requires two environment variables:
  - `RAILWAY_TOKEN` - Railway API token (from Railway account)
  - `RAILWAY_SERVICE_ID` - Service ID (from Railway dashboard URL)

### 3. Setup Script (Created)
- `setup_railway_restart.sh` - Safe script to set up the required environment variables
- Features:
  - Checks existing variables (won't overwrite unless confirmed)
  - Validates token format
  - Shows summary before making changes
  - Asks for confirmation
  - Auto-detects Service ID when possible

## How It Works

### Railway GraphQL API Flow:
1. User clicks "Restart" button in dashboard
2. Frontend calls `/api/bot-control` with `action=restart`
3. Backend queries Railway GraphQL API to get latest deployment ID
4. Backend calls `deploymentRestart` mutation with deployment ID
5. Railway restarts the service
6. Dashboard refreshes to show updated status

### Code Implementation:
```python
# dashboard.py - /api/bot-control endpoint
- Gets RAILWAY_TOKEN and RAILWAY_SERVICE_ID from environment
- Queries Railway GraphQL API: https://backboard.railway.com/graphql/v2
- Gets latest deployment ID for the service
- Calls deploymentRestart mutation
- Returns success/error message
```

## Expected Outcome

### Success Case:
1. User clicks "🔄 Restart" button
2. Button shows "Processing..."
3. Message appears: "✅ Bot restart initiated via Railway API. This may take 30-60 seconds."
4. Page auto-refreshes after 5 seconds
5. Bot status shows as "Running" again
6. Old pending bets get settled automatically (bot checks on startup)

### Fallback Case:
- If `RAILWAY_TOKEN` or `RAILWAY_SERVICE_ID` not set:
  - Shows instructions on how to set them up
  - Provides link to Railway dashboard for manual restart

## Safety Considerations

### Script Safety:
- ✅ Won't overwrite existing variables unless explicitly confirmed
- ✅ Validates token format before setting
- ✅ Shows summary before making changes
- ✅ Exits safely on errors

### API Safety:
- ✅ Only restarts deployments (doesn't delete or modify)
- ✅ Falls back gracefully if API not configured
- ✅ Shows clear error messages

## Questions for Dev

1. **Railway API Token**: 
   - Is Railway GraphQL API the best approach, or is there a simpler method?
   - Do we need a paid Railway plan for API tokens? (Documentation suggests PERSONAL/TEAM tokens)

2. **Service ID Detection**:
   - Can we auto-detect Service ID from Railway environment variables?
   - Railway might expose `RAILWAY_SERVICE_ID` automatically - should we check for that first?

3. **Alternative Approaches**:
   - Could we use Railway CLI from within the app? (Currently tries this as fallback)
   - Should we use Railway's webhook/deployment triggers instead?
   - Is there a Railway environment variable that already contains the service ID?

4. **Error Handling**:
   - What happens if Railway API is down?
   - Should we add retry logic?
   - Should we log restart attempts?

5. **Security**:
   - Is storing `RAILWAY_TOKEN` as environment variable secure enough?
   - Should we encrypt it or use Railway's secrets management?

## Files Changed

1. `dashboard.py`:
   - Added `/api/bot-control` endpoint (lines ~516-580)
   - Added Bot Control Panel UI (lines ~980-1000)
   - Added `controlBot()` JavaScript function (lines ~1370-1400)
   - Updated `updateBotStatus()` to show control panel

2. `setup_railway_restart.sh`:
   - New script for safe variable setup
   - Checks existing variables
   - Validates inputs
   - Asks for confirmation

3. `README_RESTART_SETUP.md`:
   - Documentation for users
   - Troubleshooting guide

## Testing Plan

1. **Test Setup Script**:
   - Run `./setup_railway_restart.sh`
   - Verify it detects existing variables
   - Verify it asks for confirmation
   - Verify it sets variables correctly

2. **Test Restart Functionality**:
   - Set `RAILWAY_TOKEN` and `RAILWAY_SERVICE_ID`
   - Click "Restart" button in dashboard
   - Verify Railway service restarts
   - Verify dashboard shows updated status

3. **Test Fallback**:
   - Remove `RAILWAY_TOKEN`
   - Click "Restart" button
   - Verify it shows setup instructions

## Potential Issues

1. **Railway API Token Access**:
   - May require paid Railway plan
   - Need to verify if free tier has API access

2. **Service ID Detection**:
   - Might not be able to auto-detect reliably
   - User may need to set manually

3. **Railway CLI Dependency**:
   - Script requires Railway CLI installed
   - May not be available in all environments

## Alternative: Simpler Approach?

Instead of Railway API, could we:
- Use Railway CLI from within the app? (Already tried, but requires CLI installed)
- Trigger a redeploy by pushing an empty commit? (Too heavy-handed)
- Use Railway's deployment webhooks? (Requires webhook setup)

## Your Opinion Needed

1. **Is Railway GraphQL API the right approach?** Or is there a simpler way?
2. **Can we auto-detect Service ID** from Railway's environment variables?
3. **Should we proceed with this approach** or use a different method?
4. **Any security concerns** with storing Railway token as env var?
5. **Should we add any additional safety checks** before restarting?

Thanks for reviewing! 🙏
