from pathlib import Path
from datetime import datetime

from digests import build_daily_digest


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

date_str = datetime.now().strftime("%Y-%m-%d")

digest = build_daily_digest()

file_path = STATE_DIR / f"daily_digest_{date_str}.txt"

file_path.write_text(digest, encoding="utf-8")

print(digest)
print(f"\nSaved to: {file_path}")