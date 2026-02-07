"""
Vig v1 Risk Manager — Circuit breaker and position limits.
"""
import logging
from config import Config
from db import Database

logger = logging.getLogger("vig.risk")


class RiskAlert:
    def __init__(self, level, reason, action):
        self.level = level
        self.reason = reason
        self.action = action
    def __str__(self):
        return f"[{self.level.upper()}] {self.reason} -> {self.action}"


class RiskManager:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db

    def check_pre_window(self) -> list[RiskAlert]:
        alerts = []
        # Circuit breaker removed - bot will continue trading regardless of win rate
        # This allows continuous operation and capital deployment

        today_windows = self.db.get_recent_windows(12)
        today_profit = sum(w.profit for w in today_windows)
        today_deployed = sum(w.deployed for w in today_windows)
        if today_deployed > 0 and today_profit < 0:
            loss_pct = abs(today_profit) / today_deployed
            if loss_pct > self.config.circuit_breaker_daily_loss_pct:
                alerts.append(RiskAlert("stop",
                    f"Daily loss {loss_pct:.1%} exceeds limit",
                    "Stop trading for today."))

        for a in alerts:
            logger.warning(str(a))
        return alerts

    def check_post_window(self, window_losses: int) -> list[RiskAlert]:
        alerts = []
        if window_losses >= self.config.circuit_breaker_window_max_losses:
            alerts.append(RiskAlert("warning",
                f"{window_losses} losses in one window", "Flag for review."))
        return alerts

    def should_stop(self, alerts):
        return any(a.level == "stop" for a in alerts)

    def should_reduce(self, alerts):
        return any(a.level == "reduce" for a in alerts)

    def get_clip_multiplier(self, alerts):
        if self.should_stop(alerts):
            return 0.0
        if self.should_reduce(alerts):
            return 0.75
        return 1.0
