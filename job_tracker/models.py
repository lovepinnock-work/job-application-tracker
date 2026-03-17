from dataclasses import dataclass
from typing import Optional, List


@dataclass
class EmailMessage:
    message_id: str
    thread_id: str
    subject: str
    from_header: str
    body_text: str
    date_iso: str


@dataclass
class Extraction:
    is_job_related: bool
    email_type: str

    company: Optional[str]
    role_display: Optional[str]
    role_key: Optional[str]
    job_id: Optional[str]

    status: Optional[str]
    application_date: Optional[str]

    event_type: Optional[str]
    event_status: Optional[str]
    event_date: Optional[str]
    due_date: Optional[str]

    # NEW
    shared_event: bool
    application_targets: List[str]

    reapply_signal: bool
    confidence: float
    notes: Optional[str]