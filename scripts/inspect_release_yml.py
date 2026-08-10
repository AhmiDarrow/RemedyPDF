"""One-shot: print TOKEN-related lines from release.yml."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
t = p.read_text(encoding="utf-8")
print("lines", len(t.splitlines()))
for i, line in enumerate(t.splitlines(), 1):
    if any(k in line for k in ("TOKEN", "token", "softprops", "GITHUB_")):
        print(f"{i}: {line}")
print("TOKEN_OK" if "secrets.GITHUB_TOKEN" in t and "GITHUB_[redacted]" not in t else "TOKEN_BAD")
