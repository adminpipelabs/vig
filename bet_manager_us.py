"""
Vig v2 — Bet Manager for Polymarket US API
Places buy orders, profit target sells, and force-exits before expiry
"""
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from db import Database, BetRecord
from scanner import MarketCandidate
from snowball import Snowball
from auth import PolymarketUSAuth, get_auth_from_env
from orders import PolymarketUSOrders, ORDER_INTENT_BUY_LONG, ORDER_INTENT_SELL_LONG, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GOOD_TILL_CANCEL
from positions import PositionTracker, Position

logger = logging.getLogger("vig.bets.us")


class BetManagerUS:
    """Bet manager using Polymarket US API"""
    
    def __init__(self, config: Config, db: Database, snowball: Snowball, position_tracker: PositionTracker):
        self.config = config
        self.db = db
        self.snowball = snowball
        self.position_tracker = position_tracker
        
        # Initialize US API auth and orders
        if config.use_us_api and not config.paper_mode:
            auth = get_auth_from_env()
            if not auth:
                logger.error("❌ Failed to initialize Polymarket US API auth")
                self.orders_client = None
            else:
                self.orders_client = PolymarketUSOrders(auth)
                logger.info("✅ Polymarket US API initialized")
        else:
            self.orders_client = None
    
    def place_bets(self, candidates: List[MarketCandidate], window_id: int, clip_multiplier: float = 1.0) -> List[BetRecord]:
        """
        Place bets using US API strategy:
        1. Buy favorite at current price
        2. Place profit target sell order
        3. Track position for force-exit before expiry
        """
        if not self.orders_client and not self.config.paper_mode:
            logger.warning("US API not available - cannot place bets")
            return []
        
        bets = []
        
        # Calculate clips upfront
        market_clips = []
        for market in candidates:
            base_clip = self.snowball.get_clip_for_market(
                max_clip_for_volume=market.max_clip or self.config.max_clip
            )
            clip = base_clip * clip_multiplier
            if clip >= 1.0:
                market_clips.append((market, clip))
        
        logger.info(f"Placing bets on {len(market_clips)} markets using US API")
        
        def place_single_bet(market_clip_tuple):
            market, clip = market_clip_tuple
            try:
                # Calculate quantity (shares)
                quantity = int(clip / market.fav_price)
                if quantity < 1:
                    logger.debug(f"Skipping {market.slug}: quantity too small ({quantity})")
                    return None
                
                # Calculate profit target price
                profit_target_price = min(0.99, market.fav_price + self.config.profit_target_pct)
                
                if self.config.paper_mode:
                    # Paper mode - just create bet record
                    bet = BetRecord(
                        window_id=window_id,
                        platform="polymarket",
                        market_id=market.market_id,
                        condition_id=market.condition_id,
                        market_question=market.question,
                        token_id=market.fav_token_id,
                        side=market.fav_side,
                        price=market.fav_price,
                        amount=clip,
                        size=quantity,
                        placed_at=datetime.now(timezone.utc).isoformat(),
                        result="pending",
                        paper=True,
                        order_id=f"paper_{window_id}_{market.market_id}"
                    )
                    bet.id = self.db.insert_bet(bet)
                    
                    # Track position in paper mode
                    self.position_tracker.add_position(
                        market_slug=market.slug,
                        market_question=market.question,
                        buy_order_id=bet.order_id,
                        quantity=quantity,
                        buy_price=market.fav_price,
                        sell_price=profit_target_price,
                        expiry_time=market.end_date
                    )
                    
                    logger.info(f"PAPER: {market.fav_side} {market.question[:50]} @ ${market.fav_price:.2f} -- ${clip:.2f}")
                    return bet
                
                # Live mode - place orders via US API
                # Step 1: Place buy order
                buy_order = self.orders_client.place_order(
                    market_slug=market.slug,
                    intent=ORDER_INTENT_BUY_LONG,
                    price=market.fav_price,
                    quantity=quantity,
                    order_type=ORDER_TYPE_LIMIT,
                    tif=TIME_IN_FORCE_GOOD_TILL_CANCEL
                )
                
                if not buy_order:
                    logger.warning(f"Buy order failed for {market.slug}")
                    return None
                
                buy_order_id = buy_order.get("orderId") or buy_order.get("id") or str(buy_order)
                
                # Step 2: Place profit target sell order
                sell_order = self.orders_client.place_order(
                    market_slug=market.slug,
                    intent=ORDER_INTENT_SELL_LONG,
                    price=profit_target_price,
                    quantity=quantity,
                    order_type=ORDER_TYPE_LIMIT,
                    tif=TIME_IN_FORCE_GOOD_TILL_CANCEL
                )
                
                sell_order_id = None
                if sell_order:
                    sell_order_id = sell_order.get("orderId") or sell_order.get("id") or str(sell_order)
                    logger.info(f"💰 Profit target placed: sell {quantity} @ ${profit_target_price:.2f}")
                
                # Create bet record
                bet = BetRecord(
                    window_id=window_id,
                    platform="polymarket",
                    market_id=market.market_id,
                    condition_id=market.condition_id,
                    market_question=market.question,
                    token_id=market.fav_token_id,
                    side=market.fav_side,
                    price=market.fav_price,
                    amount=clip,
                    size=quantity,
                    placed_at=datetime.now(timezone.utc).isoformat(),
                    result="pending",
                    paper=False,
                    order_id=buy_order_id
                )
                bet.id = self.db.insert_bet(bet)
                
                # Track position
                self.position_tracker.add_position(
                    market_slug=market.slug,
                    market_question=market.question,
                    buy_order_id=buy_order_id,
                    sell_order_id=sell_order_id,
                    quantity=quantity,
                    buy_price=market.fav_price,
                    sell_price=profit_target_price,
                    expiry_time=market.end_date
                )
                
                logger.info(f"LIVE: {market.fav_side} {market.question[:50]} @ ${market.fav_price:.2f} -- ${clip:.2f}")
                return bet
                
            except Exception as e:
                logger.error(f"Error placing bet on {market.slug}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
        
        # Place bets in parallel
        max_workers = min(20, len(market_clips))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(place_single_bet, mc) for mc in market_clips]
            for future in as_completed(futures):
                bet = future.result()
                if bet:
                    bets.append(bet)
        
        logger.info(f"Placed {len(bets)} bets using US API")
        return bets
    
    def check_and_close_positions(self):
        """Check positions and force-close those expiring soon"""
        if not self.orders_client:
            return
        
        positions_to_close = self.position_tracker.get_positions_needing_exit(
            minutes_before_expiry=self.config.force_exit_minutes_before_expiry
        )
        
        for position in positions_to_close:
            logger.warning(f"🚨 Force closing position before expiry: {position.market_slug} ({position.minutes_to_expiry():.1f}m remaining)")
            
            # Close position via API
            result = self.orders_client.close_position(position.market_slug)
            
            if result:
                self.position_tracker.mark_closed(position.market_slug, "force_exit")
                logger.info(f"✅ Position force-closed: {position.market_slug}")
            else:
                logger.error(f"❌ Failed to force-close position: {position.market_slug}")
    
    def check_profit_targets(self):
        """Check if profit target sell orders have been filled"""
        if not self.orders_client:
            return
        
        open_positions = self.position_tracker.get_open_positions()
        
        for position in open_positions:
            if not position.sell_order_id:
                continue
            
            # Check if sell order is still open
            open_orders = self.orders_client.get_open_orders(position.market_slug)
            sell_order_ids = [o.get("orderId") or o.get("id") for o in open_orders]
            
            # If sell order not in open orders, it was filled
            if position.sell_order_id not in sell_order_ids:
                self.position_tracker.mark_profit_target_filled(position.market_slug)
                logger.info(f"💰 Profit target filled: {position.market_slug}")
    
    def close(self):
        """Cleanup"""
        if self.orders_client:
            self.orders_client.close()
