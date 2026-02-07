"""
Vig v1 Bet Manager — Place bets and track settlements.
"""
import logging
import random
from datetime import datetime, timezone
from typing import Optional

from config import Config
from db import Database, BetRecord
from scanner import MarketCandidate
from snowball import Snowball

logger = logging.getLogger("vig.bets")


class BetManager:
    def __init__(self, config, db, snowball, clob_client=None):
        self.config = config
        self.db = db
        self.snowball = snowball
        self.clob_client = clob_client
        self._cloudflare_error_logged = False  # Track if we've already logged Cloudflare error this window

    def place_bets(self, candidates, window_id, clip_multiplier=1.0):
        # Reset Cloudflare error flag for new window
        self._cloudflare_error_logged = False
        bets = []
        
        # Get current balance for live trading
        available_balance = None
        if not self.config.paper_mode and self.clob_client:
            try:
                from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
                params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
                balance_info = self.clob_client.get_balance_allowance(params)
                available_balance = float(balance_info.get("balance", 0)) / 1e6  # USDC.e has 6 decimals
                logger.info(f"Available CLOB balance: ${available_balance:.2f}")
            except Exception as e:
                logger.warning(f"Could not check balance: {e}")
        
        for market in candidates:
            base_clip = self.snowball.get_clip_for_market(
                max_clip_for_volume=market.max_clip or self.config.max_clip)
            clip = base_clip * clip_multiplier
            if clip < 1.0:
                continue

            # Check balance before placing bet (live mode only)
            if not self.config.paper_mode and available_balance is not None:
                if available_balance < clip:
                    logger.warning(f"Insufficient balance (${available_balance:.2f}) for clip ${clip:.2f} — stopping this window")
                    break
                # Update available balance after each bet
                available_balance -= clip

            size = clip / market.fav_price
            bet = BetRecord(
                window_id=window_id, platform="polymarket",
                market_id=market.market_id, condition_id=market.condition_id,
                market_question=market.question, token_id=market.fav_token_id,
                side=market.fav_side, price=market.fav_price, amount=clip, size=size,
                placed_at=datetime.now(timezone.utc).isoformat(),
                result="pending", paper=self.config.paper_mode,
            )

            if self.config.paper_mode:
                bet.order_id = f"paper_{window_id}_{market.market_id}"
                logger.info(f"PAPER: {bet.side} {market.question[:50]} @ ${bet.price:.2f} -- ${bet.amount:.2f}")
            else:
                order_id = self._place_live_order(market, clip, size)
                if not order_id:
                    # Order failed - already logged in _place_live_order
                    continue
                bet.order_id = order_id
                logger.info(f"LIVE: {bet.side} {market.question[:50]} @ ${bet.price:.2f} -- ${bet.amount:.2f}")

            bet.id = self.db.insert_bet(bet)
            bets.append(bet)

        logger.info(f"Placed {len(bets)} bets for window {window_id}")
        return bets

    def _place_live_order(self, market, amount, size):
        if not self.clob_client:
            return None
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY
            order_args = OrderArgs(price=market.fav_price, size=size,
                                   side=BUY, token_id=market.fav_token_id)
            signed_order = self.clob_client.create_order(order_args)
            # Use FAK (Fill and Kill) - fills as much as possible, cancels remainder
            # Better for immediate execution on expiring markets
            resp = self.clob_client.post_order(signed_order, OrderType.FAK)
            if isinstance(resp, dict):
                return resp.get("orderID", resp.get("id", str(resp)))
            return str(resp)
        except Exception as e:
            error_str = str(e)
            # Log the actual error for debugging
            logger.error(f"Order failed: {e}")
            import traceback
            logger.debug(f"Order error traceback: {traceback.format_exc()}")
            return None

    def settle_bets(self, window_id):
        pending = self.db.get_pending_bets(window_id)
        if not pending:
            return {"settled": 0, "wins": 0, "losses": 0, "profit": 0}

        wins = losses = 0
        total_profit = total_returned = 0.0
        settled = 0

        for bet in pending:
            if self.config.paper_mode:
                result, payout = self._simulate_settlement(bet)
            else:
                result, payout = self._check_live_settlement(bet)

            if result == "pending":
                continue

            profit = payout - bet.amount if result == "won" else -bet.amount
            
            # If won, try to sell the position to convert shares back to cash
            if result == "won" and not self.config.paper_mode and self.clob_client:
                sell_success = self._sell_winning_position(bet)
                if not sell_success:
                    logger.warning(f"  ⚠️  Could not sell winning position for bet {bet.id} - shares may need manual redemption")
            
            self.db.update_bet_result(bet.id, result, payout, profit)

            if result == "won":
                wins += 1
                total_returned += payout
            else:
                losses += 1
            total_profit += profit
            settled += 1

            emoji = "W" if result == "won" else "L"
            logger.info(f"  [{emoji}] {bet.side} {bet.market_question[:40]}")

        return {"settled": settled, "wins": wins, "losses": losses,
                "profit": total_profit, "returned": total_returned,
                "still_pending": len(pending) - settled}

    def _simulate_settlement(self, bet):
        base_prob = bet.price
        edge_bonus = 0.05
        actual_prob = min(0.98, base_prob + edge_bonus)
        if random.random() < actual_prob:
            return "won", bet.amount / bet.price
        return "lost", 0.0

    def _check_live_settlement(self, bet):
        # Settlement check doesn't require CLOB client - just checks Gamma API
        try:
            import httpx, json
            logger.debug(f"[SETTLEMENT] Fetching market {bet.market_id} for bet {bet.id}")
            resp = httpx.get(f"{self.config.gamma_url}/markets/{bet.market_id}", timeout=10)
            if resp.status_code != 200:
                logger.debug(f"[SETTLEMENT] Market {bet.market_id} API returned {resp.status_code}")
                return "pending", 0.0
            market = resp.json()
            
            outcome_prices = market.get("outcomePrices", "")
            market_closed = market.get("closed", False)
            logger.debug(f"[SETTLEMENT] Market {bet.market_id}: closed={market_closed}, prices={outcome_prices[:50] if outcome_prices else 'None'}")
            
            if not outcome_prices:
                logger.debug(f"[SETTLEMENT] No outcome prices for market {bet.market_id}")
                return "pending", 0.0
            
            # Parse prices - handle both string and list formats
            if isinstance(outcome_prices, list):
                prices = [float(p) for p in outcome_prices]
            elif outcome_prices.startswith("["):
                prices = json.loads(outcome_prices)
                prices = [float(p) for p in prices]
            else:
                prices = outcome_prices.split(",")
                prices = [float(p.strip().strip('"')) for p in prices]

            idx = 0 if bet.side == "YES" else 1
            winning_price = prices[idx] if len(prices) > idx else 0
            
            logger.debug(f"[SETTLEMENT] Bet {bet.id} ({bet.side}): winning_price={winning_price:.4f}")
            
            # Check if market is resolved (either closed OR prices show clear resolution)
            # Polymarket sometimes shows resolved prices before marking market as closed
            clearly_resolved = winning_price >= 0.95 or winning_price <= 0.05
            
            if market_closed or clearly_resolved:
                if winning_price >= 0.95:
                    logger.debug(f"[SETTLEMENT] Bet {bet.id} WON (price {winning_price:.4f} >= 0.95)")
                    return "won", bet.size
                elif winning_price <= 0.05:
                    logger.debug(f"[SETTLEMENT] Bet {bet.id} LOST (price {winning_price:.4f} <= 0.05)")
                    return "lost", 0.0
            
            logger.debug(f"[SETTLEMENT] Bet {bet.id} still pending (price {winning_price:.4f} not clearly resolved)")
            return "pending", 0.0
        except Exception as e:
            logger.error(f"[SETTLEMENT] Settlement check failed for bet {bet.id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "pending", 0.0

    def _sell_winning_position(self, bet):
        """
        Attempt to sell winning position back to market to convert shares to cash.
        Returns True if successful, False otherwise.
        """
        if not bet.token_id:
            logger.warning(f"[SELL] Bet {bet.id} has no token_id - cannot sell")
            return False
        
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import SELL
            
            # Calculate shares owned
            shares = bet.size / bet.price if bet.price > 0 else 0
            if shares <= 0:
                logger.warning(f"[SELL] Bet {bet.id} has invalid shares calculation")
                return False
            
            logger.info(f"[SELL] Attempting to sell {shares:.2f} shares for bet {bet.id}")
            
            # Try selling at 0.99 (should fill at market price ~$1.00 for resolved markets)
            # Use FOK (Fill-or-Kill) for immediate execution
            order = self.clob_client.create_order(OrderArgs(
                token_id=bet.token_id,
                price=0.99,
                size=round(shares, 2),
                side=SELL
            ))
            
            response = self.clob_client.post_order(order, OrderType.FOK)
            
            # Check if order was successful
            if isinstance(response, dict):
                order_id = response.get('orderID') or response.get('id')
                if order_id:
                    logger.info(f"[SELL] ✅ Successfully placed sell order {order_id} for bet {bet.id}")
                    return True
                else:
                    logger.warning(f"[SELL] ⚠️  Sell order response unclear: {response}")
                    return False
            else:
                # Response might be a string order ID
                logger.info(f"[SELL] ✅ Sell order placed: {response}")
                return True
                
        except Exception as e:
            # Don't fail the settlement if sell fails - log and continue
            # The position might be on a closed market that needs redemption instead
            logger.warning(f"[SELL] ❌ Could not sell position for bet {bet.id}: {e}")
            return False
