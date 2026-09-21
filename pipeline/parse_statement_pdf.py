#!/usr/bin/env python3
"""Parse the FY2027 'Statement of Community District Needs' PDF (QN02) into
structured rows. Each request is a 2-column block: the board's explanation on
the left, the agency's full response (prefixed 'Agency Response:') on the right.
Outputs a CSV with the detailed responses the open-data Register lacks."""
import re
import sys
import csv

TXT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/qn02.txt"
OUT = sys.argv[2] if len(sys.argv) > 2 else "QN02_FY2027_statement_parsed.csv"

lines = open(TXT, encoding="utf-8").read().split("\n")

# The right column ("Agency Response:") starts at a fixed character column.
cols = [l.index("Agency Response:") for l in lines if "Agency Response:" in l]
SPLIT = max(set(cols), key=cols.count)

HDR = re.compile(r"^\s*(?:(\d+) of (\d+)|(CS))\s+(.*?)\s{2,}(\S.*?)\s*$")
PAGENUM = re.compile(r"^\s*\d+\s*$")
SKIP = re.compile(r"^\s*(CAPITAL BUDGET REQUESTS|EXPENSE BUDGET REQUESTS|Agency\s+Priority\s+Title)\s*$", re.I)
DIV = re.compile(r"^\s*(CAPITAL|EXPENSE) BUDGET REQUESTS\s*$", re.I)   # Capital/Expense section

rows = []
section = None
i = 0
while i < len(lines):
    dm = DIV.match(lines[i])
    if dm:
        section = "Capital" if dm.group(1).upper() == "CAPITAL" else "Expense"
        i += 1
        continue
    m = HDR.match(lines[i])
    if not m:
        i += 1
        continue
    entry_section = section
    if m.group(3):                      # "CS" = sited capital request (no "N of M")
        pri, denom = "CS", ""
    else:
        pri, denom = m.group(1), m.group(2)
    title, agency = m.group(4), m.group(5)
    # continuation lines of the title/type (indented, before the blank line)
    sub = []
    j = i + 1
    while j < len(lines) and lines[j].strip() and not HDR.match(lines[j]):
        sub.append(lines[j].strip())
        j += 1
    req_type = " ".join(sub)
    while j < len(lines) and not lines[j].strip():   # skip blanks
        j += 1
    # collect the body block (until the next header), drop page-number lines
    body = []
    while j < len(lines) and not HDR.match(lines[j]):
        dm2 = DIV.match(lines[j])
        if dm2:
            section = "Capital" if dm2.group(1).upper() == "CAPITAL" else "Expense"
        elif not PAGENUM.match(lines[j]) and not SKIP.match(lines[j]):
            body.append(lines[j])
        j += 1
    # the right column starts where "Agency Response:" begins in THIS entry
    arcol = next((b.index("Agency Response:") for b in body if "Agency Response:" in b), SPLIT)
    left, right = [], []
    for b in body:
        lt, rt = b[:arcol].rstrip(), b[arcol:].strip()
        if lt:
            left.append(lt)
        if rt:
            right.append(rt)
    response = re.sub(r"^Agency Response:\s*", "", " ".join(right)).strip()
    rows.append({
        "priority": pri,
        "list_of": denom,                         # 42 = expense list, else capital
        "track": entry_section if entry_section in ("Capital", "Expense") else ("Expense" if denom == "42" else "Capital"),
        "agency": agency,
        "title": title.strip(),
        "request_type": req_type,
        "explanation": " ".join(left).strip(),
        "response": response,
    })
    i = j

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"SPLIT column = {SPLIT}")
print(f"Parsed entries: {len(rows)}")
from collections import Counter
print("list_of distribution:", dict(Counter(r["list_of"] for r in rows)))
print("rows with empty response:", sum(1 for r in rows if not r["response"]))
print()
nb = [r for r in rows if "Northern Blvd" in r["title"] or "Northern Boulevard" in r["explanation"]]
for r in nb:
    print("=== VERIFY:", r["title"], "|", r["agency"], "| priority", r["priority"], r["track"])
    print("   explanation:", r["explanation"])
    print("   RESPONSE:", r["response"])
