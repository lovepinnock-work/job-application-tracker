

from util import make_app_key


class Reconciler:

    def __init__(self):
        self.apps = {}  # app_key -> row

    def process(self, ext):

        if not ext.is_job_related:
            print("ignored")
            return

        app_key = make_app_key(ext.company, ext.role_key, ext.job_id)

        if not app_key:
            print("missing key")
            return

        app = self.apps.get(app_key)

        if ext.email_type == "application_confirmation":

            if app:
                if app["Status"] in ["Rejected", "Canceled"]:
                    print("reapply detected")
                    app["Status"] = "Awaiting"
                else:
                    print("refresh")
            else:
                print("new application")

                self.apps[app_key] = {
                    "Company": ext.company,
                    "Role": ext.role_display,
                    "Status": "Awaiting",
                }

        elif ext.email_type == "rejection":

            if app:
                app["Status"] = "Rejected"
                print("updated to rejected")

            else:
                print("reject but no app")

        print(self.apps)