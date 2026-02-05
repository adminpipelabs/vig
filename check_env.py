#!/usr/bin/env python3
"""Quick check of .env configuration"""
from dotenv import load_dotenv
import os

load_dotenv()

required = [
    'POLYGON_PRIVATE_KEY',
    'POLYGON_FUNDER_ADDRESS',
    'PAPER_MODE',
    'STARTING_CLIP',
    'MAX_CLIP',
    'MIN_FAVORITE_PRICE',
    'MAX_FAVORITE_PRICE',
    'MAX_BETS_PER_WINDOW',
    'MIN_VOLUME_ABS',
    'SCAN_INTERVAL_SECONDS',
    'DB_PATH',
]

print("Checking .env configuration...\n")
all_good = True

for key in required:
    value = os.getenv(key)
    if value:
        if key == 'POLYGON_PRIVATE_KEY':
            print(f"  OK {key}: {'*' * 20}... (hidden)")
        elif key == 'POLYGON_FUNDER_ADDRESS':
            print(f"  OK {key}: {value[:10]}...{value[-6:]}")
        else:
            print(f"  OK {key}: {value}")
    else:
        print(f"  MISSING {key}")
        all_good = False

print()
if all_good:
    print("All required variables are set!")
else:
    print("Some variables are missing. Please check your .env file.")