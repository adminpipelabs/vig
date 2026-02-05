# Test Results for Dev — Order Placement Issues

**Date:** February 4, 2026  
**Requested by:** MO

---

## 1. `client.set_allowances()` Output

**Result:** ❌ Method does not exist

```
AttributeError: 'ClobClient' object has no attribute 'set_allowances'
```

**Available allowance methods:**
- `get_balance_allowance()` ✅
- `update_balance_allowance()` ✅

**Note:** The `set_allowances()` method mentioned by MO does not exist in the current `py-clob-client` version (0.34.5 - latest available). We've been using `update_balance_allowance()` instead.

**Version Check:**
- Installed: 0.34.5
- Latest available: 0.34.5
- No newer version with `set_allowances()` found

---

## 2. Full Error Traceback from Manual Test Order

**Market:** Will Kahrabaa Ismailia FC win on 2026-02-04?  
**Token ID:** `88935552803805200614363760402590819779763081586466777299788105505305613405537`  
**Price:** $0.83  
**Side:** NO  
**Order Size:** 1.1976 shares ($1 test bet)

**Full Traceback:**
```
Traceback (most recent call last):
  File "<string>", line 52, in <module>
  File "/opt/homebrew/lib/python3.11/site-packages/py_clob_client/client.py", line 627, in create_and_post_order
    return self.post_order(ord)
           ^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.11/site-packages/py_clob_client/client.py", line 614, in post_order
    return post(
           ^^^^^
  File "/opt/homebrew/lib/python3.11/site-packages/py_clob_client/http_helpers/helpers.py", line 69, in post
    return request(endpoint, POST, headers, data)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.11/site-packages/py_clob_client/http_helpers/helpers.py", line 57, in request
    raise PolyApiException(resp)
py_clob_client.exceptions.PolyApiException: PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance'}]
```

**Error:** `not enough balance / allowance`

**Context:**
- CLOB balance: $94.94 USDC.e ✅
- On-chain approvals: Complete (USDC.e → Exchange & NegRisk) ✅
- `update_balance_allowance()` called: ✅
- Still getting balance/allowance error ❌

---

## 3. Sample Token ID from Bot Scanner Logs

**Token ID:** `88935552803805200614363760402590819779763081586466777299788105505305613405537`

**Market Details:**
- Question: "Will Kahrabaa Ismailia FC win on 2026-02-04?"
- Price: $0.83
- Side: NO
- Expiry: ~30 minutes from scan time

**How to test:**
```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY

TOKEN_ID = "88935552803805200614363760402590819779763081586466777299788105505305613405537"

order = client.create_and_post_order(
    OrderArgs(
        token_id=TOKEN_ID,
        price=0.83,
        size=1.0 / 0.83,  # $1 worth
        side=BUY,
    )
)
```

---

## Current Status Summary

**What's Working:**
- ✅ Token approvals on-chain (USDC.e + CTF)
- ✅ CLOB balance: $94.94 USDC.e
- ✅ `update_balance_allowance()` executes successfully
- ✅ Bot scanning and finding markets
- ✅ CLOB client initialization

**What's Not Working:**
- ❌ Orders fail with "not enough balance / allowance"
- ❌ `set_allowances()` method doesn't exist in current py-clob-client version

**Hypothesis:**
1. The `set_allowances()` method might be in a newer version of py-clob-client
2. There might be a different approval flow we're missing
3. The order size/price format might be incorrect (though error says balance/allowance, not format)
4. There might be a conditional token approval needed that we haven't done

---

## Questions for Dev

1. What version of `py-clob-client` should we be using? (Currently 0.34.5)
2. Is `set_allowances()` in a newer version, or is it called something else?
3. Are there any conditional token approvals needed beyond what we've done?
4. Should the order size be in a different format (raw token units vs shares)?

---

**Files:**
- Test script: `/Users/mikaelo/vig/test_order.py`
- Bot logs: `/Users/mikaelo/.cursor/projects/Users-mikaelo-trading-bridge/terminals/43597.txt`
