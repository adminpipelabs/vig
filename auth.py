"""
Vig v2 — Polymarket US API Authentication (Ed25519)
"""
import os
import time
import base64
import hashlib
from typing import Dict, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import logging

logger = logging.getLogger("vig.auth")


class PolymarketUSAuth:
    """Ed25519 authentication for Polymarket US API"""
    
    def __init__(self, key_id: str, private_key: str):
        """
        Initialize auth with Ed25519 keypair.
        
        Args:
            key_id: API key ID (UUID from Polymarket developer portal)
            private_key: Ed25519 private key (base64 or PEM format)
        """
        self.key_id = key_id
        self.private_key = self._load_private_key(private_key)
    
    def _load_private_key(self, key_str: str) -> Ed25519PrivateKey:
        """
        Load Ed25519 private key from string.
        Handles multiple formats:
        - Hex: 64 hex characters (32 bytes)
        - Base64: 44 characters (32 bytes) or longer
        - PEM: Full PEM format with headers
        - 64-byte keys: If key is 64 bytes (private+public), use first 32 bytes
        """
        # Strip whitespace
        key_str = key_str.strip()
        
        try:
            # Try hex format (64 hex chars = 32 bytes)
            if len(key_str) == 64 and all(c in '0123456789abcdefABCDEF' for c in key_str):
                key_bytes = bytes.fromhex(key_str)
                if len(key_bytes) == 32:
                    return Ed25519PrivateKey.from_private_bytes(key_bytes)
            
            # Try base64 format
            try:
                key_bytes = base64.b64decode(key_str, validate=True)
                
                # If exactly 32 bytes, use it
                if len(key_bytes) == 32:
                    return Ed25519PrivateKey.from_private_bytes(key_bytes)
                
                # If 64 bytes, might be private+public concatenated - use first 32 bytes
                elif len(key_bytes) == 64:
                    logger.warning("Key is 64 bytes - using first 32 bytes as private key")
                    private_key_bytes = key_bytes[:32]
                    return Ed25519PrivateKey.from_private_bytes(private_key_bytes)
                
                # If other length, log warning but try first 32 bytes
                elif len(key_bytes) > 32:
                    logger.warning(f"Key decoded to {len(key_bytes)} bytes - using first 32 bytes")
                    private_key_bytes = key_bytes[:32]
                    return Ed25519PrivateKey.from_private_bytes(private_key_bytes)
                
            except Exception as e:
                logger.debug(f"Base64 decode failed: {e}")
            
            # Try PEM format
            try:
                if "BEGIN" in key_str or "PRIVATE KEY" in key_str:
                    key_obj = serialization.load_pem_private_key(
                        key_str.encode(),
                        password=None
                    )
                    if isinstance(key_obj, Ed25519PrivateKey):
                        return key_obj
            except Exception as e:
                logger.debug(f"PEM decode failed: {e}")
            
            # Final attempt: try base64 decode without validation
            try:
                key_bytes = base64.b64decode(key_str)
                if len(key_bytes) >= 32:
                    # Use first 32 bytes
                    private_key_bytes = key_bytes[:32] if len(key_bytes) > 32 else key_bytes
                    return Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            except:
                pass
            
            raise ValueError(
                f"Invalid Ed25519 private key format. "
                f"Key length: {len(key_str)} chars. "
                f"Expected: 64 hex chars, 44 base64 chars (32 bytes), or PEM format. "
                f"If key is longer, it might be concatenated (private+public) - we'll use first 32 bytes."
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise ValueError(f"Invalid Ed25519 private key format: {e}")
    
    def sign_message(self, message: bytes) -> bytes:
        """Sign message with Ed25519 private key"""
        return self.private_key.sign(message)
    
    def get_auth_headers(self, method: str, path: str) -> Dict[str, str]:
        """
        Generate authentication headers for API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /v1/orders)
        
        Returns:
            Dict with X-PM-Access-Key, X-PM-Timestamp, X-PM-Signature headers
        """
        # Timestamp in milliseconds
        timestamp = str(int(time.time() * 1000))
        
        # Message format: timestamp + method + path (per Polymarket API docs)
        # Method should be uppercase (GET, POST, etc.)
        method_upper = method.upper()
        message = f"{timestamp}{method_upper}{path}".encode('utf-8')
        
        # Sign message with Ed25519 private key
        signature_bytes = self.sign_message(message)
        signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
        
        # Debug logging (first time only to avoid spam)
        if not hasattr(self, '_logged_auth_debug'):
            logger.info(f"🔐 Auth debug: key_id={self.key_id[:8]}..., timestamp={timestamp}, method={method.upper()}, path={path}")
            logger.info(f"🔐 Auth debug: signature (first 20 chars)={signature_b64[:20]}...")
            self._logged_auth_debug = True
        
        return {
            "X-PM-Access-Key": self.key_id,
            "X-PM-Timestamp": timestamp,
            "X-PM-Signature": signature_b64,
            "Content-Type": "application/json"
        }


def get_auth_from_env() -> Optional[PolymarketUSAuth]:
    """Load auth from environment variables"""
    key_id = os.getenv("POLYMARKET_US_KEY_ID")
    private_key = os.getenv("POLYMARKET_US_PRIVATE_KEY")
    
    if not key_id or not private_key:
        logger.warning("⚠️  POLYMARKET_US_KEY_ID or POLYMARKET_US_PRIVATE_KEY not set")
        return None
    
    # Strip whitespace from key ID (common issue)
    key_id = key_id.strip()
    
    # Validate key ID format (should be UUID)
    if len(key_id) != 36 or key_id.count('-') != 4:
        logger.error(f"❌ Invalid POLYMARKET_US_KEY_ID format: '{key_id}' (expected UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)")
        return None
    
    # Log key ID for debugging (full ID since it's not sensitive)
    logger.info(f"🔑 Loading Polymarket US API auth")
    logger.info(f"   Key ID: {key_id}")
    logger.info(f"   Key ID length: {len(key_id)} chars")
    logger.info(f"   Private key length: {len(private_key)} chars")
    logger.info(f"   Private key (first 20): {private_key[:20]}...")
    logger.info(f"   Private key (last 20): ...{private_key[-20:]}")
    
    # Verify private key matches expected format
    try:
        import base64
        decoded = base64.b64decode(private_key.strip())
        logger.info(f"   Private key decoded: {len(decoded)} bytes")
        if len(decoded) >= 32:
            logger.info(f"   ✅ Will use first 32 bytes for Ed25519")
        else:
            logger.error(f"   ❌ Private key too short: {len(decoded)} bytes (need 32)")
    except Exception as e:
        logger.error(f"   ❌ Failed to decode private key: {e}")
    
    try:
        auth = PolymarketUSAuth(key_id, private_key)
        logger.info("✅ Polymarket US API auth initialized successfully")
        return auth
    except Exception as e:
        logger.error(f"❌ Failed to initialize auth: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
