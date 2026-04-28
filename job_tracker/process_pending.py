import time
from datetime import datetime, timezone

from extractor import GeminiExtractor
from reconciler import Reconciler
from sheets_repo import SheetsRepo
from gmail_client import GmailClient
from queue_store import (
    load_pending_queue,
    save_pending_queue,
    remove_from_pending_queue,
    increment_retry,
)
from usage_budget import can_consume, consume_one, remaining
from state_store import (
    utc_now_iso,
    load_processed_cache,
    save_processed_cache,
    append_run_log,
    write_heartbeat,
)
from config import (
    PROCESSED_LABEL_NAME,
    REVIEW_LABEL_NAME,
    SLEEP_SECONDS,
    MAX_GEMINI_CALLS_PER_DAY,
    MAX_GEMINI_CALLS_PER_RUN,
)

def is_temporary_api_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "503" in msg
        or "service unavailable" in msg
        or "429" in msg
        or "resource_exhausted" in msg
        or "quota exceeded" in msg
    )


def main():

    write_heartbeat()
    append_run_log({
        "ts": utc_now_iso(),
        "mode": "PROCESS_PENDING",
        "message_id": None,
        "thread_id": None,
        "subject": None,
        "from": None,
        "result": "startup",
        "needs_review": False,
        "error": None,
    })

    repo = SheetsRepo()
    reconciler = Reconciler(repo)
    extractor = GeminiExtractor()
    gmail = GmailClient()

    processed_label_id = gmail.get_or_create_label(PROCESSED_LABEL_NAME)
    review_label_id = gmail.get_or_create_label(REVIEW_LABEL_NAME)

    processed_cache = load_processed_cache()
    queue = load_pending_queue()

    queue.sort(key=lambda x: x.get("date_iso") or "")

    print(f"Pending queue size: {len(queue)}")
    print(f"Gemini remaining today: {remaining(MAX_GEMINI_CALLS_PER_DAY)}")

    processed_this_run = 0
    new_queue = list(queue)

    for item in queue:
        if processed_this_run >= MAX_GEMINI_CALLS_PER_RUN:
            break

        if not can_consume(MAX_GEMINI_CALLS_PER_DAY):
            print("Daily Gemini budget exhausted.")
            break

        msg_id = item["message_id"]

        run_log_entry = {
            "ts": utc_now_iso(),
            "mode": "PROCESS_PENDING",
            "message_id": msg_id,
            "thread_id": item["thread_id"],
            "subject": item["subject"],
            "from": item["from_header"],
            "result": None,
            "needs_review": False,
            "error": None,
        }

        try:
            consume_one()

            ext = extractor.extract(
                subject=item["subject"],
                body=item["body_text"],
                from_header=item["from_header"],
                date_iso=item["date_iso"],
                thread_id=item["thread_id"],
                message_id=msg_id,
            )

            print("\n--- EXTRACTION ---")
            print(ext)

            result = reconciler.process(ext)

            run_log_entry["result"] = result.get("result")
            run_log_entry["needs_review"] = result.get("needs_review", False)

            if result.get("needs_review"):
                gmail.add_label_to_message(msg_id, review_label_id)

            gmail.add_label_to_message(msg_id, processed_label_id)

            processed_cache[msg_id] = {
                "processed_at": utc_now_iso(),
                "result": result.get("result"),
                "needs_review": result.get("needs_review", False),
            }

            new_queue = remove_from_pending_queue(msg_id, new_queue)
            processed_this_run += 1

        except Exception as e:
            run_log_entry["error"] = str(e)

            if is_temporary_api_error(e):
                print(f"Temporary API error for {msg_id}: {e}")
                new_queue = increment_retry(msg_id, new_queue)
                run_log_entry["result"] = "retry_later"
            else:
                print(f"Hard error for {msg_id}: {e}")
                new_queue = increment_retry(msg_id, new_queue)
                run_log_entry["result"] = "retry_later"

        append_run_log(run_log_entry)
        time.sleep(SLEEP_SECONDS)

    save_pending_queue(new_queue)
    save_processed_cache(processed_cache)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        append_run_log({
            "ts": utc_now_iso(),
            "mode": "PROCESS_PENDING",
            "message_id": None,
            "thread_id": None,
            "subject": None,
            "from": None,
            "result": None,
            "needs_review": False,
            "error": str(e),
        })
        print(f"ERROR in main: {e}")
        raise