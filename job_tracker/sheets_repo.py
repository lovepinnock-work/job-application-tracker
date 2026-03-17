import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsRepo:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(__file__))

        project_root = os.path.dirname(os.path.dirname(__file__))
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

        if os.path.isabs(credentials_path):
            full_credentials_path = credentials_path
        else:
            full_credentials_path = os.path.normpath(os.path.join(project_root, credentials_path))
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

        if not spreadsheet_id:
            raise ValueError("Missing GOOGLE_SHEETS_SPREADSHEET_ID in .env")

        full_credentials_path = os.path.normpath(os.path.join(os.path.dirname(__file__), credentials_path))

        creds = Credentials.from_service_account_file(full_credentials_path, scopes=SCOPES)
        self.service = build("sheets", "v4", credentials=creds)
        self.spreadsheet_id = spreadsheet_id

        self.applications_sheet = "Applications"
        self.events_sheet = "Events"
        self.event_apps_sheet = "EventApplications"
        self.review_sheet = "ReviewQueue"

    # ---------- generic helpers ----------

    def _get_sheet_values(self, sheet_name: str):
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=sheet_name)
            .execute()
        )
        return result.get("values", [])

    def _append_row(self, sheet_name: str, row: list):
        body = {"values": [row]}
        (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=sheet_name,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

    def _update_row(self, sheet_name: str, row_number: int, row: list):
        body = {"values": [row]}
        rng = f"{sheet_name}!A{row_number}"
        (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=rng,
                valueInputOption="RAW",
                body=body,
            )
            .execute()
        )

    # ---------- Applications ----------

    def get_applications(self):
        values = self._get_sheet_values(self.applications_sheet)
        if not values:
            return []

        headers = values[0]
        rows = []
        for i, row in enumerate(values[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            item = dict(zip(headers, padded))
            item["_row"] = i
            rows.append(item)
        return rows

    def find_application_by_app_key(self, app_key: str) -> Optional[dict]:
        if not app_key:
            return None

        for row in self.get_applications():
            if row.get("App Key") == app_key:
                return row
        return None

    def get_open_applications_by_company(self, company: str):
        out = []
        for row in self.get_applications():
            if row.get("Company", "").strip().lower() == company.strip().lower():
                if row.get("Status") not in {"Rejected", "Canceled", "Closed"}:
                    out.append(row)
        return out

    def create_application(self, ext, app_key: str):
        application_id = str(uuid.uuid4())

        row = [
            application_id,
            ext.company or "",
            ext.role_display or "",
            ext.role_key or "",
            ext.job_id or "",
            app_key or "",
            ext.status or "Awaiting",
            ext.application_date or "NOW",
            ext.application_date or ext.event_date or ext.due_date or "NOW",
            "",
            "",
            "",
            ext.confidence,
            ext.notes or "",
        ]

        self._append_row(self.applications_sheet, row)
        return self.find_application_by_app_key(app_key)

    def update_application_status(self, app: dict, ext, new_status: str):
        row = [
            app.get("Application ID", ""),
            app.get("Company", ""),
            app.get("Role Display", ""),
            app.get("Role Key", ""),
            app.get("Job ID", ""),
            app.get("App Key", ""),
            new_status,
            app.get("Date Applied", ""),
            ext.application_date or ext.event_date or ext.due_date or "NOW",
            app.get("Interview Date", ""),
            app.get("Assessment Date", ""),
            app.get("Offer Due Date", ""),
            ext.confidence,
            ext.notes or app.get("Notes", ""),
        ]
        self._update_row(self.applications_sheet, app["_row"], row)

    def refresh_application(self, app: dict, ext):
        row = [
            app.get("Application ID", ""),
            app.get("Company", ""),
            app.get("Role Display", ""),
            app.get("Role Key", ""),
            app.get("Job ID", ""),
            app.get("App Key", ""),
            app.get("Status", "Awaiting"),
            app.get("Date Applied", ""),
            ext.application_date or ext.event_date or ext.due_date or "NOW",
            app.get("Interview Date", ""),
            app.get("Assessment Date", ""),
            app.get("Offer Due Date", ""),
            ext.confidence,
            ext.notes or app.get("Notes", ""),
        ]
        self._update_row(self.applications_sheet, app["_row"], row)

    def reset_for_reapply(self, app: dict, ext):
        row = [
            app.get("Application ID", ""),
            app.get("Company", ""),
            app.get("Role Display", ""),
            app.get("Role Key", ""),
            app.get("Job ID", ""),
            app.get("App Key", ""),
            "Awaiting",
            ext.application_date or "NOW",
            ext.application_date or "NOW",
            "",
            "",
            "",
            ext.confidence,
            ext.notes or app.get("Notes", ""),
        ]
        self._update_row(self.applications_sheet, app["_row"], row)

    def update_application_event_fields(self, app: dict, ext, fallback_status: str):
        interview_date = app.get("Interview Date", "")
        assessment_date = app.get("Assessment Date", "")
        offer_due_date = app.get("Offer Due Date", "")

        if ext.event_type == "Interview":
            interview_date = ext.event_date or interview_date
        elif ext.event_type == "Assessment":
            assessment_date = ext.due_date or ext.event_date or assessment_date
        elif ext.event_type == "Offer":
            offer_due_date = ext.due_date or offer_due_date

        row = [
            app.get("Application ID", ""),
            app.get("Company", ""),
            app.get("Role Display", ""),
            app.get("Role Key", ""),
            app.get("Job ID", ""),
            app.get("App Key", ""),
            ext.status or fallback_status,
            app.get("Date Applied", ""),
            ext.event_date or ext.application_date or ext.due_date or "NOW",
            interview_date,
            assessment_date,
            offer_due_date,
            ext.confidence,
            ext.notes or app.get("Notes", ""),
        ]
        self._update_row(self.applications_sheet, app["_row"], row)

    # ---------- Events ----------

    def get_events(self):
        values = self._get_sheet_values(self.events_sheet)
        if not values:
            return []

        headers = values[0]
        rows = []
        for i, row in enumerate(values[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            item = dict(zip(headers, padded))
            item["_row"] = i
            rows.append(item)
        return rows

    def create_event(self, event_key: str, ext):
        event_id = str(uuid.uuid4())
        row = [
            event_id,
            event_key,
            ext.company or "",
            ext.event_type or "",
            ext.event_status or "",
            ext.event_date or "",
            ext.due_date or "",
            ext.confidence,
            ext.notes or "",
        ]
        self._append_row(self.events_sheet, row)
        return self.find_event_by_event_key(event_key)

    def find_event_by_event_key(self, event_key: str) -> Optional[dict]:
        for row in self.get_events():
            if row.get("Event Key") == event_key:
                return row
        return None

    def update_event(self, event: dict, ext):
        row = [
            event.get("Event ID", ""),
            event.get("Event Key", ""),
            event.get("Company", ""),
            event.get("Event Type", ""),
            ext.event_status or event.get("Event Status", ""),
            ext.event_date or event.get("Event Date", ""),
            ext.due_date or event.get("Due Date", ""),
            ext.confidence,
            ext.notes or event.get("Notes", ""),
        ]
        self._update_row(self.events_sheet, event["_row"], row)

    # ---------- EventApplications ----------

    def get_event_links(self):
        values = self._get_sheet_values(self.event_apps_sheet)
        if not values:
            return []

        headers = values[0]
        rows = []
        for i, row in enumerate(values[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            item = dict(zip(headers, padded))
            item["_row"] = i
            rows.append(item)
        return rows

    def link_event_to_application(self, event_id: str, application_id: str):
        existing = self.get_event_links()
        for row in existing:
            if row.get("Event ID") == event_id and row.get("Application ID") == application_id:
                return

        self._append_row(self.event_apps_sheet, [event_id, application_id])

    # ---------- Review queue ----------

    def enqueue_review(self, reason: str, ext):
        row = [
            "NOW",
            reason,
            ext.company or "",
            ext.role_display or "",
            ext.role_key or "",
            ext.job_id or "",
            ext.status or "",
            ext.confidence,
            ext.notes or "",
        ]
        self._append_row(self.review_sheet, row)