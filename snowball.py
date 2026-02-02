"""
Vig v1 Snowball — Clip size management and growth/harvest logic.
"""
import logging
from dataclasses import dataclass
from config import Config

logger = logging.getLogger("vig.snowball")


@dataclass
class SnowballState:
    clip_size: float
    phase: str
    total_pocketed: float
    bankroll: float
    windows_completed: int


class Snowball:
    def __init__(self, config: Config):
        self.config = config
        self.state = SnowballState(
            clip_size=config.starting_clip, phase="growth",
            total_pocketed=0.0, bankroll=0.0, windows_completed=0,
        )

    def get_clip_for_market(self, max_clip_for_volume: float) -> float:
        return min(self.state.clip_size, max_clip_for_volume)

    def process_window(self, window_profit: float, bets_in_window: int) -> dict:
        result = {"pocketed": 0.0, "new_clip": self.state.clip_size,
                  "phase": self.state.phase, "hit_max": False}

        self.state.windows_completed += 1
        self.state.bankroll += window_profit

        if window_profit > 0:
            if self.state.phase == "harvest" or self.state.clip_size >= self.config.max_clip:
                result["pocketed"] = window_profit
                self.state.total_pocketed += window_profit
                self.state.phase = "harvest"
                result["phase"] = "harvest"
            else:
                pocket = window_profit * (1 - self.config.snowball_reinvest_pct)
                reinvest = window_profit * self.config.snowball_reinvest_pct
                result["pocketed"] = pocket
                self.state.total_pocketed += pocket

                if bets_in_window > 0:
                    new_clip = self.state.clip_size + (reinvest / bets_in_window)
                    if new_clip >= self.config.max_clip:
                        new_clip = self.config.max_clip
                        self.state.phase = "harvest"
                        result["phase"] = "harvest"
                        result["hit_max"] = True
                        logger.info(f"Hit ${self.config.max_clip:.2f} max! HARVEST mode.")
                    self.state.clip_size = new_clip
                    result["new_clip"] = new_clip

        elif window_profit < 0:
            if bets_in_window > 0 and self.state.phase == "growth":
                new_clip = max(self.config.starting_clip,
                               self.state.clip_size - abs(window_profit) / bets_in_window)
                self.state.clip_size = new_clip
                result["new_clip"] = new_clip
                self.state.phase = "growth"
                result["phase"] = "growth"
            result["pocketed"] = 0.0

        logger.info(f"Snowball: profit=${window_profit:.2f} | pocketed=${result['pocketed']:.2f} | "
                    f"clip=${result['new_clip']:.2f} | phase={result['phase']}")
        return result

    def get_state(self) -> SnowballState:
        return self.state

    def load_state(self, clip_size, phase, total_pocketed, bankroll, windows_completed):
        self.state = SnowballState(clip_size=clip_size, phase=phase,
            total_pocketed=total_pocketed, bankroll=bankroll,
            windows_completed=windows_completed)
        logger.info(f"State restored: clip=${clip_size:.2f} phase={phase}")
