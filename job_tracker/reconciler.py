from util import make_app_key, make_event_key, norm


class Reconciler:
    def __init__(self, repo):
        self.repo = repo

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
            self._handle_event(ext, app_key, "Assessment")

        elif ext.email_type in {"interview_invite", "interview_completed"}:
            self._handle_event(ext, app_key, "Interviewing")

        elif ext.email_type in {"offer", "offer_deadline"}:
            self._handle_event(ext, app_key, "Offer")

    def _handle_application_confirmation(self, ext, app_key):
        if not app_key:
            print("missing app key for application_confirmation")
            self.repo.enqueue_review("missing app key", ext)
            return

        app = self.repo.find_application_by_app_key(app_key)

        if app:
            if app["Status"] in {"Rejected", "Canceled"}:
                print(f"reapply detected: {app_key}")
                self.repo.reset_for_reapply(app, ext)
            else:
                print(f"refresh existing application: {app_key}")
                self.repo.refresh_application(app, ext)
        else:
            print(f"new application: {app_key}")
            self.repo.create_application(ext, app_key)

    def _handle_status_update(self, ext, app_key, new_status):
        if not app_key:
            print(f"missing app key for {new_status.lower()}")
            self.repo.enqueue_review(f"missing app key for {new_status.lower()}", ext)
            return

        app = self.repo.find_application_by_app_key(app_key)
        if app:
            print(f"updated to {new_status.lower()}: {app_key}")
            self.repo.update_application_status(app, ext, new_status)
        else:
            print(f"{new_status.lower()} but no matching application: {app_key}")
            self.repo.enqueue_review(f"{new_status.lower()} but no matching application", ext)

    def _handle_event(self, ext, app_key, fallback_status):
        target_apps = self._resolve_target_applications(ext, app_key)

        if not target_apps:
            print("event found but no matching applications")
            self.repo.enqueue_review("event found but no matching applications", ext)
            return

        if ext.event_type == "Assessment":
            normalized_event_date = (ext.event_date or "")[:10] if ext.event_date else ""
            normalized_due_date = (ext.due_date or "")[:10] if ext.due_date else ""
        else:
            normalized_event_date = (ext.event_date or "")[:10] if ext.event_date else ""
            normalized_due_date = (ext.due_date or "")[:10] if ext.due_date else ""

        event_key = make_event_key(
            ext.company,
            ext.event_type,
            normalized_event_date,
            normalized_due_date,
            ""
        )

        event = self.repo.find_event_by_event_key(event_key)
        if event:
            self.repo.update_event(event, ext)
            event_id = event["Event ID"]
        else:
            event = self.repo.create_event(event_key, ext)
            event_id = event["Event ID"]

        for app in target_apps:
            self.repo.link_event_to_application(event_id, app["Application ID"])
            self.repo.update_application_event_fields(app, ext, fallback_status)

        print(f"linked event {event_id} to {len(target_apps)} application(s)")

    def _resolve_target_applications(self, ext, app_key):
        matches = []

        if app_key:
            app = self.repo.find_application_by_app_key(app_key)
            if app:
                matches.append(app)

        if ext.application_targets and ext.company:
            target_norms = {norm(t) for t in ext.application_targets if t}
            open_apps = self.repo.get_open_applications_by_company(ext.company)
            for app in open_apps:
                role_key_norm = norm(app.get("Role Key"))
                job_id_norm = norm(app.get("Job ID"))
                if role_key_norm in target_norms or (job_id_norm and job_id_norm in target_norms):
                    if app not in matches:
                        matches.append(app)

        if ext.shared_event and ext.company:
            open_apps = self.repo.get_open_applications_by_company(ext.company)
            for app in open_apps:
                if app not in matches:
                    matches.append(app)

        if not matches and ext.company and ext.event_type:
            open_apps = self.repo.get_open_applications_by_company(ext.company)

            if len(open_apps) == 1:
                matches.extend(open_apps)
            elif len(open_apps) > 1 and ext.event_type == "Assessment":
                matches.extend(open_apps)

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
            