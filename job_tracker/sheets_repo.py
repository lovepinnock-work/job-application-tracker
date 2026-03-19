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

    def _row_from_dict(self, headers, data: dict):
        return [data.get(h, "") for h in headers]

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

    def clear_sheet_data(self, sheet_name: str):
        values = self._get_sheet_values(sheet_name)
        if len(values) <= 1:
            return

        end_row = len(values)
        rng = f"{sheet_name}!A2:Z{end_row}"
        body = {"values": []}

        self.service.spreadsheets().values().clear(
            spreadsheetId=self.spreadsheet_id,
            range=rng,
            body={}
        ).execute()


    def clear_all_test_data(self):
        self.clear_sheet_data(self.applications_sheet)
        self.clear_sheet_data(self.events_sheet)
        self.clear_sheet_data(self.event_apps_sheet)
        self.clear_sheet_data(self.review_sheet)

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

        values = self._get_sheet_values(self.applications_sheet)
        headers = values[0]

        data = {
            "Company": ext.company,
            "Status": ext.status or "Awaiting",
            "Date Applied": ext.application_date or "NOW",
            "Last Updated": ext.application_date or ext.event_date or ext.due_date or "NOW",
            "Role Display": ext.role_display,
            "Job ID": ext.job_id,
            "Interview Date": "",
            "Assessment Date": "",
            "Offer Due Date": "",
            "Notes": ext.notes or "",
            "Role Key": ext.role_key,
            "Confidence": ext.confidence,
            "Application ID": application_id,
            "App Key": app_key,
        }

        row = self._row_from_dict(headers, data)

        self._append_row(self.applications_sheet, row)

        return self.find_application_by_app_key(app_key)

    def update_application_status(self, app: dict, ext, new_status: str):
        values = self._get_sheet_values(self.applications_sheet)
        headers = values[0]

        data = dict(app)

        data["Status"] = new_status
        data["Last Updated"] = ext.application_date or ext.event_date or ext.due_date or "NOW"
        data["Confidence"] = ext.confidence
        if ext.notes:
            data["Notes"] = ext.notes

        row = self._row_from_dict(headers, data)

        self._update_row(self.applications_sheet, app["_row"], row)

    def refresh_application(self, app: dict, ext):
        values = self._get_sheet_values(self.applications_sheet)
        headers = values[0]

        data = dict(app)

        data["Last Updated"] = ext.application_date or ext.event_date or ext.due_date or "NOW"
        data["Confidence"] = ext.confidence

        row = self._row_from_dict(headers, data)

        self._update_row(self.applications_sheet, app["_row"], row)

    def reset_for_reapply(self, app: dict, ext):
        values = self._get_sheet_values(self.applications_sheet)
        headers = values[0]

        data = dict(app)

        data["Status"] = "Awaiting"
        data["Date Applied"] = ext.application_date or "NOW"
        data["Last Updated"] = ext.application_date or "NOW"
        data["Interview Date"] = ""
        data["Assessment Date"] = ""
        data["Offer Due Date"] = ""
        data["Confidence"] = ext.confidence

        row = self._row_from_dict(headers, data)

        self._update_row(self.applications_sheet, app["_row"], row)

    def update_application_event_fields(self, app: dict, ext, fallback_status: str):
        values = self._get_sheet_values(self.applications_sheet)
        headers = values[0]

        data = dict(app)

        data["Status"] = ext.status or fallback_status
        data["Last Updated"] = ext.event_date or ext.application_date or ext.due_date or "NOW"

        if ext.event_type == "Interview":
            data["Interview Date"] = ext.event_date

        elif ext.event_type == "Assessment":
            data["Assessment Date"] = ext.due_date or ext.event_date

        elif ext.event_type == "Offer":
            data["Offer Due Date"] = ext.due_date

        data["Confidence"] = ext.confidence

        row = self._row_from_dict(headers, data)

        self._update_row(self.applications_sheet, app["_row"], row)

    # ---------- Events ----------

    def get_events(self):
        values = self._get_sheet_values(self.events_sheet)
        if not values:
            return []

        headers = [str(h).strip() for h in values[0]]
        rows = []

        for i, row in enumerate(values[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            item = dict(zip(headers, padded))
            item["_row"] = i
            rows.append(item)

        return rows

    def create_event(self, event_key: str, ext):
        event_id = str(uuid.uuid4())

        values = self._get_sheet_values(self.events_sheet)
        headers = values[0]

        data = {
            "Event ID": event_id,
            "Event Key": event_key,
            "Company": ext.company or "",
            "Event Type": ext.event_type or "",
            "Event Status": ext.event_status or "",
            "Event Date": ext.event_date or "",
            "Due Date": ext.due_date or "",
            "Confidence": ext.confidence,
            "Notes": ext.notes or "",
        }

        row = self._row_from_dict(headers, data)
        self._append_row(self.events_sheet, row)

        return self.find_event_by_event_key(event_key)

    def find_event_by_event_key(self, event_key: str):
        if not event_key:
            return None

        rows = self.get_events()
        for row in rows:
            candidate = str(row.get("Event Key", "")).strip()
            if candidate == event_key.strip():
                return row
        return None

    def update_event(self, event: dict, ext):
        values = self._get_sheet_values(self.events_sheet)
        headers = values[0]

        data = dict(event)

        if ext.event_status:
            data["Event Status"] = ext.event_status
        if ext.event_date:
            data["Event Date"] = ext.event_date
        if ext.due_date:
            data["Due Date"] = ext.due_date

        data["Confidence"] = ext.confidence
        if ext.notes:
            data["Notes"] = ext.notes

        row = self._row_from_dict(headers, data)
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

        values = self._get_sheet_values(self.event_apps_sheet)
        headers = values[0]

        data = {
            "Event ID": event_id,
            "Application ID": application_id,
        }

        row = self._row_from_dict(headers, data)
        self._append_row(self.event_apps_sheet, row)

    # ---------- Review queue ----------

    def enqueue_review(self, reason: str, ext):
        values = self._get_sheet_values(self.review_sheet)
        headers = values[0]

        data = {
            "Company": ext.company or "",
            "Reason": reason,
            "Created At": "NOW",
            "Role Display": ext.role_display or "",
            "Role Key": ext.role_key or "",
            "Job ID": ext.job_id or "",
            "Status": ext.status or "",
            "Confidence": ext.confidence,
            "Notes": ext.notes or "",
        }

        row = self._row_from_dict(headers, data)
        self._append_row(self.review_sheet, row)