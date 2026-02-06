"""
Bot Status Manager
Tracks bot status and provides control endpoints
"""
import os
import time
import json
from pathlib import Path
from datetime import datetime, timezone

STATUS_FILE = Path("/tmp/vig_bot_status.json")  # Railway ephemeral filesystem
if os.getenv("DB_PATH"):
    # If using persistent volume, store there
    status_path = Path(os.getenv("DB_PATH")).parent / "vig_bot_status.json"
    if status_path.parent.exists():
        STATUS_FILE = status_path


def update_bot_status(status: str, activity: str = None, last_scan: str = None):
    """Update bot status file"""
    data = {
        "status": status,  # "running", "stopped", "error"
        "activity": activity or "Idle",
        "last_scan": last_scan or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass  # Fail silently if can't write


def get_bot_status():
    """Get current bot status"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    
    # Default status
    return {
        "status": "unknown",
        "activity": "Unknown",
        "last_scan": None,
        "updated_at": None,
    }
