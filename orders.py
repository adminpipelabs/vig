"""
Vig v2 — Polymarket US API Order Functions
"""
import httpx
import logging
from typing import Dict, Optional, List
from auth import PolymarketUSAuth

logger = logging.getLogger("vig.orders")

BASE_URL = "https://api.polymarket.us"

# Order types
ORDER_TYPE_LIMIT = "ORDER_TYPE_LIMIT"
ORDER_TYPE_MARKET = "ORDER_TYPE_MARKET"

# Order intents
ORDER_INTENT_BUY_LONG = "ORDER_INTENT_BUY_LONG"
ORDER_INTENT_SELL_LONG = "ORDER_INTENT_SELL_LONG"
ORDER_INTENT_BUY_SHORT = "ORDER_INTENT_BUY_SHORT"
ORDER_INTENT_SELL_SHORT = "ORDER_INTENT_SELL_SHORT"

# Time in force
TIME_IN_FORCE_GOOD_TILL_CANCEL = "TIME_IN_FORCE_GOOD_TILL_CANCEL"
TIME_IN_FORCE_GOOD_TILL_DATE = "TIME_IN_FORCE_GOOD_TILL_DATE"
TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "TIME_IN_FORCE_IMMEDIATE_OR_CANCEL"
TIME_IN_FORCE_FILL_OR_KILL = "TIME_IN_FORCE_FILL_OR_KILL"

MANUAL_ORDER_INDICATOR_AUTOMATIC = "MANUAL_ORDER_INDICATOR_AUTOMATIC"


class PolymarketUSOrders:
    """Order management for Polymarket US API"""
    
    def __init__(self, auth: PolymarketUSAuth):
        self.auth = auth
        self.client = httpx.Client(timeout=30.0)
    
    def place_order(
        self,
        market_slug: str,
        intent: str,
        price: float,
        quantity: int,
        order_type: str = ORDER_TYPE_LIMIT,
        tif: str = TIME_IN_FORCE_GOOD_TILL_CANCEL,
        slippage_tolerance: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Place order via US API.
        
        Args:
            market_slug: Market slug (e.g., "nyc-temp-above-50-feb-17")
            intent: ORDER_INTENT_BUY_LONG, ORDER_INTENT_SELL_LONG, etc.
            price: Price for YES side (0.001-0.999 per API spec)
            quantity: Number of shares
            order_type: ORDER_TYPE_LIMIT or ORDER_TYPE_MARKET
            tif: Time in force
            slippage_tolerance: For market orders (optional)
        
        Returns:
            Order response dict or None if failed
        
        Note: price.value always represents YES/long side price, even when buying NO.
        Per API docs: "price.value always refers to the long side's price"
        """
        # Validate price per API spec: must be between 0.001 and 0.999
        if price < 0.001 or price > 0.999:
            logger.error(f"❌ Invalid price {price:.3f}: must be between 0.001 and 0.999")
            return None
        
        # Validate quantity
        if quantity < 1:
            logger.error(f"❌ Invalid quantity {quantity}: must be >= 1")
            return None
        
        path = "/v1/orders"
        headers = self.auth.get_auth_headers("POST", path)
        
        # Format price as string per API spec
        price_str = f"{price:.3f}".rstrip('0').rstrip('.')
        if price_str == "1":
            price_str = "0.999"  # Cap at max allowed
        
        payload = {
            "marketSlug": market_slug,
            "type": order_type,
            "intent": intent,
            "price": {
                "value": price_str,
                "currency": "USD"
            },
            "quantity": quantity,
            "tif": tif,
            "manualOrderIndicator": MANUAL_ORDER_INDICATOR_AUTOMATIC
        }
        
        if order_type == ORDER_TYPE_MARKET and slippage_tolerance:
            payload["slippageTolerance"] = slippage_tolerance
        
        try:
            # Log request details for debugging (first time only)
            if not hasattr(self, '_logged_request_debug'):
                logger.info(f"🌐 API Request Debug:")
                logger.info(f"   URL: {BASE_URL}{path}")
                logger.info(f"   Method: POST")
                logger.info(f"   Headers: X-PM-Access-Key={headers.get('X-PM-Access-Key', 'MISSING')[:8]}...")
                logger.info(f"   Headers: X-PM-Timestamp={headers.get('X-PM-Timestamp', 'MISSING')}")
                logger.info(f"   Headers: X-PM-Signature={headers.get('X-PM-Signature', 'MISSING')[:20]}...")
                self._logged_request_debug = True
            
            response = self.client.post(
                f"{BASE_URL}{path}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ Order placed: {intent} {quantity} @ ${price:.2f} on {market_slug}")
            return result
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            logger.error(f"❌ Order failed ({e.response.status_code}): {error_text}")
            
            # If 401, log detailed auth info
            if e.response.status_code == 401:
                logger.error(f"🔐 Authentication Debug:")
                logger.error(f"   Key ID sent: {headers.get('X-PM-Access-Key', 'MISSING')}")
                logger.error(f"   Timestamp sent: {headers.get('X-PM-Timestamp', 'MISSING')}")
                logger.error(f"   Error: {error_text}")
                logger.error(f"   ⚠️  Verify POLYMARKET_US_KEY_ID matches your Polymarket dashboard exactly")
            
            return None
        except Exception as e:
            logger.error(f"❌ Order error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def close_position(self, market_slug: str) -> Optional[Dict]:
        """
        Close entire position at market price.
        
        Args:
            market_slug: Market slug
        
        Returns:
            Close position response or None if failed
        """
        path = "/v1/order/close-position"
        headers = self.auth.get_auth_headers("POST", path)
        
        payload = {"marketSlug": market_slug}
        
        try:
            response = self.client.post(
                f"{BASE_URL}{path}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ Position closed: {market_slug}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Close position failed ({e.response.status_code}): {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Close position error: {e}")
            return None
    
    def get_open_orders(self, market_slug: Optional[str] = None) -> List[Dict]:
        """
        Get open orders.
        
        Args:
            market_slug: Optional filter by market
        
        Returns:
            List of open orders
        """
        path = "/v1/orders/open"
        if market_slug:
            path += f"?marketSlug={market_slug}"
        
        headers = self.auth.get_auth_headers("GET", path)
        
        try:
            response = self.client.get(
                f"{BASE_URL}{path}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"❌ Get open orders error: {e}")
            return []
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel specific order"""
        path = f"/v1/order/{order_id}/cancel"
        headers = self.auth.get_auth_headers("POST", path)
        
        try:
            response = self.client.post(
                f"{BASE_URL}{path}",
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"✅ Order canceled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Cancel order error: {e}")
            return False
    
    def cancel_all_orders(self, market_slug: Optional[str] = None) -> bool:
        """Cancel all open orders"""
        path = "/v1/orders/open/cancel"
        headers = self.auth.get_auth_headers("POST", path)
        
        payload = {}
        if market_slug:
            payload["marketSlug"] = market_slug
        
        try:
            response = self.client.post(
                f"{BASE_URL}{path}",
                headers=headers,
                json=payload if payload else None
            )
            response.raise_for_status()
            logger.info(f"✅ All orders canceled")
            return True
        except Exception as e:
            logger.error(f"❌ Cancel all orders error: {e}")
            return False
    
    def preview_order(
        self,
        market_slug: str,
        intent: str,
        price: float,
        quantity: int
    ) -> Optional[Dict]:
        """Preview order before placing"""
        path = "/v1/order/preview"
        headers = self.auth.get_auth_headers("POST", path)
        
        payload = {
            "marketSlug": market_slug,
            "intent": intent,
            "price": {"value": str(price), "currency": "USD"},
            "quantity": quantity
        }
        
        try:
            response = self.client.post(
                f"{BASE_URL}{path}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"❌ Preview order error: {e}")
            return None
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
