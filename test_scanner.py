#!/usr/bin/env python3
"""Test scanner to see if it finds markets"""
import os
from dotenv import load_dotenv
load_dotenv()

from config import Config
from scanner import Scanner

config = Config()
scanner = Scanner(config)

print("Testing scanner with current config:")
print(f"  min_favorite_price: {config.min_favorite_price}")
print(f"  max_favorite_price: {config.max_favorite_price}")
print(f"  expiry_window_minutes: {config.expiry_window_minutes}")
print(f"  min_volume_abs: {config.min_volume_abs}")
print(f"  max_bets_per_window: {config.max_bets_per_window}")
print()

candidates = scanner.scan()
print(f"Found {len(candidates)} candidates")
for i, m in enumerate(candidates[:10], 1):
    print(f"{i}. {m.fav_side} {m.question[:60]}")
    print(f"   ${m.fav_price:.2f} | exp {m.minutes_to_expiry:.0f}m | vol ${m.volume:,.0f}")

scanner.close()
