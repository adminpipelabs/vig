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
            
            # Debug: List all attributes to find the httpx client
            all_attrs = [attr for attr in dir(self) if not attr.startswith('__')]
            logger.debug(f"ClobClient attributes: {all_attrs}")
            
            # Find the httpx client - check multiple possible names
            client_attr = None
            old_client = None
            
            for attr_name in ['client', '_client', 'http_client', '_http_client', '_session', 'session']:
                if hasattr(self, attr_name):
                    candidate = getattr(self, attr_name)
                    # Check if it's an httpx.Client instance
                    if isinstance(candidate, httpx.Client):
                        client_attr = attr_name
                        old_client = candidate
                        logger.info(f"Found httpx client at attribute: {attr_name}")
                        break
            
            if not client_attr or not old_client:
                # Try to find any httpx-like object
                for attr_name in all_attrs:
                    try:
                        candidate = getattr(self, attr_name)
                        if hasattr(candidate, 'request') and hasattr(candidate, 'headers'):
                            # Looks like an HTTP client
                            client_attr = attr_name
                            old_client = candidate
                            logger.info(f"Found HTTP client-like object at attribute: {attr_name} (type: {type(candidate).__name__})")
                            break
                    except:
                        continue
            
            if not client_attr or not old_client:
                logger.error("❌ Could not find httpx client attribute in ClobClient")
                logger.error(f"Available attributes: {all_attrs}")
                logger.error("Attempting alternative approach: patching httpx.Client globally...")
                # Fallback: patch httpx.Client to always use proxy
                _patch_httpx_globally()
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
        
        # Assign the patched init
        clob_module.ClobClient.__init__ = _patched_init
        logger.info("✅ py_clob_client globally patched with residential proxy")
        
    except Exception as e:
        logger.error(f"❌ Failed to patch py_clob_client: {e}")
        import traceback
        logger.error(traceback.format_exc())


def _patch_httpx_globally():
    """
    Fallback: Patch httpx.Client to always use proxy if client attribute not found.
    This patches httpx.Client.__init__ to inject proxy parameter.
    """
    _original_client_init = httpx.Client.__init__
    
    def _patched_client_init(self, *args, **kwargs):
        # Inject proxy if not already provided
        if 'proxy' not in kwargs:
            kwargs['proxy'] = PROXY_URL
            logger.debug(f"Injecting proxy into httpx.Client: {PROXY_URL.split('@')[-1] if '@' in PROXY_URL else '...'}")
        
        # Call original init with proxy included
        _original_client_init(self, *args, **kwargs)
        
        # Verify proxy was set
        proxy_set = getattr(self, '_proxy', None) or getattr(self, '_proxies', {})
        if proxy_set:
            logger.info(f"✅ httpx.Client created with proxy: {bool(proxy_set)}")
        else:
            logger.warning("⚠️  Proxy may not have been set in httpx.Client")
    
    httpx.Client.__init__ = _patched_client_init
    logger.info("✅ httpx.Client.__init__ globally patched - all new clients will use proxy")


def add_debug_wrapper():
    """
    Temporary debug wrapper to see actual httpx exceptions.
    This helps diagnose proxy connection issues.
    """
    _original_request = httpx.Client.request
    
    def _debug_request(self, method, url, **kwargs):
        # Log request details (including proxy)
        proxy_info = getattr(self, '_proxy', None) or getattr(self, '_proxies', {}) or kwargs.get('proxy')
        logger.debug(f"HTTPX Request: {method} {url} (proxy: {bool(proxy_info)})")
        
        try:
            return _original_request(self, method, url, **kwargs)
        except Exception as e:
            # Get proxy info from multiple sources
            proxy_info = (
                getattr(self, '_proxy', None) or 
                getattr(self, '_proxies', {}) or 
                kwargs.get('proxy') or
                "Not set"
            )
            
            logger.error("=" * 60)
            logger.error(f"❌ HTTPX Request failed:")
            logger.error(f"   Method: {method}")
            logger.error(f"   URL: {url}")
            logger.error(f"   Proxy configured: {bool(proxy_info) and proxy_info != 'Not set'}")
            logger.error(f"   Proxy value: {str(proxy_info)[:50] if proxy_info != 'Not set' else 'Not set'}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)[:200]}")
            import traceback
            logger.error(f"   Full traceback:\n{traceback.format_exc()}")
            logger.error("=" * 60)
            raise
    
    httpx.Client.request = _debug_request
    logger.info("✅ Debug wrapper added to httpx.Client.request")
