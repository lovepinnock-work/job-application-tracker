from sheets_repo import SheetsRepo
from review_helpers import (
    make_application_payload,
    make_event_payload,
    make_event_application_link,
)


def prompt(text, default=None):
    if default is not None:
        value = input(f"{text} [{default}]: ").strip()
        return value if value else default
    return input(f"{text}: ").strip()


def yes_no(text, default="y"):
    value = input(f"{text} ({'Y/n' if default == 'y' else 'y/N'}): ").strip().lower()
    if not value:
        value = default
    return value in {"y", "yes"}


def normalize(s):
    return (s or "").strip().lower()


def list_review_rows(repo):
    rows = repo.get_review_rows()
    rows = [r for r in rows if any(str(v).strip() for k, v in r.items() if not k.startswith("_"))]

    if not rows:
        print("No review rows found.")
        return []

    print("\nReview Queue Rows:")
    print("-" * 100)
    for row in rows:
        print(
            f'Row {row["_row"]}: '
            f'Company={row.get("Company", "")} | '
            f'Role={row.get("Role Display", "")} | '
            f'Reason={row.get("Reason", "")} | '
            f'Status={row.get("Status", "")}'
        )
    print("-" * 100)
    return rows


def list_applications(repo):
    apps = repo.get_applications()
    if not apps:
        print("No applications found.")
        return []

    print("\nApplications:")
    print("-" * 120)
    for app in apps:
        print(
            f'AppID={app.get("Application ID", "")} | '
            f'Company={app.get("Company", "")} | '
            f'Role={app.get("Role Display", "")} | '
            f'RoleKey={app.get("Role Key", "")} | '
            f'Status={app.get("Status", "")}'
        )
    print("-" * 120)
    return apps


def suggest_applications(repo, review):
    apps = repo.get_applications()
    if not apps:
        return []

    review_company = normalize(review.get("Company"))
    review_role_display = normalize(review.get("Role Display"))
    review_role_key = normalize(review.get("Role Key"))
    review_job_id = normalize(review.get("Job ID"))

    scored = []

    for app in apps:
        score = 0

        app_company = normalize(app.get("Company"))
        app_role_display = normalize(app.get("Role Display"))
        app_role_key = normalize(app.get("Role Key"))
        app_job_id = normalize(app.get("Job ID"))

        if review_company and app_company == review_company:
            score += 5

        if review_job_id and app_job_id and review_job_id == app_job_id:
            score += 10

        if review_role_key and app_role_key and review_role_key == app_role_key:
            score += 8

        if review_role_display and app_role_display and review_role_display == app_role_display:
            score += 6

        if (
            review_role_display
            and app_role_display
            and (review_role_display in app_role_display or app_role_display in review_role_display)
        ):
            score += 3

        if score > 0:
            scored.append((score, app))

    scored.sort(key=lambda x: (-x[0], x[1].get("Company", ""), x[1].get("Role Display", "")))
    return [app for _, app in scored[:5]]


def choose_application_id(repo, review):
    suggestions = suggest_applications(repo, review)

    if suggestions:
        print("\nSuggested application matches:")
        print("-" * 120)
        for idx, app in enumerate(suggestions, start=1):
            print(
                f'[{idx}] AppID={app.get("Application ID", "")} | '
                f'Company={app.get("Company", "")} | '
                f'Role={app.get("Role Display", "")} | '
                f'RoleKey={app.get("Role Key", "")} | '
                f'Status={app.get("Status", "")}'
            )
        print("-" * 120)

        choice = prompt("Pick suggestion number, type an Application ID manually, or leave blank to skip", "")
        if not choice:
            return None

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(suggestions):
                return suggestions[idx - 1].get("Application ID", "")

        return choice

    print("\nNo strong application suggestions found.")
    if yes_no("Show all applications?", "n"):
        list_applications(repo)

    application_id = prompt("Enter Application ID to link (leave blank to skip)", "")
    return application_id or None


def promote_to_application(repo, review):
    status = prompt("Application status", review.get("Status") or "Awaiting")
    date_applied = prompt("Date applied (YYYY-MM-DD)", review.get("Created At"))
    notes = prompt("Notes", review.get("Notes", ""))

    confidence_val = None
    if review.get("Confidence"):
        try:
            confidence_val = float(review["Confidence"])
        except Exception:
            confidence_val = None

    payload = make_application_payload(
        company=review.get("Company", ""),
        role_display=review.get("Role Display", ""),
        role_key=review.get("Role Key", ""),
        job_id=review.get("Job ID", ""),
        status=status,
        date_applied=date_applied or None,
        notes=notes,
        confidence=confidence_val,
    )

    repo.append_application_from_payload(payload)

    print("\nCreated Application:")
    for k, v in payload.items():
        print(f"{k}: {v}")

    if yes_no("Clear review row now?", "y"):
        repo.clear_review_row(review["_row"])
        print("Review row cleared.")


def promote_to_event(repo, review):
    event_type = prompt("Event type", "Assessment")
    event_status = prompt("Event status", "Open")
    event_date = prompt("Event date (YYYY-MM-DD)", review.get("Created At"))
    due_date = prompt("Due date (YYYY-MM-DD)", "")
    notes = prompt("Notes", review.get("Notes", ""))

    confidence_val = None
    if review.get("Confidence"):
        try:
            confidence_val = float(review["Confidence"])
        except Exception:
            confidence_val = None

    event_payload = make_event_payload(
        company=review.get("Company", ""),
        event_type=event_type,
        event_status=event_status,
        event_date=event_date or None,
        due_date=due_date or None,
        notes=notes,
        confidence=confidence_val,
    )

    repo.append_event_from_payload(event_payload)

    print("\nCreated Event:")
    for k, v in event_payload.items():
        print(f"{k}: {v}")

    if yes_no("Link this event to an application?", "y"):
        application_id = choose_application_id(repo, review)
        if application_id:
            link_payload = make_event_application_link(
                event_id=event_payload["Event ID"],
                application_id=application_id,
            )
            repo.append_event_application_link_from_payload(link_payload)

            print("\nCreated EventApplications link:")
            for k, v in link_payload.items():
                print(f"{k}: {v}")
        else:
            print("Skipped linking event to application.")

    if yes_no("Clear review row now?", "y"):
        repo.clear_review_row(review["_row"])
        print("Review row cleared.")


def clear_review_only(repo, review):
    if yes_no("Are you sure you want to clear this review row without promoting it?", "n"):
        repo.clear_review_row(review["_row"])
        print("Review row cleared.")
    else:
        print("Canceled.")


def main():
    repo = SheetsRepo()

    rows = list_review_rows(repo)
    if not rows:
        return

    row_num_raw = prompt("Enter ReviewQueue row number to act on")
    try:
        row_num = int(row_num_raw)
    except ValueError:
        print("Invalid row number.")
        return

    review = repo.get_review_row_by_index(row_num)
    if not review:
        print(f"Review row {row_num} not found.")
        return

    print("\nSelected Review Row:")
    for k, v in review.items():
        if not k.startswith("_"):
            print(f"{k}: {v}")

    choice = prompt("Choose action: application / event / clear", "application").lower()

    if choice == "application":
        promote_to_application(repo, review)
    elif choice == "event":
        promote_to_event(repo, review)
    elif choice == "clear":
        clear_review_only(repo, review)
    else:
        print("Invalid choice. Use 'application', 'event', or 'clear'.")


if __name__ == "__main__":
    main()