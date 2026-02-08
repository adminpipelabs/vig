"""
Vig v2 Risk Manager — Simplified risk management (no circuit breaker).
Agent never stops itself - only manages position sizing.
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
        # Vig v2: No circuit breaker - agent never stops itself
        # Only return warnings for logging, never stop alerts
        alerts = []
        return alerts

    def check_post_window(self, window_losses: int) -> list[RiskAlert]:
        # Vig v2: No circuit breaker - just log warnings
        alerts = []
        return alerts

    def should_stop(self, alerts):
        # Vig v2: Never stop
        return False

    def should_reduce(self, alerts):
        # Vig v2: Never reduce (fixed bet sizing)
        return False

    def get_clip_multiplier(self, alerts):
        # Vig v2: Always use full clip size (no reduction)
        return 1.0
