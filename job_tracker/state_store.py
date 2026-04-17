import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

PROCESSED_CACHE_FILE = STATE_DIR / "processed_messages.json"
RUN_LOG_FILE = STATE_DIR / "run_log.jsonl"
HEARTBEAT_FILE = STATE_DIR / "heartbeat.txt"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_heartbeat():
    HEARTBEAT_FILE.write_text(f"last_run={utc_now_iso()}\n", encoding="utf-8")


def load_processed_cache():
    if not PROCESSED_CACHE_FILE.exists():
        return {}

    try:
        with open(PROCESSED_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_processed_cache(cache):
    with open(PROCESSED_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def append_run_log(entry: dict):
    with open(RUN_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")