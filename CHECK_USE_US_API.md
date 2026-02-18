# Check USE_US_API Environment Variable

**Critical:** The bot only uses the US API if `USE_US_API=true` is set.

## Verify in Railway

1. Go to Railway Dashboard
2. Click on **"vig"** service (the bot worker)
3. Go to **Variables** tab
4. Check if `USE_US_API` exists and is set to `true`

**If missing or set to `false`:**
- Add/Update: `USE_US_API=true`
- Save
- Redeploy

## What to Check

The logs show "Placing bets on 10 markets using US API" which means `USE_US_API=true` is set, BUT we're still getting authentication errors.

## Other Possible Issues

Based on Polymarket docs:
1. **Account verification**: Must complete KYC in Polymarket US app
2. **Authentication method**: Must use same sign-in method (Apple/Google/Email) for developer portal
3. **API key status**: Key might need to be activated/enabled

## Next Steps

1. Verify `USE_US_API=true` in Railway
2. Check Polymarket dashboard - is account fully verified?
3. Try creating a NEW API key pair (revoke old, create new)
4. Contact Polymarket support if issue persists
