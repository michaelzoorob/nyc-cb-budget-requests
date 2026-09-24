#!/usr/bin/env python3
"""Fetch + parse every NYC community board's FY2027 Statement PDF (in parallel),
build each board's two-stage detailed sheet, and combine into one all-boards CSV.
Committees: Queens CB2 exact (from its committee form); all other boards inferred
from the responsible agency + request text (CB2's committee taxonomy)."""
import collections
import concurrent.futures
import glob
import os
import subprocess
import sys
import urllib.request
import pandas as pd

PREFIX = {1: "MN", 2: "BX", 3: "BK", 4: "QN", 5: "SI"}
MAXCB = {1: 12, 2: 12, 3: 18, 4: 14, 5: 3}            # 59 boards total
BASE = "https://raw.githubusercontent.com/NYCPlanning/labs-cd-needs-statements/master"
HERE = os.path.dirname(os.path.abspath(__file__))   # sibling pipeline scripts
REGISTER = "Register_FY2027_allboards.csv"
FORM = "Submitting Budget Requests to Budget Committee (Responses) - Form Responses 1.csv"


def fetch_parse(boro, cb):
    pre = PREFIX[boro]
    code = f"{pre}{cb:02d}"
    url = f"{BASE}/{pre}%20DNS%20FY%202027/FY2027_Statement_{code}.pdf"
    pdf, txt, out = f"/tmp/{code}.pdf", f"/tmp/{code}.txt", f"parsed_{code}.csv"
    if not os.path.exists(txt):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research"})
            open(pdf, "wb").write(urllib.request.urlopen(req, timeout=90).read())
        except Exception:
            return (boro, cb, code, "NO_PDF", 0)
        subprocess.run(["pdftotext", "-layout", pdf, txt], capture_output=True)
    subprocess.run(["python3", os.path.join(HERE, "parse_statement_pdf.py"), txt, out], capture_output=True)
    n = 0
    if os.path.exists(out):
        try:
            n = len(pd.read_csv(out, dtype=str))
        except Exception:
            n = 0
    return (boro, cb, code, "PARSED" if n else "PARSE_FAIL", n)


# --reuse-parsed skips the download + PDF parse and rebuilds from the parsed_*.csv
# already in the working directory. Use it when only the build logic or the
# committee labels changed; the Statement PDFs themselves don't change.
REUSE = "--reuse-parsed" in sys.argv
tasks = [(b, cb) for b in PREFIX for cb in range(1, MAXCB[b] + 1)]
for _f in glob.glob("out_*.csv") + ([] if REUSE else glob.glob("parsed_*.csv")):
    os.remove(_f)
if REUSE:
    parsed = []
    for b, cb in tasks:
        code = f"{PREFIX[b]}{cb:02d}"
        n = len(pd.read_csv(f"parsed_{code}.csv", dtype=str)) if os.path.exists(f"parsed_{code}.csv") else 0
        parsed.append((b, cb, code, "PARSED" if n else "NO_PARSED_CSV", n))
else:
    sys.stderr.write(f"Fetching + parsing {len(tasks)} boards (parallel)...\n")
    sys.stderr.flush()
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        parsed = list(ex.map(lambda t: fetch_parse(*t), tasks))

ok = [p for p in parsed if p[3] == "PARSED"]
sys.stderr.write(f"Parsed OK: {len(ok)}/{len(tasks)}\n")
for b, cb, code, st, n in parsed:
    if st != "PARSED":
        sys.stderr.write(f"  FAIL {code}: {st}\n")

dfs = []
for boro, cb, code, st, n in ok:
    out = f"out_{code}.csv"
    args = ["python3", os.path.join(HERE, "build_statement_sheet.py"), str(boro), f"{cb:02d}",
            f"parsed_{code}.csv", REGISTER, out]
    if code == "QN02":
        args.append(FORM)
    r = subprocess.run(args, capture_output=True, text=True)
    if "fell back" in r.stderr:     # requests with no committee label yet
        sys.stderr.write(f"  {code}:{r.stderr.strip().split('committees:', 1)[-1]}\n")
    if os.path.exists(out):
        dfs.append(pd.read_csv(out, dtype=str))
    else:
        sys.stderr.write(f"  BUILD FAIL {code}: {r.stderr.strip()[:160]}\n")

allb = pd.concat(dfs, ignore_index=True).fillna("")
allb.to_csv("CB FY2027 Requests (all boards, detailed, 2-stage).csv", index=False)
sys.stderr.write(f"COMBINED: {len(allb)} rows across {allb['Board'].nunique()} boards\n")
sys.stderr.write(str(dict(sorted(collections.Counter(allb["Board"]).items()))) + "\n")
