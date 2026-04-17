import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

USAGE_FILE = STATE_DIR / "gemini_usage.json"


def _today_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_usage():
    if not USAGE_FILE.exists():
        return {"date": _today_utc(), "count": 0}

    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"date": _today_utc(), "count": 0}

    if data.get("date") != _today_utc():
        return {"date": _today_utc(), "count": 0}

    return {
        "date": data.get("date", _today_utc()),
        "count": int(data.get("count", 0)),
    }


def save_usage(data):
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def can_consume(max_per_day: int) -> bool:
    data = load_usage()
    return data["count"] < max_per_day


def consume_one():
    data = load_usage()
    data["count"] += 1
    save_usage(data)
    return data["count"]


def remaining(max_per_day: int) -> int:
    data = load_usage()
    return max(0, max_per_day - data["count"])