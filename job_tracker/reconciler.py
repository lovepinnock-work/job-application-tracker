from util import make_app_key, make_event_key, norm


class Reconciler:
    def __init__(self, repo):
        self.repo = repo

    def process(self, ext):
        if not ext.is_job_related:
            print("ignored")
            return {"result": "ignored", "needs_review": False}

        app_key = make_app_key(ext.company, ext.role_key, ext.job_id)

        if ext.email_type == "application_confirmation":
            return self._handle_application_confirmation(ext, app_key)

        elif ext.email_type == "rejection":
            return self._handle_status_update(ext, app_key, "Rejected")

        elif ext.email_type == "canceled":
            return self._handle_status_update(ext, app_key, "Canceled")

        elif ext.email_type in {
            "assessment_invite",
            "assessment_completed",
            "assessment_passed",
            "assessment_failed",
        }:
            return self._handle_event(ext, app_key, "Assessment")

        elif ext.email_type in {"interview_invite", "interview_completed"}:
            return self._handle_event(ext, app_key, "Interviewing")

        elif ext.email_type in {"offer", "offer_deadline"}:
            return self._handle_event(ext, app_key, "Offer")

        self.repo.enqueue_review("unhandled email_type", ext)
        return {"result": "review", "needs_review": True}

    def _handle_application_confirmation(self, ext, app_key):
        if not app_key:
            print("missing app key for application_confirmation")
            self.repo.enqueue_review("missing app key", ext)
            return {"result": "review", "needs_review": True}

        app = self.repo.find_application_by_app_key(app_key)

        if app:
            if app.get("Status") in {"Rejected", "Canceled"}:
                print(f"reapply detected: {app_key}")
                self.repo.reset_for_reapply(app, ext)
                return {"result": "reapplied", "needs_review": False}
            else:
                print(f"refresh existing application: {app_key}")
                self.repo.refresh_application(app, ext)
                return {"result": "updated", "needs_review": False}
        else:
            print(f"new application: {app_key}")
            self.repo.create_application(ext, app_key)
            return {"result": "created", "needs_review": False}

    def _handle_status_update(self, ext, app_key, new_status):
        if not app_key:
            print(f"missing app key for {new_status.lower()}")
            self.repo.enqueue_review(f"missing app key for {new_status.lower()}", ext)
            return {"result": "review", "needs_review": True}

        app = self.repo.find_application_by_app_key(app_key)
        if app:
            print(f"updated to {new_status.lower()}: {app_key}")
            self.repo.update_application_status(app, ext, new_status)
            return {"result": "updated", "needs_review": False}
        else:
            print(f"{new_status.lower()} but no matching application: {app_key}")
            self.repo.enqueue_review(f"{new_status.lower()} but no matching application", ext)
            return {"result": "review", "needs_review": True}

    def _handle_event(self, ext, app_key, fallback_status):
        target_apps = self._resolve_target_applications(ext, app_key)

        if not target_apps:
            print("event found but no matching applications")
            self.repo.enqueue_review("event found but no matching applications", ext)
            return {"result": "review", "needs_review": True}

        normalized_event_date = (ext.event_date or "")[:10] if ext.event_date else ""
        normalized_due_date = (ext.due_date or "")[:10] if ext.due_date else ""

        event_key = make_event_key(
            ext.company,
            ext.event_type,
            normalized_event_date,
            normalized_due_date,
            "",
        )

        event = self.repo.find_event_by_event_key(event_key)
        if event:
            self.repo.update_event(event, ext)
            event_id = event["Event ID"]
        else:
            event = self.repo.create_event(event_key, ext)
            if not event:
                self.repo.enqueue_review("event creation failed", ext)
                return {"result": "review", "needs_review": True}
            event_id = event["Event ID"]

        for app in target_apps:
            self.repo.link_event_to_application(event_id, app["Application ID"])
            self.repo.update_application_event_fields(app, ext, fallback_status)

        print(f"linked event {event_id} to {len(target_apps)} application(s)")
        return {"result": "event_linked", "needs_review": False}

    def _resolve_target_applications(self, ext, app_key):
        matches = []

        # 1) Direct app key match
        if app_key:
            app = self.repo.find_application_by_app_key(app_key)
            if app:
                matches.append(app)

        # 2) Explicit targets in extraction
        if ext.application_targets and ext.company:
            target_norms = {norm(t) for t in ext.application_targets if t}
            open_apps = self.repo.get_open_applications_by_company(ext.company)

            for app in open_apps:
                role_key_norm = norm(app.get("Role Key"))
                job_id_norm = norm(app.get("Job ID"))

                if role_key_norm in target_norms or (job_id_norm and job_id_norm in target_norms):
                    if app not in matches:
                        matches.append(app)

        # 3) Shared event applies to all open apps at company
        if ext.shared_event and ext.company:
            open_apps = self.repo.get_open_applications_by_company(ext.company)
            for app in open_apps:
                if app not in matches:
                    matches.append(app)

        # 4) Fallback for generic single-company event emails
        if not matches and ext.company and ext.event_type:
            open_apps = self.repo.get_open_applications_by_company(ext.company)

            if len(open_apps) == 1:
                matches.extend(open_apps)
            elif len(open_apps) > 1 and ext.event_type == "Assessment":
                matches.extend(open_apps)

        return matches