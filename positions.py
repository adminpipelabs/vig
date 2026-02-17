"""
Vig v2 — Position Tracking for Polymarket US API
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger("vig.positions")


@dataclass
class Position:
    """Track an open position"""
    market_slug: str
    market_question: str
    buy_order_id: str
    sell_order_id: Optional[str] = None
    quantity: int = 0
    buy_price: float = 0.0
    sell_price: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiry_time: Optional[datetime] = None
    status: str = "open"  # open, profit_target_filled, closed, expired
    
    def minutes_to_expiry(self) -> Optional[float]:
        """Calculate minutes until expiry"""
        if not self.expiry_time:
            return None
        now = datetime.now(timezone.utc)
        delta = self.expiry_time - now
        return delta.total_seconds() / 60
    
    def should_force_exit(self, minutes_before_expiry: int = 10) -> bool:
        """Check if position should be force-closed before expiry"""
        if not self.expiry_time:
            return False
        mins = self.minutes_to_expiry()
        if mins is None:
            return False
        return mins < minutes_before_expiry and self.status == "open"


class PositionTracker:
    """Track all open positions"""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}  # market_slug -> Position
    
    def add_position(
        self,
        market_slug: str,
        market_question: str,
        buy_order_id: str,
        quantity: int,
        buy_price: float,
        sell_price: float,
        expiry_time: Optional[datetime] = None,
        sell_order_id: Optional[str] = None
    ):
        """Add new position"""
        position = Position(
            market_slug=market_slug,
            market_question=market_question,
            buy_order_id=buy_order_id,
            sell_order_id=sell_order_id,
            quantity=quantity,
            buy_price=buy_price,
            sell_price=sell_price,
            expiry_time=expiry_time
        )
        self.positions[market_slug] = position
        logger.info(f"📊 Position opened: {market_slug} ({quantity} @ ${buy_price:.2f})")
    
    def update_sell_order(self, market_slug: str, sell_order_id: str):
        """Update sell order ID after placing profit target"""
        if market_slug in self.positions:
            self.positions[market_slug].sell_order_id = sell_order_id
    
    def mark_profit_target_filled(self, market_slug: str):
        """Mark position as closed via profit target"""
        if market_slug in self.positions:
            self.positions[market_slug].status = "profit_target_filled"
            logger.info(f"💰 Profit target filled: {market_slug}")
    
    def mark_closed(self, market_slug: str, reason: str = "force_exit"):
        """Mark position as closed"""
        if market_slug in self.positions:
            self.positions[market_slug].status = "closed"
            logger.info(f"🔒 Position closed ({reason}): {market_slug}")
    
    def remove_position(self, market_slug: str):
        """Remove position from tracker"""
        if market_slug in self.positions:
            del self.positions[market_slug]
    
    def get_position(self, market_slug: str) -> Optional[Position]:
        """Get position by market slug"""
        return self.positions.get(market_slug)
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions.values() if p.status == "open"]
    
    def get_positions_needing_exit(self, minutes_before_expiry: int = 10) -> List[Position]:
        """Get positions that need force exit before expiry"""
        return [
            p for p in self.get_open_positions()
            if p.should_force_exit(minutes_before_expiry)
        ]
