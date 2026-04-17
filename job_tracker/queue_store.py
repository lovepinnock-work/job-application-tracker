import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

PENDING_QUEUE_FILE = STATE_DIR / "pending_messages.json"


def load_pending_queue():
    if not PENDING_QUEUE_FILE.exists():
        return []

    try:
        with open(PENDING_QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def save_pending_queue(queue):
    with open(PENDING_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def is_queued(message_id: str, queue: list) -> bool:
    return any(item.get("message_id") == message_id for item in queue)


def add_to_pending_queue(message: dict, queue: list):
    if is_queued(message["message_id"], queue):
        return queue

    item = {
        "message_id": message["message_id"],
        "thread_id": message["thread_id"],
        "subject": message["subject"],
        "from_header": message["from_header"],
        "body_text": message["body_text"],
        "date_iso": message["date_iso"],
        "retry_count": 0,
        "first_seen_at": message.get("date_iso") or "",
    }
    queue.append(item)
    queue.sort(key=lambda x: x.get("date_iso") or "")
    return queue


def remove_from_pending_queue(message_id: str, queue: list):
    return [item for item in queue if item.get("message_id") != message_id]


def increment_retry(message_id: str, queue: list):
    for item in queue:
        if item.get("message_id") == message_id:
            item["retry_count"] = int(item.get("retry_count", 0)) + 1
            break
    return queue