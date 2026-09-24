#!/usr/bin/env python3
"""Build one fiscal year's all-boards CSV.

    build_all_boards.py [--fy YEAR] [--reuse-parsed]

PDF years (shared.PDF_YEARS): fetch + parse every board's Statement PDF in
parallel, build each board's two-stage sheet with build_statement_sheet.py, and
combine. Other years come from the Register alone via build_register_year.py.
Either way the output is "CB FY<YEAR> Requests (all boards, detailed, 2-stage).csv"
in the working directory, with the same columns.

Committees: Queens CB2's FY2027 requests take theirs from CB2's committee form;
everything else comes from committee_labels.csv (see label_committees/).
"""
import collections
import concurrent.futures
import glob
import os
import subprocess
import sys
import urllib.request

import pandas as pd

from build_register_year import build as build_from_register, fetch_register
from shared import BORO_ABBR, LATEST, PDF_YEARS, PUBLICATIONS

PREFIX = {1: "MN", 2: "BX", 3: "BK", 4: "QN", 5: "SI"}
MAXCB = {1: 12, 2: 12, 3: 18, 4: 14, 5: 3}            # 59 boards total
BASE = "https://raw.githubusercontent.com/NYCPlanning/labs-cd-needs-statements/master"
HERE = os.path.dirname(os.path.abspath(__file__))   # sibling pipeline scripts
FORM = "Submitting Budget Requests to Budget Committee (Responses) - Form Responses 1.csv"
FORM_YEAR = "2027"                                  # the year CB2's committee form covers

FY = sys.argv[sys.argv.index("--fy") + 1] if "--fy" in sys.argv else LATEST
# --reuse-parsed skips the download + PDF parse and rebuilds from the parsed CSVs
# already in the working directory. Use it when only the build logic or the
# committee labels changed; the Statement PDFs themselves don't change.
REUSE = "--reuse-parsed" in sys.argv
OUT_CSV = f"CB FY{FY} Requests (all boards, detailed, 2-stage).csv"
REGISTER = f"Register_FY{FY}_allboards.csv"

if FY not in PUBLICATIONS:
    sys.exit(f"Unknown fiscal year {FY}; known: {sorted(PUBLICATIONS)}")
if FY not in PDF_YEARS:
    sys.exit(subprocess.run(["python3", os.path.join(HERE, "build_register_year.py"), FY, OUT_CSV]).returncode)


def fetch_parse(boro, cb):
    pre = PREFIX[boro]
    code = f"{pre}{cb:02d}"
    url = f"{BASE}/{pre}%20DNS%20FY%20{FY}/FY{FY}_Statement_{code}.pdf"
    pdf, txt, out = f"/tmp/FY{FY}_{code}.pdf", f"/tmp/FY{FY}_{code}.txt", f"parsed_FY{FY}_{code}.csv"
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


if not os.path.exists(REGISTER):
    sys.stderr.write(f"Downloading the FY{FY} Register ({' + '.join(PUBLICATIONS[FY])})...\n")
    fetch_register(FY, REGISTER)

tasks = [(b, cb) for b in PREFIX for cb in range(1, MAXCB[b] + 1)]
for _f in glob.glob(f"out_FY{FY}_*.csv") + ([] if REUSE else glob.glob(f"parsed_FY{FY}_*.csv")):
    os.remove(_f)
if REUSE:
    parsed = []
    for b, cb in tasks:
        code = f"{PREFIX[b]}{cb:02d}"
        f = f"parsed_FY{FY}_{code}.csv"
        n = len(pd.read_csv(f, dtype=str)) if os.path.exists(f) else 0
        parsed.append((b, cb, code, "PARSED" if n else "NO_PARSED_CSV", n))
else:
    sys.stderr.write(f"Fetching + parsing {len(tasks)} FY{FY} Statements (parallel)...\n")
    sys.stderr.flush()
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        parsed = list(ex.map(lambda t: fetch_parse(*t), tasks))

ok = [p for p in parsed if p[3] == "PARSED"]
sys.stderr.write(f"Parsed OK: {len(ok)}/{len(tasks)}\n")
for b, cb, code, st, n in parsed:
    if st != "PARSED":
        sys.stderr.write(f"  FAIL {code}: {st}\n")

built = {}
env = dict(os.environ, CB_FY=FY)
for boro, cb, code, st, n in ok:
    out = f"out_FY{FY}_{code}.csv"
    args = ["python3", os.path.join(HERE, "build_statement_sheet.py"), str(boro), f"{cb:02d}",
            f"parsed_FY{FY}_{code}.csv", REGISTER, out]
    if code == "QN02" and FY == FORM_YEAR and os.path.exists(FORM):
        args.append(FORM)
    r = subprocess.run(args, capture_output=True, text=True, env=env)
    if os.path.exists(out):
        df = pd.read_csv(out, dtype=str).fillna("")
        # A PDF must describe this board's own requests. Rows join to the Register on
        # explanation text, which matches ~98% for a correct file. DCP's FY2026 file
        # for Manhattan CB7 holds CB6's requests and matches 0%; such a board falls
        # back to the Register below.
        matched = (df["OMB Executive Response"] != "").mean() if len(df) else 0
        if matched < 0.5:
            sys.stderr.write(f"  {code}: PDF requests match only {matched:.0%} of this board's "
                             f"Register entries (wrong board's file?); using the Register\n")
        else:
            built[code] = df
            if "fell back" in r.stderr:     # requests with no committee label yet
                sys.stderr.write(f"  {code}:{r.stderr.strip().split('committees:', 1)[-1]}\n")
    else:
        sys.stderr.write(f"  BUILD FAIL {code}: {r.stderr.strip()[:160]}\n")

# A board whose PDF has no per-request responses (all 12 Bronx boards in FY2026)
# gets that year's rows from the Register instead, with the same columns.
code_to_board = {f"{PREFIX[b]}{cb:02d}": BORO_ABBR[str(b)] + "CB" + str(cb) for b, cb in tasks}
missing = [c for c in code_to_board if c not in built]
if missing:
    reg_rows = build_from_register(FY, REGISTER, {code_to_board[c] for c in missing})
    for c in missing:
        rows = reg_rows[reg_rows["Board"] == code_to_board[c]]
        if len(rows):
            built[c] = rows
    got = [c for c in missing if c in built]
    sys.stderr.write(f"  from the Register instead of the PDF: {len(got)} boards {got}\n")
    if len(got) < len(missing):
        sys.stderr.write(f"  NO DATA in either source: {[c for c in missing if c not in built]}\n")

allb = pd.concat([built[c] for c in code_to_board if c in built], ignore_index=True).fillna("")
allb.to_csv(OUT_CSV, index=False)
sys.stderr.write(f"COMBINED FY{FY}: {len(allb)} rows across {allb['Board'].nunique()} boards\n")
sys.stderr.write(str(dict(sorted(collections.Counter(allb["Board"]).items()))) + "\n")
