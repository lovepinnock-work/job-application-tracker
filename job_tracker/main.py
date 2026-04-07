import json
import time
from pathlib import Path
from datetime import datetime, timezone

from extractor import GeminiExtractor
from reconciler import Reconciler
from sheets_repo import SheetsRepo
from gmail_client import GmailClient


BASE_DIR = Path(__file__).resolve().parent.parent

# Modes
RUN_MODE = "TEST_EMAILS"   # TODO: Revert "TEST_EMAILS" or "GMAIL"
TEST_CASE = 0        # used only for TEST_EMAILS

# Test controls
CLEAR_SHEETS_BEFORE_TEST = False
SLEEP_SECONDS = 1

# Gmail labels
PROCESSED_LABEL_NAME = "JobTracker/Processed"
REVIEW_LABEL_NAME = "JobTracker/Review"

# Local state/log files
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

PROCESSED_CACHE_FILE = STATE_DIR / "processed_messages.json"
RUN_LOG_FILE = STATE_DIR / "run_log.jsonl"

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


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


def load_email(path):
    full_path = BASE_DIR / path

    with open(full_path, encoding="utf-8") as f:
        text = f.read()

    parts = text.split("BODY:")
    header_part = parts[0]
    body = parts[1].strip() if len(parts) > 1 else ""

    subject = ""
    from_header = ""

    for line in header_part.splitlines():
        line = line.strip()
        if line.upper().startswith("SUBJECT:"):
            subject = line[len("SUBJECT:"):].strip()
        elif line.upper().startswith("FROM:"):
            from_header = line[len("FROM:"):].strip()

    return {
        "message_id": str(path),
        "thread_id": f"thread::{path}",
        "subject": subject,
        "from_header": from_header,
        "body_text": body,
        "date_iso": "2026-03-14T12:00:00Z",
    }


def get_test_messages(case=0):
    files = []

    if case == 0:
        files = [
            "test_emails/linkedin_app_1.txt",
            "test_emails/linkedin_app_2.txt",
        ]
    elif case == 1:
        files = [
            "test_emails/glean_apply.txt",
            "test_emails/glean_reject.txt",
            "test_emails/junk_linkedin.txt",
            "test_emails/usa_reject.txt",
            "test_emails/amazon_apply.txt",
            "test_emails/amazon_apply_1.txt",
            "test_emails/amazon_assessment_invite.txt",
            "test_emails/amazon_assessment_reminder.txt",
            "test_emails/amazon_assessment_completed.txt",
            "test_emails/amazon_reject.txt",
            "test_emails/amazon_reject_1.txt",
        ]
    elif case == 2:
        files = [
            "test_emails/amazon_apply.txt",
            "test_emails/amazon_apply_1.txt",
            "test_emails/amazon_assessment_invite.txt",
            "test_emails/amazon_assessment_reminder.txt",
            "test_emails/amazon_assessment_completed.txt",
            "test_emails/amazon_reject.txt",
            "test_emails/amazon_reject_1.txt",
            "test_emails/sf_assessment_invite.txt",
        ]
    elif case == 3:
        files = [
            "test_emails/glean_apply.txt",
            "test_emails/glean_reject.txt",
            "test_emails/linkedin_apply.txt",
            "test_emails/sf_1_apply.txt",
            "test_emails/sf_assessment_invite.txt",
            "test_emails/sf_assessment_pass.txt",
            "test_emails/apple_interview.txt",
            "test_emails/offer_example.txt",
            "test_emails/junk_microsoft.txt",
            "test_emails/junk_nvidia.txt",
            "test_emails/junk_sf.txt",
            "test_emails/junk_northrop.txt",
            "test_emails/junk_linkedin.txt",
            "test_emails/amazon_apply.txt",
            "test_emails/amazon_apply_1.txt",
            "test_emails/amazon_assessment_invite.txt",
            "test_emails/amazon_assessment_reminder.txt",
            "test_emails/amazon_assessment_completed.txt",
            "test_emails/amazon_reject.txt",
            "test_emails/amazon_reject_1.txt",
            "test_emails/sf_assessment_invite.txt",
        ]

    return [load_email(f) for f in files]


def get_gmail_messages(gmail: GmailClient, processed_cache: dict):
    query = (
        f'newer_than:14d -label:"{PROCESSED_LABEL_NAME}" '
        '('
        'subject:("application" OR "applying" OR "interview" OR "assessment" OR "offer" OR "rejection" OR "thanks for applying" OR "application status" OR "exam" OR "test" OR "invitation") '
        'OR "received your application" '
        'OR "not proceed" '
        'OR "not a match" '
        'OR "application status" '
        'OR "written exam" '
        'OR "physical agility test" '
        'OR from:(jobs OR careers OR recruiting OR talent OR greenhouse OR workday OR myworkday OR lever OR ashby OR codesignal OR hackerrank OR governmentjobs)'
        ')'
    )

    message_ids = gmail.list_recent_message_ids(query=query, max_results=5)

    messages = []
    for message_id in message_ids:
        if message_id in processed_cache:
            continue
        msg = gmail.get_message(message_id)
        messages.append(msg)

    messages.sort(key=lambda msg: msg.get("date_iso", ""))
    return messages


def main():
    HEARTBEAT_FILE = STATE_DIR / "heartbeat.txt"

    def write_heartbeat():
        HEARTBEAT_FILE.write_text(f"last_run={utc_now_iso()}\n", encoding="utf-8")
    write_heartbeat()
    
    extractor = GeminiExtractor()
    repo = SheetsRepo()
    reconciler = Reconciler(repo)

    processed_cache = load_processed_cache()

    gmail = None
    processed_label_id = None
    review_label_id = None

    # Update run log everytime main is ran
    append_run_log({
        "ts": utc_now_iso(),
        "mode": RUN_MODE,
        "message_id": None,
        "thread_id": None,
        "subject": None,
        "from": None,
        "result": "startup",
        "needs_review": False,
        "error": None,
    })
    print(f"MAIN STARTED at {utc_now_iso()} in mode {RUN_MODE}")

    if RUN_MODE == "TEST_EMAILS":
        if CLEAR_SHEETS_BEFORE_TEST:
            repo.clear_all_test_data()
        messages = get_test_messages(TEST_CASE)

    elif RUN_MODE == "GMAIL":
        gmail = GmailClient()
        processed_label_id = gmail.get_or_create_label(PROCESSED_LABEL_NAME)
        review_label_id = gmail.get_or_create_label(REVIEW_LABEL_NAME)
        messages = get_gmail_messages(gmail, processed_cache)

    else:
        raise ValueError(f"Invalid RUN_MODE: {RUN_MODE}")

    print(f"Processing {len(messages)} message(s) in mode: {RUN_MODE}")

    for msg in messages:
        print("\n==============================")
        print("SUBJECT:", msg["subject"])
        print("FROM:", msg["from_header"])

        run_log_entry = {
            "ts": utc_now_iso(),
            "mode": RUN_MODE,
            "message_id": msg["message_id"],
            "thread_id": msg["thread_id"],
            "subject": msg["subject"],
            "from": msg["from_header"],
            "result": None,
            "needs_review": False,
            "error": None,
        }

        try:
            ext = extractor.extract(
                subject=msg["subject"],
                body=msg["body_text"],
                from_header=msg["from_header"],
                date_iso=msg["date_iso"],
                thread_id=msg["thread_id"],
                message_id=msg["message_id"],
            )

            print("\n--- EXTRACTION ---")
            print(ext)

            result = reconciler.process(ext)

            run_log_entry["result"] = result.get("result")
            run_log_entry["needs_review"] = result.get("needs_review", False)

            if RUN_MODE == "GMAIL" and gmail:
                if result.get("needs_review") and review_label_id:
                    gmail.add_label_to_message(msg["message_id"], review_label_id)
                    print(f"Labeled review: {msg['message_id']}")

                if processed_label_id:
                    gmail.add_label_to_message(msg["message_id"], processed_label_id)
                    print(f"Labeled processed: {msg['message_id']}")

                processed_cache[msg["message_id"]] = {
                    "processed_at": utc_now_iso(),
                    "result": result.get("result"),
                    "needs_review": result.get("needs_review", False),
                }
                save_processed_cache(processed_cache)

        except Exception as e:
            run_log_entry["error"] = str(e)
            print(f"ERROR processing message {msg['message_id']}: {e}")

        append_run_log(run_log_entry)
        time.sleep(SLEEP_SECONDS)

# Catch exceptions at top level, ensuring run log is always updated
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        append_run_log({
            "ts": utc_now_iso(),
            "mode": RUN_MODE,
            "message_id": None,
            "thread_id": None,
            "subject": None,
            "from": None,
            "result": "fatal_error",
            "needs_review": False,
            "error": str(e),
        })
        raise