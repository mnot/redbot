# === pyproject-tmpl: managed file (do not edit; overwritten by `make update-pyproject`) ===
import pathlib, re, sys

START_RE = re.compile(r'\s*# === pyproject-tmpl: start "([^"]+)" ===\s*')
END_RE = re.compile(r'\s*# === pyproject-tmpl: end "([^"]+)" ===\s*')
MANAGED_RE = re.compile(r'#.*pyproject-tmpl')

def extract(text):
    out = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = START_RE.fullmatch(lines[i])
        if m:
            name = m.group(1)
            j = i + 1
            while j < len(lines):
                em = END_RE.fullmatch(lines[j])
                if em and em.group(1) == name:
                    out[name] = lines[i+1:j]
                    i = j
                    break
                j += 1
            else:
                sys.exit(f"ERROR: region {name!r} not closed in {sys.argv[1]}")
        i += 1
    return out

def merge(template_text, local_regions):
    lines = template_text.splitlines()
    out, seen = [], set()
    i = 0
    while i < len(lines):
        m = START_RE.fullmatch(lines[i])
        if m:
            name = m.group(1)
            seen.add(name)
            out.append(lines[i])
            j = i + 1
            while j < len(lines):
                em = END_RE.fullmatch(lines[j])
                if em and em.group(1) == name:
                    out.extend(local_regions.get(name, lines[i+1:j]))
                    out.append(lines[j])
                    i = j
                    break
                j += 1
            else:
                sys.exit(f"ERROR: template region {name!r} not closed")
        else:
            out.append(lines[i])
        i += 1
    return seen, out

def skeleton_lines(text):
    """Return list of lines outside any project region (template-managed portion)."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = START_RE.fullmatch(lines[i])
        if m:
            name = m.group(1)
            out.append(lines[i])
            j = i + 1
            while j < len(lines):
                em = END_RE.fullmatch(lines[j])
                if em and em.group(1) == name:
                    out.append(lines[j])
                    i = j
                    break
                j += 1
            else:
                break
        else:
            out.append(lines[i])
        i += 1
    return out

local = pathlib.Path(sys.argv[1])
tmpl = pathlib.Path(sys.argv[2])
local_text = local.read_text() if local.exists() else None
tmpl_text = tmpl.read_text()
local_regions = extract(local_text) if local_text is not None else {}
seen, merged = merge(tmpl_text, local_regions)
# At-risk lines: present in local outside regions, absent from new template entirely.
# Only checked when adopting a file the template does not already manage; once managed,
# out-of-region content belongs to the template, so a dropped line is template churn.
at_risk = []
already_managed = local_text is not None and any(
    MANAGED_RE.search(line) for line in local_text.splitlines()
)
if local_text is not None and not already_managed:
    tmpl_lines = set(tmpl_text.splitlines())
    for line in skeleton_lines(local_text):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # blank or comment — not data-loss-critical
        if line not in tmpl_lines:
            at_risk.append(line)
if at_risk:
    print(f"  NOTE: {local}: {len(at_risk)} line(s) not present in new template; appended for manual triage", file=sys.stderr)
    merged.extend([
        "",
        "# === pyproject-tmpl: MIGRATION NEEDED ===",
        "# The lines below were in your prior file but are not in the new template.",
        "# Move what you still want into a named region above, then delete this section.",
        "# ---",
    ])
    for line in at_risk:
        merged.append("# " + line)
for orphan in sorted(set(local_regions) - seen):
    print(f"  WARNING: {local}: local region {orphan!r} has no slot in template; content dropped", file=sys.stderr)
local.write_text("\n".join(merged) + "\n")
