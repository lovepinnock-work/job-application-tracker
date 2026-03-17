import os
from typing import Optional, Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from models import Extraction

load_dotenv()

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

    reapply_signal: bool
    confidence: float
    notes: Optional[str] = Field(default=None)


class GeminiExtractor:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
                reapply_signal=False,
                confidence=0.99,
                notes="Filtered as obvious non-job email",
            )

        payload = {
            "subject": subject,
            "from": from_header,
            "date": date_iso,
            "thread_id": thread_id,
            "message_id": message_id,
            "body_text": body[:12000],
        }

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

        # The SDK can return parsed structured output when using a Pydantic schema.
        parsed = response.parsed
        if parsed is None:
            parsed = GeminiExtraction.model_validate_json(response.text)

        return Extraction(
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
            reapply_signal=parsed.reapply_signal,
            confidence=parsed.confidence,
            notes=parsed.notes,
        )