import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sheets_repo import SheetsRepo


BASE_DIR = Path(__file__).resolve().parent.parent
RUN_LOG_FILE = BASE_DIR / "state" / "run_log.jsonl"


def _read_run_log():
    if not RUN_LOG_FILE.exists():
        return []

    rows = []
    with open(RUN_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def _parse_iso(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _filter_logs_since(hours=None, days=None):
    rows = _read_run_log()
    now = datetime.now(timezone.utc)

    if hours is not None:
        cutoff = now - timedelta(hours=hours)
    elif days is not None:
        cutoff = now - timedelta(days=days)
    else:
        cutoff = datetime.min.replace(tzinfo=timezone.utc)

    out = []
    for row in rows:
        ts = _parse_iso(row.get("ts"))
        if ts and ts >= cutoff:
            out.append(row)
    return out


def _applications_summary(repo: SheetsRepo):
    apps = repo.get_applications()
    status_counts = Counter()

    for app in apps:
        status = app.get("Status", "").strip() or "Unknown"
        status_counts[status] += 1

    return apps, status_counts


def build_daily_digest():
    repo = SheetsRepo()
    apps, status_counts = _applications_summary(repo)
    logs = _filter_logs_since(hours=24)

    result_counts = Counter()
    review_count = 0

    for row in logs:
        result = row.get("result") or "unknown"
        result_counts[result] += 1
        if row.get("needs_review"):
            review_count += 1

    lines = []
    lines.append("JobTracker Daily Digest")
    lines.append("")
    lines.append(f"Applications tracked: {len(apps)}")
    lines.append("")

    lines.append("Current application status breakdown:")
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")

    lines.append("")
    lines.append("Last 24 hours:")
    for result, count in sorted(result_counts.items()):
        lines.append(f"- {result}: {count}")
    lines.append(f"- review items: {review_count}")

    recent_reviews = [r for r in logs if r.get("needs_review")]
    if recent_reviews:
        lines.append("")
        lines.append("Recent review items:")
        for row in recent_reviews[-10:]:
            subj = row.get("subject", "")
            sender = row.get("from", "")
            lines.append(f"- {subj} | {sender}")

    return "\n".join(lines)


def build_weekly_digest():
    repo = SheetsRepo()
    apps, status_counts = _applications_summary(repo)
    logs = _filter_logs_since(days=7)

    result_counts = Counter()
    review_count = 0
    company_counts = Counter()

    for row in logs:
        result = row.get("result") or "unknown"
        result_counts[result] += 1
        if row.get("needs_review"):
            review_count += 1

    for app in apps:
        company = app.get("Company", "").strip()
        if company:
            company_counts[company] += 1

    lines = []
    lines.append("JobTracker Weekly Digest")
    lines.append("")
    lines.append(f"Applications tracked: {len(apps)}")
    lines.append("")

    lines.append("Current application status breakdown:")
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")

    lines.append("")
    lines.append("Last 7 days:")
    for result, count in sorted(result_counts.items()):
        lines.append(f"- {result}: {count}")
    lines.append(f"- review items: {review_count}")

    if company_counts:
        lines.append("")
        lines.append("Top companies in tracker:")
        for company, count in company_counts.most_common(10):
            lines.append(f"- {company}: {count}")

    return "\n".join(lines)