"""
proxy_init.py
MUST be imported FIRST in main.py. Does two things:
1. Patches httpx so all clients use our proxy and ignore env proxy (trust_env=False).
2. Replaces py_clob_client's global _http_client with a proxied client (they use a module-level client).
"""
import os
import httpx

# Unset env proxy vars so nothing overrides our proxy (httpx uses them when trust_env=True)
for key in list(os.environ.keys()):
    if key.upper() in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY"):
        del os.environ[key]

# Hardcoded proxy — bot must trade; env var was not reliably read on Railway.
# Format: http://user:pass@host:port
# If you get ProxyError 403: check Bright Data dashboard (credentials, zone active, balance).
PROXY_URL = "http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335"

# Allow override from env if set (so we can switch back later without code change)
_env_proxy = os.getenv("RESIDENTIAL_PROXY_URL", "").strip()
if _env_proxy and "placeholder" not in _env_proxy.lower() and "your-" not in _env_proxy.lower():
    PROXY_URL = _env_proxy

def _is_valid_proxy():
    if not PROXY_URL or not PROXY_URL.startswith("http"):
        return False
    bad = ("placeholder", "your-username", "your-proxy", "user:pass", ":port")
    return not any(p in PROXY_URL.lower() for p in bad)


if _is_valid_proxy():
    _OriginalClient = httpx.Client
    _OriginalAsyncClient = httpx.AsyncClient

    class ProxiedClient(_OriginalClient):
        def __init__(self, *args, **kwargs):
            kwargs["proxy"] = PROXY_URL
            kwargs["trust_env"] = False  # do not use HTTPS_PROXY etc.
            if "proxies" in kwargs:
                del kwargs["proxies"]
            super().__init__(*args, **kwargs)

    class ProxiedAsyncClient(_OriginalAsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["proxy"] = PROXY_URL
            kwargs["trust_env"] = False
            if "proxies" in kwargs:
                del kwargs["proxies"]
            super().__init__(*args, **kwargs)

    httpx.Client = ProxiedClient
    httpx.AsyncClient = ProxiedAsyncClient
    try:
        import httpx._client
        httpx._client.Client = ProxiedClient
        httpx._client.AsyncClient = ProxiedAsyncClient
    except Exception:
        pass

    # py_clob_client uses a MODULE-LEVEL client in http_helpers/helpers.py:
    #   _http_client = httpx.Client(http2=True)
    # We replace it with a client that has proxy + trust_env=False so env vars cannot override.
    import py_clob_client.http_helpers.helpers as _helpers
    if getattr(_helpers, "_http_client", None) is not None:
        try:
            _helpers._http_client.close()
        except Exception:
            pass
        _helpers._http_client = httpx.Client(
            proxy=PROXY_URL,
            trust_env=False,
            http2=False,  # HTTP/1.1 only — some proxies handle it more reliably
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    _display = PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL[:40]
    print(f"PROXY ACTIVE: {_display}")
    
    # Test proxy connection at startup - BLOCKING so we see results immediately
    import logging
    _logger = logging.getLogger("vig.proxy")
    
    def _test_proxy():
        _logger.info("=" * 70)
        _logger.info("TESTING BRIGHT DATA PROXY CONNECTION...")
        _logger.info(f"Proxy URL: {PROXY_URL.split('@')[-1] if '@' in PROXY_URL else 'hidden'}")
        
        # Test 1: Bright Data test endpoint
        try:
            _logger.info("Test 1: Connecting to Bright Data test endpoint (lumtest.com)...")
            test_client = httpx.Client(proxy=PROXY_URL, trust_env=False, timeout=10.0)
            resp = test_client.get("https://lumtest.com/myip.json", timeout=10.0)
            test_client.close()
            if resp.status_code == 200:
                ip_info = resp.json()
                _logger.info("=" * 70)
                _logger.info("✅ PROXY TEST SUCCESS!")
                _logger.info(f"   Connected to Bright Data successfully")
                _logger.info(f"   Proxy IP: {ip_info.get('ip', 'unknown')}")
                _logger.info(f"   Country: {ip_info.get('country', 'unknown')}")
                _logger.info(f"   This means proxy authentication WORKS!")
                _logger.info("=" * 70)
            else:
                _logger.error("=" * 70)
                _logger.error(f"❌ PROXY TEST FAILED: Bright Data returned {resp.status_code}")
                _logger.error(f"   Response: {resp.text[:200]}")
                _logger.error("=" * 70)
        except httpx.ProxyError as e:
            error_str = str(e)
            _logger.error("=" * 70)
            _logger.error("❌ PROXY TEST FAILED: ProxyError")
            _logger.error(f"   Error: {error_str}")
            if "403" in error_str:
                _logger.error("   ⚠️  403 Forbidden = Bright Data is rejecting requests")
                _logger.error("   Possible causes:")
                _logger.error("   1. Wrong credentials (but curl works, so unlikely)")
                _logger.error("   2. Zone suspended or inactive (check dashboard)")
                _logger.error("   3. Account balance empty (check dashboard)")
                _logger.error("   4. Trial account restrictions (no proof, but possible)")
                _logger.error("   5. Railway IP blocked by Bright Data (contact support)")
            _logger.error("=" * 70)
        except Exception as e:
            _logger.error("=" * 70)
            _logger.error(f"❌ PROXY TEST FAILED: {type(e).__name__}")
            _logger.error(f"   Error: {str(e)}")
            _logger.error("=" * 70)
        
        # Test 2: Polymarket CLOB (if test 1 succeeded)
        try:
            _logger.info("Test 2: Testing Polymarket CLOB through proxy...")
            test_client = httpx.Client(proxy=PROXY_URL, trust_env=False, timeout=10.0)
            resp = test_client.get("https://clob.polymarket.com/health", timeout=10.0)
            test_client.close()
            if resp.status_code == 200:
                _logger.info("✅ Polymarket CLOB accessible through proxy!")
            else:
                _logger.warning(f"⚠️  Polymarket returned {resp.status_code}: {resp.text[:100]}")
        except httpx.ProxyError as e:
            _logger.error(f"❌ Polymarket CLOB blocked: ProxyError - {e}")
        except Exception as e:
            _logger.warning(f"⚠️  Polymarket test error: {e}")
    
    # Run test immediately (blocking) so we see results in logs
    _test_proxy()
else:
    print("NO PROXY: RESIDENTIAL_PROXY_URL invalid or unset")
