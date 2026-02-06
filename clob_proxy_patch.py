"""
clob_proxy_patch.py
Patches py_clob_client to use residential proxy for Cloudflare bypass.

The issue: py_clob_client creates its own httpx.Client internally and doesn't
respect environment variables. We need to inject the proxy directly.
"""
import os
import httpx
import logging

logger = logging.getLogger("vig.clob_proxy_patch")

PROXY_URL = os.getenv("RESIDENTIAL_PROXY_URL", "").strip()


def patch_clob_globally():
    """
    Monkey-patch py_clob_client to always use proxy.
    Call this once at startup before creating any ClobClient.
    """
    if not PROXY_URL:
        logger.warning("⚠️  No RESIDENTIAL_PROXY_URL set — CLOB calls may be blocked by Cloudflare")
        return
    
    try:
        import py_clob_client.client as clob_module
        
        _original_init = clob_module.ClobClient.__init__
        
        def _patched_init(self, *args, **kwargs):
            # Call original init first
            _original_init(self, *args, **kwargs)
            
            # Find the httpx client - it might be stored as 'client', '_client', or 'http_client'
            client_attr = None
            for attr_name in ['client', '_client', 'http_client', '_http_client']:
                if hasattr(self, attr_name):
                    client_attr = attr_name
                    break
            
            if not client_attr:
                logger.warning("⚠️  Could not find httpx client attribute in ClobClient - patch may not work")
                return
            
            old_client = getattr(self, client_attr)
            if not old_client:
                logger.warning("⚠️  ClobClient httpx client is None - patch may not work")
                return
            
            # Get old headers and base_url
            old_headers = dict(old_client.headers) if hasattr(old_client, 'headers') else {}
            base_url = getattr(old_client, 'base_url', None) or (self.host if hasattr(self, 'host') else None)
            
            # Close the original client
            try:
                if hasattr(old_client, 'close'):
                    old_client.close()
            except:
                pass
            
            # Create new client with proxy
            new_client = httpx.Client(
                base_url=base_url,
                proxy=PROXY_URL,
                timeout=30.0,
                headers={
                    **old_headers,
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
            )
            
            # Replace the client
            setattr(self, client_attr, new_client)
            
            proxy_display = PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL[:30] + "..."
            logger.info(f"✅ ClobClient patched with proxy: {proxy_display} (client attr: {client_attr})")
            
            # Verify proxy is set
            if hasattr(new_client, '_proxy') or hasattr(new_client, '_proxies'):
                proxy_set = getattr(new_client, '_proxy', None) or getattr(new_client, '_proxies', {})
                logger.info(f"✅ Verified proxy is set in httpx client: {bool(proxy_set)}")
            else:
                logger.warning("⚠️  Could not verify proxy in httpx client - may need different approach")
        
        clob_module.ClobClient.__init__ = _patched_init
        logger.info("✅ py_clob_client globally patched with residential proxy")
        
    except Exception as e:
        logger.error(f"❌ Failed to patch py_clob_client: {e}")
        import traceback
        logger.error(traceback.format_exc())


def add_debug_wrapper():
    """
    Temporary debug wrapper to see actual httpx exceptions.
    This helps diagnose proxy connection issues.
    """
    _original_request = httpx.Client.request
    
    def _debug_request(self, method, url, **kwargs):
        try:
            return _original_request(self, method, url, **kwargs)
        except Exception as e:
            proxy_info = getattr(self, '_proxy', None) or getattr(self, '_proxies', {})
            logger.error(f"❌ HTTPX Request failed:")
            logger.error(f"   Method: {method}")
            logger.error(f"   URL: {url}")
            logger.error(f"   Proxy: {proxy_info}")
            logger.error(f"   Error: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            raise
    
    httpx.Client.request = _debug_request
    logger.info("✅ Debug wrapper added to httpx.Client.request")
