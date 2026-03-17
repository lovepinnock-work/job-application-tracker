import uuid

from util import make_app_key, make_event_key, norm


class Reconciler:
    def __init__(self):
        # app_key -> application row
        self.apps = {}

        # event_id -> event row
        self.events = {}

        # list of {"EventID": ..., "ApplicationID": ...}
        self.event_links = []

    def process(self, ext):
        if not ext.is_job_related:
            print("ignored")
            return

        app_key = make_app_key(ext.company, ext.role_key, ext.job_id)

        if ext.email_type == "application_confirmation":
            self._handle_application_confirmation(ext, app_key)

        elif ext.email_type == "rejection":
            self._handle_status_update(ext, app_key, "Rejected")

        elif ext.email_type == "canceled":
            self._handle_status_update(ext, app_key, "Canceled")

        elif ext.email_type in {"assessment_invite", "assessment_completed", "assessment_passed", "assessment_failed"}:
            self._handle_event(ext, app_key, fallback_status="Assessment")

        elif ext.email_type in {"interview_invite", "interview_completed"}:
            self._handle_event(ext, app_key, fallback_status="Interviewing")

        elif ext.email_type in {"offer", "offer_deadline"}:
            self._handle_event(ext, app_key, fallback_status="Offer")

        self._print_state()

    def _handle_application_confirmation(self, ext, app_key):
        if not app_key:
            print("missing app key for application_confirmation")
            return

        app = self.apps.get(app_key)

        if app:
            if app["Status"] in {"Rejected", "Canceled"}:
                print(f"reapply detected: {app_key}")
                app["Status"] = "Awaiting"
                app["Date Applied"] = ext.application_date or "NOW"
                app["Last Updated"] = ext.application_date or "NOW"
            else:
                print(f"refresh existing application: {app_key}")
                app["Last Updated"] = ext.application_date or "NOW"
        else:
            print(f"new application: {app_key}")
            self.apps[app_key] = {
                "ApplicationID": str(uuid.uuid4()),
                "Company": ext.company,
                "Role Display": ext.role_display,
                "Role Key": ext.role_key,
                "Job ID": ext.job_id,
                "App Key": app_key,
                "Status": ext.status or "Awaiting",
                "Date Applied": ext.application_date or "NOW",
                "Last Updated": ext.application_date or "NOW",
                "Interview Date": None,
                "Assessment Date": None,
                "Offer Due Date": None,
            }

    def _handle_status_update(self, ext, app_key, new_status):
        if not app_key:
            print(f"missing app key for {new_status.lower()}")
            return

        app = self.apps.get(app_key)
        if app:
            print(f"updated to {new_status.lower()}: {app_key}")
            app["Status"] = new_status
            app["Last Updated"] = ext.application_date or ext.event_date or "NOW"
        else:
            print(f"{new_status.lower()} but no matching application: {app_key}")

    def _handle_event(self, ext, app_key, fallback_status):
        target_apps = self._resolve_target_applications(ext, app_key)

        if not target_apps:
            print("event found but no matching applications")
            return

        # If this is an assessment completion, update an existing open event instead of creating a new one
        if ext.email_type in {"assessment_completed", "assessment_passed", "assessment_failed"}:
            event_id = self._find_existing_event_for_targets(ext, target_apps)

            if not event_id:
                event_id = self._create_event(ext)
            else:
                self._update_event(event_id, ext)

        else:
            event_id = self._find_existing_event_for_targets(ext, target_apps)
            if event_id:
                self._update_event(event_id, ext)
            else:
                event_id = self._create_event(ext)

        for app in target_apps:
            self._link_event_to_application(event_id, app["ApplicationID"])

            app["Status"] = ext.status or fallback_status
            app["Last Updated"] = ext.event_date or ext.application_date or ext.due_date or "NOW"

            if ext.event_type == "Assessment":
                app["Assessment Date"] = ext.due_date or ext.event_date or app["Assessment Date"]

            elif ext.event_type == "Interview":
                app["Interview Date"] = ext.event_date or app["Interview Date"]

            elif ext.event_type == "Offer":
                app["Offer Due Date"] = ext.due_date or app["Offer Due Date"]

        print(f"linked event {event_id} to {len(target_apps)} application(s)")

    def _create_event(self, ext):
        normalized_event_date = (ext.event_date or "")[:10] if ext.event_date else ""
        normalized_due_date = (ext.due_date or "")[:10] if ext.due_date else ""

        event_key = make_event_key(
            ext.company,
            ext.event_type,
            normalized_event_date,
            normalized_due_date,
            ""  # do not use message-specific value for event identity
        )

        for existing_id, event in self.events.items():
            if event["Event Key"] == event_key:
                return existing_id

        event_id = str(uuid.uuid4())
        self.events[event_id] = {
            "EventID": event_id,
            "Event Key": event_key,
            "Company": ext.company,
            "Event Type": ext.event_type,
            "Event Status": ext.event_status,
            "Event Date": ext.event_date,
            "Due Date": ext.due_date,
            "Confidence": ext.confidence,
            "Notes": ext.notes,
        }
        return event_id

    def _resolve_target_applications(self, ext, app_key):
        matches = []

        # Case 1: exact current app key match
        if app_key and app_key in self.apps:
            matches.append(self.apps[app_key])

        # Case 2: explicit application targets in email
        if ext.application_targets:
            target_norms = {norm(t) for t in ext.application_targets if t}
            for app in self.apps.values():
                role_key_norm = norm(app["Role Key"])
                job_id_norm = norm(app["Job ID"])
                if role_key_norm in target_norms or (job_id_norm and job_id_norm in target_norms):
                    if app not in matches:
                        matches.append(app)

        # Case 3: shared event -> all open apps at same company
        if ext.shared_event and ext.company:
            company_norm = norm(ext.company)
            for app in self.apps.values():
                if norm(app["Company"]) == company_norm and app["Status"] not in {"Rejected", "Canceled", "Closed"}:
                    if app not in matches:
                        matches.append(app)

        # Case 4: fallback for generic event emails with no targets
        # If event email names a company and there are open apps there:
        if not matches and ext.company and ext.event_type:
            company_norm = norm(ext.company)
            company_open_apps = [
                app for app in self.apps.values()
                if norm(app["Company"]) == company_norm and app["Status"] not in {"Rejected", "Canceled", "Closed"}
            ]

            if len(company_open_apps) == 1:
                matches.extend(company_open_apps)

            elif len(company_open_apps) > 1 and ext.event_type == "Assessment":
                # assessment emails are often shared across multiple active apps
                matches.extend(company_open_apps)

        return matches

    def _link_event_to_application(self, event_id, application_id):
        for link in self.event_links:
            if link["EventID"] == event_id and link["ApplicationID"] == application_id:
                return

        self.event_links.append({
            "EventID": event_id,
            "ApplicationID": application_id,
        })

    def _print_state(self):
        print("\nApplications:")
        for k, v in self.apps.items():
            print(k, "=>", v)

        print("\nEvents:")
        for k, v in self.events.items():
            print(k, "=>", v)

        print("\nEvent Links:")
        for link in self.event_links:
            print(link)

    def _find_existing_event_for_targets(self, ext, target_apps):
        target_app_ids = {app["ApplicationID"] for app in target_apps}

        for event_id, event in self.events.items():
            if event["Company"] != ext.company:
                continue
            if event["Event Type"] != ext.event_type:
                continue

            linked_app_ids = {
                link["ApplicationID"]
                for link in self.event_links
                if link["EventID"] == event_id
            }

            # overlap means likely same event chain
            if linked_app_ids & target_app_ids:
                # Prefer existing open assessment/interview/offer event
                if event["Event Status"] in {"Open", "Scheduled"}:
                    return event_id

        return None


    def _update_event(self, event_id, ext):
        event = self.events[event_id]

        # keep the best available values
        if ext.event_status:
            event["Event Status"] = ext.event_status
        if ext.event_date:
            event["Event Date"] = ext.event_date
        if ext.due_date:
            event["Due Date"] = ext.due_date
        if ext.confidence is not None:
            event["Confidence"] = ext.confidence
        if ext.notes:
            event["Notes"] = ext.notes
            