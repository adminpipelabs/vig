"""
Vig v1 Scanner — Find markets expiring within the window, filter for favorites.
"""
import httpx
import json
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

from config import Config

logger = logging.getLogger("vig.scanner")


@dataclass
class MarketCandidate:
    market_id: str
    condition_id: str
    question: str
    slug: str
    category: str
    end_date: datetime
    minutes_to_expiry: float
    fav_side: str
    fav_price: float
    fav_token_id: str
    other_side: str
    other_price: float
    other_token_id: str
    volume: float
    volume_24h: float
    liquidity: float
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    max_clip: Optional[float] = None

    def __str__(self):
        return (f"{self.fav_side} {self.question[:60]} "
                f"@ ${self.fav_price:.2f} | exp {self.minutes_to_expiry:.0f}m | "
                f"vol ${self.volume:,.0f}")


class Scanner:
    def __init__(self, config: Config):
        self.config = config
        self.gamma_url = config.gamma_url
        self.client = httpx.Client(timeout=30)

    def scan(self) -> list[MarketCandidate]:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=self.config.expiry_window_minutes)

        logger.info(f"Scanning for markets expiring between "
                    f"{now.strftime('%H:%M')} and {window_end.strftime('%H:%M')} UTC")

        raw_markets = self._fetch_markets(now, window_end)
        logger.info(f"Gamma API returned {len(raw_markets)} markets in expiry window")

        candidates = []
        for market in raw_markets:
            candidate = self._parse_market(market, now)
            if candidate:
                candidates.append(candidate)
        logger.info(f"After favorite filter: {len(candidates)} qualifying markets")

        filtered = self._apply_volume_filter(candidates)
        logger.info(f"After volume filter: {len(filtered)} markets")

        # Prioritize markets expiring soon (next 15-30 min) - sort by expiry time first, then volume
        filtered.sort(key=lambda m: (m.minutes_to_expiry < 30, -m.volume, m.minutes_to_expiry))
        result = filtered[:self.config.max_bets_per_window]

        logger.info(f"Final candidates: {len(result)} markets")
        for m in result:
            logger.info(f"  -> {m}")
        return result

    def _fetch_markets(self, window_start, window_end) -> list[dict]:
        params = {
            "active": "true",
            "closed": "false",
            "end_date_min": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date_max": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 500,  # Increased to catch more markets
            "order": "volume24hr",
            "ascending": "false",
        }
        try:
            resp = self.client.get(f"{self.gamma_url}/markets", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Gamma API error: {e}")
            return []

    def _parse_market(self, market: dict, now: datetime) -> Optional[MarketCandidate]:
        try:
            market_id = market.get("id", "")
            condition_id = market.get("conditionId", "")
            question = market.get("question", "")
            slug = market.get("slug", "")
            category = market.get("category", "")
            end_date_str = market.get("endDate") or market.get("endDateIso", "")

            if not end_date_str or not question:
                return None

            end_date = self._parse_datetime(end_date_str)
            if not end_date:
                return None

            minutes_to_expiry = (end_date - now).total_seconds() / 60
            # Vig v2: Accept any market expiring in the future (no expiry window filter)
            if minutes_to_expiry <= 0:
                return None  # Only reject already-expired markets

            prices = self._parse_prices(market.get("outcomePrices", ""))
            if not prices or len(prices) < 2:
                return None
            yes_price, no_price = prices[0], prices[1]

            token_ids = self._parse_token_ids(market.get("clobTokenIds", ""))
            if not token_ids or len(token_ids) < 2:
                return None
            yes_token_id, no_token_id = token_ids[0], token_ids[1]

            volume = float(market.get("volume", 0) or 0)
            volume_24h = float(market.get("volume24hr", 0) or 0)
            liquidity = float(market.get("liquidityNum", 0) or market.get("liquidity", 0) or 0)

            if not market.get("acceptingOrders", True):
                return None
            if not market.get("enableOrderBook", True):
                return None

            # Vig v2: Accept any favorite > 50% (min_favorite_price defaults to 0.50)
            min_p = self.config.min_favorite_price

            if yes_price >= min_p:
                fav_side, fav_price, fav_token = "YES", yes_price, yes_token_id
                other_side, other_price, other_token = "NO", no_price, no_token_id
            elif no_price >= min_p:
                fav_side, fav_price, fav_token = "NO", no_price, no_token_id
                other_side, other_price, other_token = "YES", yes_price, yes_token_id
            else:
                return None  # Neither side is favorite (both < 50%)

            return MarketCandidate(
                market_id=market_id, condition_id=condition_id,
                question=question, slug=slug, category=category,
                end_date=end_date, minutes_to_expiry=minutes_to_expiry,
                fav_side=fav_side, fav_price=fav_price, fav_token_id=fav_token,
                other_side=other_side, other_price=other_price, other_token_id=other_token,
                volume=volume, volume_24h=volume_24h, liquidity=liquidity,
            )
        except Exception as e:
            logger.debug(f"Error parsing market: {e}")
            return None

    def _apply_volume_filter(self, candidates):
        # Vig v2: No volume filter - accept all candidates
        filtered = []
        for m in candidates:
            # Still calculate max_clip for risk management, but don't filter by volume
            m.max_clip = m.volume * self.config.max_volume_pct if m.volume > 0 else float('inf')
            filtered.append(m)
        return filtered

    def enrich_with_clob(self, candidates, clob_client):
        for m in candidates:
            try:
                book = clob_client.get_order_book(m.fav_token_id)
                if book and hasattr(book, 'bids') and hasattr(book, 'asks'):
                    if book.bids:
                        m.best_bid = float(book.bids[0].price)
                    if book.asks:
                        m.best_ask = float(book.asks[0].price)
                    if m.best_bid and m.best_ask:
                        m.spread = m.best_ask - m.best_bid
                        m.fav_price = m.best_ask
            except Exception as e:
                logger.debug(f"CLOB enrichment failed for {m.market_id}: {e}")
        return candidates

    def _parse_prices(self, prices_str):
        try:
            if prices_str.startswith("["):
                return [float(p) for p in json.loads(prices_str)]
            return [float(p.strip().strip('"')) for p in prices_str.split(",")]
        except:
            return []

    def _parse_token_ids(self, token_ids_str):
        try:
            if token_ids_str.startswith("["):
                return json.loads(token_ids_str)
            return [t.strip().strip('"') for t in token_ids_str.split(",") if t.strip()]
        except:
            return []

    def _parse_datetime(self, dt_str):
        for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def close(self):
        self.client.close()
