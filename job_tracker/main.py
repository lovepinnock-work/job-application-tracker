import os

from extractor import GeminiExtractor
from reconciler import Reconciler
from sheets_repo import SheetsRepo

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def load_email(path):
    full_path = os.path.join(BASE_DIR, path)

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

    return subject, from_header, body


def main():
    extractor = GeminiExtractor()
    repo = SheetsRepo()
    reconciler = Reconciler(repo)

    files = [
        "test_emails/amazon_apply.txt",
        "test_emails/amazon_apply_1.txt",
        "test_emails/amazon_assessment_invite.txt",
        "test_emails/amazon_assessment_reminder.txt",
        "test_emails/amazon_assessment_completed.txt",
        "test_emails/amazon_reject.txt",
        "test_emails/amazon_reject_1.txt",
        "test_emails/sf_assessment_invite.txt"
    ]

    """
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
        "test_emails/junk_linkedin.txt"
    ]

    """

    for f in files:
        subject, from_header, body = load_email(f)

        ext = extractor.extract(
            subject=subject,
            body=body,
            from_header=from_header,
            date_iso="2026-03-14T12:00:00Z",
            thread_id="test-thread",
            message_id=f,
        )

        print("\n--- EXTRACTION ---")
        print(ext)

        reconciler.process(ext)


if __name__ == "__main__":
    main()