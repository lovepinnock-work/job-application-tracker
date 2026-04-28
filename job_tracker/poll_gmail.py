import json
from datetime import datetime, timezone
from pathlib import Path

from gmail_client import GmailClient
from queue_store import load_pending_queue, save_pending_queue, add_to_pending_queue
from config import PROCESSED_LABEL_NAME, MAX_FETCH_RESULTS
from state_store import (
    utc_now_iso,
    load_processed_cache,
    save_processed_cache,
    append_run_log,
    write_heartbeat,
)


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)



def obvious_non_job(subject: str, body: str, from_header: str = "") -> bool:
    text = f"{subject}\n{body}\n{from_header}".lower()

    junk_patterns = [
        "security alert",
        "new sign-in",
        "your job alert",
        "this job is a match",
        "talent community",
        "manage your job alerts",
        "messages-noreply@linkedin.com",
        "jobalerts-noreply@linkedin.com",
        "glassdoor community",
        "noreply@glassdoor.com",
        "linkedin news",
        "editors-noreply@linkedin.com",
        "new jobs match your profile",
        "jobs that match based on your profile",
        "that match your profile",
        "matched your profile",
        "new job alert",
        "verify your email",
        "code will expire after",
        "complete survery",
        "provide demographic information in a",
        "wants your feedback",
        "your otp",
        "apply now to",
        "roles inside",
        "this newsletter",
        "your saved job",
        "confirm your identity",
        "security code",
        "code expires in",
        "one-time pass code",
        "messages received",
        "see who else is applying",
        "your application was viewed",
        "finalize your profile",
        "here are some new roles at",
        "jobs that best fit your preferences",
        "provide us with anonymous feedback",
        "based on your profile and preferences",
        "exciting new opportunities tailored",
    ]

    return any(p in text for p in junk_patterns)


def get_candidate_messages(gmail: GmailClient, processed_cache: dict, queue: list):
    query = (
        f'newer_than:14d -label:"{PROCESSED_LABEL_NAME}" '
        '('
        'subject:("application" OR "applying" OR "interview" OR "assessment" OR "offer" OR "rejection" OR "thanks for applying" OR "application status" OR "exam" OR "test" OR "invitation") '
        'OR "received your application" '
        'OR "after careful review" '
        'OR "not proceed" '
        'OR "not a match" '
        'OR "moving forward" '
        'OR "pursue other candidates" '
        'OR "after careful consideration" '
        'OR "for further consideration" '
        'OR "not selected you" '
        'OR "application status" '
        'OR "submitted your application" '
        'OR "your interest" '
        'OR "reapply" '
        'OR "regret to inform you" '
        'OR "unfortunately" '
        'OR "exam" '
        'OR from:(jobs OR careers OR recruiting OR talent OR greenhouse OR indeed OR workday OR myworkday OR lever OR ashby OR ashbyhq OR codesignal OR hackerrank OR governmentjobs)'
        ')'
    )

    message_ids = gmail.list_recent_message_ids(query=query, max_results=MAX_FETCH_RESULTS)

    messages = []
    queued_ids = {item.get("message_id") for item in queue}

    for message_id in message_ids:
        if message_id in processed_cache:
            continue
        if message_id in queued_ids:
            continue
        msg = gmail.get_message(message_id)
        messages.append(msg)

    messages.sort(key=lambda m: m.get("date_iso") or "")
    return messages


def main():
    
    write_heartbeat()
    append_run_log({
        "ts": utc_now_iso(),
        "mode": "POLL_ONLY",
        "message_id": None,
        "thread_id": None,
        "subject": None,
        "from": None,
        "result": "startup",
        "needs_review": False,
        "error": None,
    })

    gmail = GmailClient()
    processed_label_id = gmail.get_or_create_label(PROCESSED_LABEL_NAME)
    processed_cache = load_processed_cache()
    queue = load_pending_queue()

    messages = get_candidate_messages(gmail, processed_cache, queue)

    print(f"Polling found {len(messages)} candidate Gmail message(s).")

    for msg in messages:
        subject = msg["subject"]
        from_header = msg["from_header"]
        body = msg["body_text"]

        if obvious_non_job(subject, body, from_header):
            gmail.add_label_to_message(msg["message_id"], processed_label_id)
            processed_cache[msg["message_id"]] = {
                "processed_at": utc_now_iso(),
                "result": "ignored_prefilter",
                "needs_review": False,
            }
            append_run_log({
                "ts": utc_now_iso(),
                "mode": "POLL_ONLY",
                "message_id": msg["message_id"],
                "thread_id": msg["thread_id"],
                "subject": subject,
                "from": from_header,
                "result": "ignored_prefilter",
                "needs_review": False,
                "error": None,
            })
            continue

        queue = add_to_pending_queue(msg, queue)

        append_run_log({
            "ts": utc_now_iso(),
            "mode": "POLL_ONLY",
            "message_id": msg["message_id"],
            "thread_id": msg["thread_id"],
            "subject": subject,
            "from": from_header,
            "result": "queued",
            "needs_review": False,
            "error": None,
        })

    save_pending_queue(queue)
    save_processed_cache(processed_cache)


if __name__ == "__main__":
    main()