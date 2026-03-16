from models import Extraction


def fake_extract(subject: str, body: str) -> Extraction:
    text = (subject + "\n" + body).lower()

    # obvious junk
    if "security alert" in text or "job alert" in text:
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
            confidence=0.2,
            notes="Filtered as non-job email",
        )

    # Glean / Chime style application confirmations
    if (
        "received your application for" in text
        or "we've received your application for" in text
        or "we wanted to let you know we received your application for" in text
    ):
        company = "Glean" if "glean" in text else "Chime" if "chime" in text else "Unknown"
        return Extraction(
            is_job_related=True,
            email_type="application_confirmation",
            company=company,
            role_display="Data Analyst" if "data analyst" in text else "Software Engineer",
            role_key="data analyst lending" if "lending" in text else "software engineer university grad",
            job_id=None,
            status="Awaiting",
            application_date=None,
            event_type=None,
            event_status=None,
            event_date=None,
            due_date=None,
            reapply_signal=False,
            confidence=0.9,
            notes=None,
        )

    # Glean / Chime style rejections
    if (
        "not move forward" in text
        or "move forward with other candidates" in text
        or "unfortunately" in text
        or "not selected" in text
    ):
        company = "Glean" if "glean" in text else "Chime" if "chime" in text else "Unknown"
        return Extraction(
            is_job_related=True,
            email_type="rejection",
            company=company,
            role_display="Data Analyst" if "data analyst" in text else "Software Engineer",
            role_key="data analyst lending" if "lending" in text else "software engineer university grad",
            job_id=None,
            status="Rejected",
            application_date=None,
            event_type=None,
            event_status=None,
            event_date=None,
            due_date=None,
            reapply_signal=False,
            confidence=0.9,
            notes=None,
        )

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
        confidence=0.5,
        notes=None,
    )