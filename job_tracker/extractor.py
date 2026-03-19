import os
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional, Literal, List

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from models import Extraction

ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

SYSTEM_PROMPT = """
You extract structured job-application updates from emails.

Rules:
- Only classify as job-related if the email is clearly about a submitted application, rejection, assessment, interview, offer, or cancellation.
- Job alerts, talent community emails, security alerts, newsletters, recruiter marketing, and LinkedIn messages are not job-related.
- role_display should be the clean human-readable title only.
- role_key should preserve the distinguishing team or segment if present.
  Example:
  - role_display: "Data Analyst"
  - role_key: "data analyst lending"
- If a job ID or requisition ID appears, include it.
- If an assessment/interview/offer has a concrete date or due date, extract it.
- If no reliable date is present, return null rather than guessing.
- If an assessment, interview, or offer email does not name a specific role or job ID but clearly applies to multiple active applications at the same company, set shared_event to true.
- If the email appears to be a generic online assessment for all active applications at a company, prefer shared_event=true rather than false.
- application_targets should contain any job IDs, role keys, or role references explicitly mentioned in the email.
- If no targets are explicitly mentioned, return an empty list.
- Return only valid structured data matching the schema.
"""


class GeminiExtraction(BaseModel):
    is_job_related: bool

    email_type: Literal[
        "application_confirmation",
        "rejection",
        "assessment_invite",
        "assessment_completed",
        "assessment_passed",
        "assessment_failed",
        "interview_invite",
        "interview_completed",
        "offer",
        "offer_deadline",
        "canceled",
        "not_job_related",
    ]

    company: Optional[str] = Field(default=None)
    role_display: Optional[str] = Field(default=None)
    role_key: Optional[str] = Field(default=None)
    job_id: Optional[str] = Field(default=None)

    status: Optional[Literal[
        "Awaiting",
        "Assessment",
        "Interviewing",
        "Offer",
        "Rejected",
        "Canceled",
        "Closed",
    ]] = Field(default=None)

    application_date: Optional[str] = Field(default=None)

    event_type: Optional[Literal["Assessment", "Interview", "Offer"]] = Field(default=None)

    event_status: Optional[Literal[
        "Open",
        "Completed",
        "Passed",
        "Failed",
        "Expired",
        "Scheduled",
        "Accepted",
        "Declined",
    ]] = Field(default=None)

    event_date: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None)

    # NEW
    shared_event: bool = Field(default=False)
    application_targets: List[str] = Field(default_factory=list)

    reapply_signal: bool
    confidence: float
    notes: Optional[str] = Field(default=None)


class GeminiExtractor:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.cache_dir = Path(__file__).resolve().parent.parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)

        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in .env")

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _obvious_non_job(self, subject: str, body: str, from_header: str = "") -> bool:
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
        ]

        return any(p in text for p in junk_patterns)

    def extract(
        self,
        subject: str,
        body: str,
        from_header: str = "",
        date_iso: str = "",
        thread_id: str = "",
        message_id: str = "",
    ) -> Extraction:
        if self._obvious_non_job(subject, body, from_header):
            return Extraction(
                is_job_related=False,
                email_type="not_job_related",
                company=None,
                role_display=None,
                role_key=None,
                job_id=None,
                status=None,
                application_date=None,
                event_type=None,
                event_status=None,
                event_date=None,
                due_date=None,
                shared_event=False,
                application_targets=[],
                reapply_signal=False,
                confidence=0.99,
                notes="Filtered as obvious non-job email",
            )

        cache_key = self._cache_key(subject, body, from_header, date_iso, thread_id, message_id)
        cache_path = self._cache_path(cache_key)

        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Extraction(**data)

        payload = {
            "subject": subject,
            "from": from_header,
            "date": date_iso,
            "thread_id": thread_id,
            "message_id": message_id,
            "body_text": body[:12000],
        }

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=str(payload),
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=GeminiExtraction,
                        temperature=0.0,
                    ),
                )

                parsed = response.parsed
                if parsed is None:
                    parsed = GeminiExtraction.model_validate_json(response.text)

                ext = Extraction(
                    is_job_related=parsed.is_job_related,
                    email_type=parsed.email_type,
                    company=parsed.company,
                    role_display=parsed.role_display,
                    role_key=parsed.role_key,
                    job_id=parsed.job_id,
                    status=parsed.status,
                    application_date=parsed.application_date,
                    event_type=parsed.event_type,
                    event_status=parsed.event_status,
                    event_date=parsed.event_date,
                    due_date=parsed.due_date,
                    shared_event=parsed.shared_event,
                    application_targets=parsed.application_targets,
                    reapply_signal=parsed.reapply_signal,
                    confidence=parsed.confidence,
                    notes=parsed.notes,
                )

                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(ext.__dict__, f, ensure_ascii=False, indent=2)

                return ext

            except Exception as e:
                last_error = e
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    wait_seconds = 65
                    print(f"Rate limited by Gemini. Waiting {wait_seconds}s before retry...")
                    time.sleep(wait_seconds)
                    continue
                raise

        raise last_error
    
    def _cache_key(self, subject: str, body: str, from_header: str, date_iso: str, thread_id: str, message_id: str) -> str:
        raw = json.dumps({
            "subject": subject,
            "from": from_header,
            "date": date_iso,
            "thread_id": thread_id,
            "message_id": message_id,
            "body_text": body[:12000],
        }, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"