import base64
import os
from datetime import datetime, timezone
from pathlib import Path


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    def __init__(self):
        base_dir = Path(__file__).resolve().parent.parent
        self.token_path = base_dir / "gmail_token.json"
        self.credentials_path = base_dir / "gmail_oauth_client.json"

        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_path, "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)

    def list_recent_message_ids(self, query="newer_than:7d", max_results=10):
        result = self.service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()

        return [m["id"] for m in result.get("messages", [])]

    def get_message(self, message_id: str):
        msg = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        headers = msg["payload"].get("headers", [])
        header_map = {h["name"]: h["value"] for h in headers}

        subject = header_map.get("Subject", "")
        from_header = header_map.get("From", "")
        thread_id = msg.get("threadId", "")

        internal_ts = msg.get("internalDate", "")

        # Convert Gmail timestamp (ms since epoch) → ISO string
        date_iso = ""
        if internal_ts:
            try:
                dt = datetime.fromtimestamp(int(internal_ts) / 1000, tz=timezone.utc)
                date_iso = dt.isoformat()
            except Exception:
                date_iso = ""

        body_text = self._extract_plain_text(msg["payload"])

        return {
            "message_id": message_id,
            "thread_id": thread_id,
            "subject": subject,
            "from_header": from_header,
            "body_text": body_text,
            "date_iso": date_iso,
        }

    def _extract_plain_text(self, payload):
        if "parts" in payload:
            for part in payload["parts"]:
                mime = part.get("mimeType", "")
                if mime == "text/plain":
                    data = part["body"].get("data")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            for part in payload["parts"]:
                text = self._extract_plain_text(part)
                if text:
                    return text
            return ""

        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        return ""