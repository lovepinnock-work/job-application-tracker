from datetime import datetime, timezone
from typing import Optional
import uuid

from util import make_app_key, make_event_key


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_application_payload(
    company: str,
    role_display: str,
    role_key: str,
    job_id: Optional[str],
    status: str = "Awaiting",
    date_applied: Optional[str] = None,
    last_updated: Optional[str] = None,
    notes: Optional[str] = None,
    confidence: Optional[float] = None,
):
    date_applied = date_applied or utc_now_iso()[:10]
    last_updated = last_updated or utc_now_iso()[:10]

    app_id = str(uuid.uuid4())
    app_key = make_app_key(company, role_key, job_id)

    return {
        "Application ID": app_id,
        "Company": company or "",
        "Role Display": role_display or "",
        "Role Key": role_key or "",
        "Job ID": job_id or "",
        "App Key": app_key or "",
        "Status": status or "Awaiting",
        "Date Applied": date_applied,
        "Last Updated": last_updated,
        "Interview Date": "",
        "Assessment Date": "",
        "Offer Due Date": "",
        "Confidence": confidence if confidence is not None else "",
        "Notes": notes or "",
    }


def make_event_payload(
    company: str,
    event_type: str,
    event_status: str,
    event_date: Optional[str] = None,
    due_date: Optional[str] = None,
    notes: Optional[str] = None,
    confidence: Optional[float] = None,
):
    event_id = str(uuid.uuid4())

    normalized_event_date = (event_date or "")[:10] if event_date else ""
    normalized_due_date = (due_date or "")[:10] if due_date else ""

    event_key = make_event_key(
        company,
        event_type,
        normalized_event_date,
        normalized_due_date,
        "",
    )

    return {
        "Event ID": event_id,
        "Event Key": event_key,
        "Company": company or "",
        "Event Type": event_type or "",
        "Event Status": event_status or "",
        "Event Date": normalized_event_date,
        "Due Date": normalized_due_date,
        "Confidence": confidence if confidence is not None else "",
        "Notes": notes or "",
    }


def make_event_application_link(event_id: str, application_id: str):
    return {
        "Event ID": event_id,
        "Application ID": application_id,
    }