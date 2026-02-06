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
    _patched_count = [0]  # Use list to allow modification in nested function
    
    def _patched_client_init(self, *args, **kwargs):
        # ALWAYS inject proxy (even if one is provided, override with ours)
        kwargs['proxy'] = PROXY_URL
        _patched_count[0] += 1
        proxy_display = PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL[:30] + "..."
        logger.info(f"🔧 Injecting proxy into httpx.Client #{_patched_count[0]}: {proxy_display}")
        
        # Call original init with proxy included
        try:
            _original_client_init(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ httpx.Client.__init__ failed: {e}")
            raise
        
        # Verify proxy was set (check multiple ways httpx might store it)
        # httpx stores proxy in transport._pool._proxy or similar
        proxy_set = False
        proxy_location = "unknown"
        
        # Check direct attributes
        if hasattr(self, '_proxy') and self._proxy:
            proxy_set = True
            proxy_location = "_proxy"
        elif hasattr(self, '_proxies') and self._proxies:
            proxy_set = True
            proxy_location = "_proxies"
        elif hasattr(self, 'transport'):
            # Check transport level
            transport = self.transport
            if hasattr(transport, '_pool'):
                pool = transport._pool
                if hasattr(pool, '_proxy') and pool._proxy:
                    proxy_set = True
                    proxy_location = "transport._pool._proxy"
        
        if proxy_set:
            logger.info(f"✅ httpx.Client #{_patched_count[0]} verified with proxy (location: {proxy_location})")
        else:
            # Log transport details for debugging
            transport_info = "None"
            if hasattr(self, 'transport'):
                transport_info = f"{type(self.transport).__name__}"
                if hasattr(self.transport, '_pool'):
                    transport_info += f" (pool: {type(self.transport._pool).__name__})"
            logger.warning(f"⚠️  httpx.Client #{_patched_count[0]} proxy NOT verified (transport: {transport_info})")
            logger.warning(f"   Client attributes: {[a for a in dir(self) if 'proxy' in a.lower()][:5]}")
    
    httpx.Client.__init__ = _patched_client_init
    logger.info("✅ httpx.Client.__init__ globally patched - all new clients will use proxy")


def add_debug_wrapper():
    """
    Temporary debug wrapper to see actual httpx exceptions.
    This helps diagnose proxy connection issues.
    """
    _original_request = httpx.Client.request
    _request_count = [0]
    
    def _debug_request(self, method, url, **kwargs):
        _request_count[0] += 1
        request_id = _request_count[0]
        
        # Log request details (including proxy)
        # Check multiple ways proxy might be stored - be thorough
        proxy_info = None
        proxy_set = False
        
        # Method 1: Check kwargs
        if 'proxy' in kwargs:
            proxy_info = kwargs['proxy']
            proxy_set = True
        elif 'proxies' in kwargs and kwargs['proxies']:
            proxy_info = kwargs['proxies']
            proxy_set = True
        
        # Method 2: Check client instance attributes
        if not proxy_set:
            proxy_info = getattr(self, '_proxy', None)
            if proxy_info:
                proxy_set = True
        
        # Method 3: Check proxies dict
        if not proxy_set:
            proxies_dict = getattr(self, '_proxies', None)
            if proxies_dict:
                proxy_info = proxies_dict
                proxy_set = True
        
        # Method 4: Check transport layer
        if not proxy_set and hasattr(self, 'transport'):
            transport = self.transport
            # Check transport._proxy
            if hasattr(transport, '_proxy') and transport._proxy:
                proxy_info = transport._proxy
                proxy_set = True
            # Check transport._pool._proxy
            elif hasattr(transport, '_pool') and hasattr(transport._pool, '_proxy'):
                pool_proxy = transport._pool._proxy
                if pool_proxy:
                    proxy_info = pool_proxy
                    proxy_set = True
        
        # Method 5: Check if httpx is using HTTPS_PROXY env var automatically
        if not proxy_set:
            import os
            https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
            if https_proxy:
                proxy_info = f"HTTPS_PROXY env var: {https_proxy[:50]}..."
                proxy_set = True
        
        # Method 6: Check httpcore connection pool directly (most reliable)
        if not proxy_set and hasattr(self, 'transport'):
            try:
                transport = self.transport
                # Check httpcore._sync.connection_pool.ConnectionPool
                if hasattr(transport, '_pool'):
                    pool = transport._pool
                    # httpcore stores proxy in _proxy attribute
                    if hasattr(pool, '_proxy') and pool._proxy:
                        proxy_info = str(pool._proxy)
                        proxy_set = True
                    # Or check _connections for proxy info
                    elif hasattr(pool, '_connections'):
                        for conn in pool._connections.values():
                            if hasattr(conn, '_proxy') and conn._proxy:
                                proxy_info = str(conn._proxy)
                                proxy_set = True
                                break
            except Exception as e:
                logger.debug(f"Could not check transport pool for proxy: {e}")
        
        # Log first request at INFO to confirm proxy; rest at DEBUG to avoid log flood
        if request_id == 1:
            logger.info(f"HTTPX Request #1: {method} {url[:50]}... (proxy: {proxy_set})")
        else:
            logger.debug(f"HTTPX Request #{request_id}: {method} {url[:50]}... (proxy: {proxy_set})")
        if proxy_set and proxy_info:
            # Redact password for logging
            proxy_str = str(proxy_info)
            if isinstance(proxy_info, dict):
                proxy_str = str(list(proxy_info.values())[0]) if proxy_info else "dict"
            if "@" in proxy_str and ":" in proxy_str.split("@")[0]:
                parts = proxy_str.split("@")
                user_pass = parts[0].split(":")
                if len(user_pass) >= 2:
                    redacted = f"{user_pass[0]}:****@{parts[1] if len(parts) > 1 else ''}"
                    logger.debug(f"   Proxy details: {redacted}")
        
        try:
            result = _original_request(self, method, url, **kwargs)
            logger.debug(f"✅ HTTPX Request #{request_id} succeeded: {result.status_code if hasattr(result, 'status_code') else 'OK'}")
            return result
        except Exception as e:
            # Get proxy info from multiple sources - comprehensive check
            proxy_info = None
            proxy_detected = False
            
            # Check all the same methods as above
            if 'proxy' in kwargs:
                proxy_info = kwargs['proxy']
                proxy_detected = True
            elif 'proxies' in kwargs and kwargs['proxies']:
                proxy_info = kwargs['proxies']
                proxy_detected = True
            elif hasattr(self, '_proxy') and self._proxy:
                proxy_info = self._proxy
                proxy_detected = True
            elif hasattr(self, '_proxies') and self._proxies:
                proxy_info = self._proxies
                proxy_detected = True
            elif hasattr(self, 'transport'):
                transport = self.transport
                if hasattr(transport, '_proxy') and transport._proxy:
                    proxy_info = transport._proxy
                    proxy_detected = True
                elif hasattr(transport, '_pool') and hasattr(transport._pool, '_proxy'):
                    pool_proxy = transport._pool._proxy
                    if pool_proxy:
                        proxy_info = pool_proxy
                        proxy_detected = True
            
            # Check HTTPS_PROXY env var
            if not proxy_detected:
                import os
                https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
                if https_proxy:
                    proxy_info = f"HTTPS_PROXY env var: {https_proxy}"
                    proxy_detected = True
            
            if not proxy_detected:
                proxy_info = "Not set"
            
            logger.error("=" * 70)
            logger.error(f"❌ HTTPX Request #{request_id} FAILED:")
            logger.error(f"   Method: {method}")
            logger.error(f"   URL: {url}")
            
            # Better proxy detection
            proxy_detected = False
            proxy_str = "Not set"
            if proxy_info and proxy_info != "Not set":
                proxy_detected = True
                proxy_str = str(proxy_info)
                if len(proxy_str) > 50:
                    proxy_str = proxy_str[:47] + "..."
            else:
                # Check transport for proxy
                if hasattr(self, 'transport'):
                    transport = self.transport
                    if hasattr(transport, '_proxy'):
                        proxy_detected = True
                        proxy_str = str(transport._proxy)[:50]
                    elif hasattr(transport, '_pool') and hasattr(transport._pool, '_proxy'):
                        proxy_detected = True
                        proxy_str = "Set in transport pool"
            
            logger.error(f"   Proxy configured: {proxy_detected}")
            logger.error(f"   Proxy info: {proxy_str}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)[:300]}")
            
            # Check if it's a Cloudflare block or proxy auth issue
            error_str = str(e).lower()
            if "403" in error_str:
                if "proxy" in error_str:
                    logger.error("   ⚠️  PROXY RETURNED 403 - Possible authentication issue or proxy IP blocked")
                else:
                    logger.error("   ⚠️  CLOUDflare BLOCKING DETECTED (403 Forbidden)")
            elif "cloudflare" in error_str or "blocked" in error_str:
                logger.error("   ⚠️  CLOUDflare BLOCKING DETECTED")
            elif "401" in error_str or "unauthorized" in error_str:
                logger.error("   ⚠️  PROXY AUTHENTICATION FAILED - Check username/password")
            
            import traceback
            logger.error(f"   Full traceback:\n{traceback.format_exc()}")
            logger.error("=" * 70)
            raise
    
    httpx.Client.request = _debug_request
    logger.info("✅ Debug wrapper added to httpx.Client.request (will log all requests)")
