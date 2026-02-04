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

    def place_bets(self, candidates, window_id, clip_multiplier=1.0):
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
                market_id=market.market_id, market_question=market.question,
                token_id=market.fav_token_id, side=market.fav_side,
                price=market.fav_price, amount=clip, size=size,
                placed_at=datetime.now(timezone.utc).isoformat(),
                result="pending", paper=self.config.paper_mode,
            )

            if self.config.paper_mode:
                bet.order_id = f"paper_{window_id}_{market.market_id}"
                logger.info(f"PAPER: {bet.side} {market.question[:50]} @ ${bet.price:.2f} -- ${bet.amount:.2f}")
            else:
                order_id = self._place_live_order(market, clip, size)
                if not order_id:
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
            resp = self.clob_client.post_order(signed_order, OrderType.GTC)
            if isinstance(resp, dict):
                return resp.get("orderID", resp.get("id", str(resp)))
            return str(resp)
        except Exception as e:
            logger.error(f"Order failed: {e}")
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
            resp = httpx.get(f"{self.config.gamma_url}/markets/{bet.market_id}", timeout=10)
            if resp.status_code != 200:
                return "pending", 0.0
            market = resp.json()
            
            outcome_prices = market.get("outcomePrices", "")
            if not outcome_prices:
                return "pending", 0.0
            if outcome_prices.startswith("["):
                prices = json.loads(outcome_prices)
            else:
                prices = outcome_prices.split(",")
            prices = [float(p.strip().strip('"')) for p in prices]

            idx = 0 if bet.side == "YES" else 1
            winning_price = prices[idx] if len(prices) > idx else 0
            
            # Check if market is resolved (either closed OR prices show clear resolution)
            # Polymarket sometimes shows resolved prices before marking market as closed
            market_closed = market.get("closed", False)
            clearly_resolved = winning_price >= 0.95 or winning_price <= 0.05
            
            if market_closed or clearly_resolved:
                if winning_price >= 0.95:
                    return "won", bet.size
                elif winning_price <= 0.05:
                    return "lost", 0.0
            
            return "pending", 0.0
        except Exception as e:
            logger.debug(f"Settlement check failed: {e}")
            return "pending", 0.0
