from extractor import fake_extract
from reconciler import Reconciler
import os


BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def load_email(path):

    full_path = os.path.join(BASE_DIR, path)

    with open(full_path, encoding="utf-8") as f:
        text = f.read()

    parts = text.split("BODY:")

    subject = parts[0]
    body = parts[1] if len(parts) > 1 else ""

    return subject, body


def main():

    r = Reconciler()

    files = [
        "test_emails/glean_apply.txt",
        "test_emails/glean_reject.txt",
    ]

    for f in files:
        subject, body = load_email(f)

        ext = fake_extract(subject, body)

        r.process(ext)


if __name__ == "__main__":
    main()
