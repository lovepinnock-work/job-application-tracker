### Utilites used in tracking app

import re
from typing import Optional

def norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def make_app_key(company, role_key, job_id):
    if not company or not role_key:
        return None

    base = f"{norm(company)}||{norm(role_key)}"

    if job_id:
        return f"{base}||{norm(job_id)}"

    return base