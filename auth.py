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
        """Load Ed25519 private key from string"""
        # Strip whitespace
        key_str = key_str.strip()
        
        try:
            # Try hex format (64 hex chars = 32 bytes)
            if len(key_str) == 64 and all(c in '0123456789abcdefABCDEF' for c in key_str):
                key_bytes = bytes.fromhex(key_str)
                if len(key_bytes) == 32:
                    return Ed25519PrivateKey.from_private_bytes(key_bytes)
            
            # Try base64 format (44 chars unpadded, 88 chars with padding)
            try:
                key_bytes = base64.b64decode(key_str, validate=True)
                if len(key_bytes) == 32:
                    return Ed25519PrivateKey.from_private_bytes(key_bytes)
            except:
                pass
            
            # Try PEM format
            try:
                key_obj = serialization.load_pem_private_key(
                    key_str.encode(),
                    password=None
                )
                if isinstance(key_obj, Ed25519PrivateKey):
                    return key_obj
            except:
                pass
            
            # If we get here, try to decode as base64 even if length doesn't match
            try:
                key_bytes = base64.b64decode(key_str)
                if len(key_bytes) == 32:
                    return Ed25519PrivateKey.from_private_bytes(key_bytes)
            except:
                pass
            
            raise ValueError(f"Key length is {len(key_str)} chars. Ed25519 private key must be 32 bytes (64 hex chars, 44 base64 chars, or PEM format)")
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise ValueError(f"Invalid Ed25519 private key format: {e}. Expected: 64 hex chars, base64 (44/88 chars), or PEM format")
    
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
        
        # Message format: timestamp + method + path
        message = f"{timestamp}{method.upper()}{path}".encode('utf-8')
        
        # Sign message
        signature_bytes = self.sign_message(message)
        signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
        
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
        return None
    
    try:
        return PolymarketUSAuth(key_id, private_key)
    except Exception as e:
        logger.error(f"Failed to initialize auth: {e}")
        return None
