import os
import time
from pathlib import Path

from extractor import GeminiExtractor
from reconciler import Reconciler
from sheets_repo import SheetsRepo
from gmail_client import GmailClient


BASE_DIR = Path(__file__).resolve().parent.parent

# Change this to "GMAIL" when ready for prod
RUN_MODE = "GMAIL"   # "TEST_EMAILS" or "GMAIL"

# Optional: wipe sheets before each local test run
CLEAR_SHEETS_BEFORE_TEST = True

# Small pause between calls
SLEEP_SECONDS = 1


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
        files = [ # Minimal set for quick testing of basic flow
            "test_emails/glean_apply.txt",
            "test_emails/glean_reject.txt",
        ]
    elif case == 1:
        files = [ # More comprehensive set for testing various scenarios
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
        files = [ # Test multiple emails from same company/role/job_id to test app key logic
        "test_emails/amazon_apply.txt",
        "test_emails/amazon_apply_1.txt",
        "test_emails/amazon_assessment_invite.txt",
        "test_emails/amazon_assessment_reminder.txt",
        "test_emails/amazon_assessment_completed.txt",
        "test_emails/amazon_reject.txt",
        "test_emails/amazon_reject_1.txt",
        "test_emails/sf_assessment_invite.txt"
    ]
    elif case == 3:
        files = [ # Unit testing
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
        "test_emails/sf_assessment_invite.txt"
    ]

    messages = []
    for f in files:
        messages.append(load_email(f))
    return messages


def get_gmail_messages():
    gmail = GmailClient()

    # Starting small while testing
    message_ids = gmail.list_recent_message_ids(
        query="newer_than:2d",
        max_results=3
    )

    messages = []
    for message_id in message_ids:
        msg = gmail.get_message(message_id)
        messages.append(msg)

    return messages


def main():
    extractor = GeminiExtractor()
    repo = SheetsRepo()
    reconciler = Reconciler(repo)

    if RUN_MODE.upper() == "TEST_EMAILS":
        if CLEAR_SHEETS_BEFORE_TEST:
            repo.clear_all_test_data()
        messages = get_test_messages(case=2)

    elif RUN_MODE.upper() == "GMAIL":
        messages = get_gmail_messages()

    else:
        raise ValueError(f"Invalid RUN_MODE: {RUN_MODE}")

    print(f"Processing {len(messages)} message(s) in mode: {RUN_MODE}")

    for msg in messages:
        print("\n==============================")
        print("SUBJECT:", msg["subject"])
        print("FROM:", msg["from_header"])

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

        reconciler.process(ext)

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()