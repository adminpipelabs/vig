#!/usr/bin/env python3
"""
Test Polymarket US API Authentication
Diagnostic script to verify key format and test authentication
"""
import os
import sys
import base64
from auth import PolymarketUSAuth, get_auth_from_env
from orders import PolymarketUSOrders

def test_key_format():
    """Test if keys are in correct format"""
    print("=" * 80)
    print("POLYMARKET US API KEY FORMAT CHECK")
    print("=" * 80)
    
    key_id = os.getenv("POLYMARKET_US_KEY_ID")
    private_key = os.getenv("POLYMARKET_US_PRIVATE_KEY")
    
    if not key_id:
        print("❌ POLYMARKET_US_KEY_ID not set")
        return False
    
    if not private_key:
        print("❌ POLYMARKET_US_PRIVATE_KEY not set")
        return False
    
    print(f"\n✅ Key ID found: {key_id[:8]}...{key_id[-4:] if len(key_id) > 12 else ''}")
    print(f"   Length: {len(key_id)} chars")
    print(f"   Format: {'✅ Valid UUID format' if len(key_id) == 36 and key_id.count('-') == 4 else '❌ Invalid UUID format'}")
    
    print(f"\n✅ Private key found: {len(private_key)} chars")
    
    # Decode private key
    try:
        decoded = base64.b64decode(private_key)
        print(f"   Decoded length: {len(decoded)} bytes")
        
        if len(decoded) == 32:
            print("   ✅ Valid 32-byte Ed25519 private key")
        elif len(decoded) >= 32:
            print(f"   ⚠️  Key is {len(decoded)} bytes - will use first 32 bytes")
        else:
            print(f"   ❌ Key too short: {len(decoded)} bytes (need 32)")
            return False
    except Exception as e:
        print(f"   ❌ Failed to decode private key: {e}")
        return False
    
    return True

def test_auth_initialization():
    """Test if auth can be initialized"""
    print("\n" + "=" * 80)
    print("AUTHENTICATION INITIALIZATION TEST")
    print("=" * 80)
    
    try:
        auth = get_auth_from_env()
        if not auth:
            print("❌ Failed to initialize auth")
            return None
        
        print("✅ Auth initialized successfully")
        print(f"   Key ID: {auth.key_id[:8]}...{auth.key_id[-4:] if len(auth.key_id) > 12 else ''}")
        return auth
    except Exception as e:
        print(f"❌ Auth initialization error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_signature_generation(auth):
    """Test signature generation"""
    print("\n" + "=" * 80)
    print("SIGNATURE GENERATION TEST")
    print("=" * 80)
    
    try:
        # Test signature generation
        headers = auth.get_auth_headers("POST", "/v1/orders")
        
        print("✅ Signature generated successfully")
        print(f"   X-PM-Access-Key: {headers['X-PM-Access-Key'][:8]}...")
        print(f"   X-PM-Timestamp: {headers['X-PM-Timestamp']}")
        print(f"   X-PM-Signature: {headers['X-PM-Signature'][:20]}...")
        
        return True
    except Exception as e:
        print(f"❌ Signature generation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_call(auth):
    """Test actual API call"""
    print("\n" + "=" * 80)
    print("API CALL TEST")
    print("=" * 80)
    
    try:
        orders_client = PolymarketUSOrders(auth)
        
        # Try to get open orders (read-only endpoint)
        print("Testing GET /v1/orders/open...")
        open_orders = orders_client.get_open_orders()
        
        print(f"✅ API call successful!")
        print(f"   Response: {open_orders}")
        return True
    except Exception as e:
        print(f"❌ API call failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n🔍 Polymarket US API Authentication Diagnostic\n")
    
    # Step 1: Check key format
    if not test_key_format():
        print("\n❌ Key format check failed. Please verify your environment variables.")
        sys.exit(1)
    
    # Step 2: Initialize auth
    auth = test_auth_initialization()
    if not auth:
        print("\n❌ Auth initialization failed.")
        sys.exit(1)
    
    # Step 3: Test signature generation
    if not test_signature_generation(auth):
        print("\n❌ Signature generation failed.")
        sys.exit(1)
    
    # Step 4: Test API call
    if not test_api_call(auth):
        print("\n❌ API call failed.")
        print("\n⚠️  If you see 'API key not found', verify:")
        print("   1. The POLYMARKET_US_KEY_ID matches your registered key on Polymarket")
        print("   2. The key was generated through the official Polymarket US developer portal")
        print("   3. The key hasn't been revoked or expired")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    main()
