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

# Hardcoded proxy — bot must trade; env var was not reliably read on Railway
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
            http2=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    _display = PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL[:40]
    print(f"PROXY ACTIVE: {_display}")
else:
    print("NO PROXY: RESIDENTIAL_PROXY_URL invalid or unset")
