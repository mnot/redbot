# === pyproject-tmpl: managed file (do not edit; overwritten by `make update-pyproject`) ===
import datetime, json, pathlib, re, sys, urllib.request

with urllib.request.urlopen("https://endoflife.date/api/python.json") as resp:
    data = json.load(resp)

today = datetime.date.today().isoformat()
versions = sorted(
    [c["cycle"] for c in data
     if c.get("eol") and c["eol"] > today and not c["cycle"].startswith("2.")],
    key=lambda v: tuple(int(x) for x in v.split(".")),
)
if not versions:
    print("ERROR: no supported Python versions returned", file=sys.stderr)
    sys.exit(1)
print(f"Currently supported Python: {', '.join(versions)}")

def patch(path, pattern, replacement):
    p = pathlib.Path(path)
    if not p.exists():
        return
    original = p.read_text()
    updated = re.sub(pattern, replacement, original, flags=re.M)
    if updated != original:
        p.write_text(updated)
        print(f"  patched {path}")

oldest = versions[0]
patch("pyproject.toml",
      r'^(requires-python\s*=\s*">=)\d+\.\d+(")',
      rf'\g<1>{oldest}\g<2>')
quoted = ", ".join(f'"{v}"' for v in versions)
patch(".github/workflows/test.yml",
      r"(python-version:\s*)\[[^\]]*\]",
      rf"\g<1>[{quoted}]")
