#!/usr/bin/env python3
"""Build one fiscal year's all-boards CSV.

    build_all_boards.py [--fy YEAR] [--reuse-parsed]

PDF years (shared.PDF_YEARS): fetch + parse every board's Statement PDF in
parallel, build each board's two-stage sheet with build_statement_sheet.py, and
combine. Other years come from the Register (build_register_year.py), plus the
Statement's request table for a board the Register lacks. Either way the output is
"CB FY<YEAR> Requests (all boards, detailed, 2-stage).csv" in the working
directory, with the same columns.

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

import difflib

from build_register_year import BOARD_ORDER, build as build_from_register, fetch_register
from parse_request_table import parse as parse_request_table, parse_five_column
from shared import (AGENCY, BORO_ABBR, COLS, LATEST, PDF_YEARS, PUBLICATIONS, infer_committees, load_labels,
                    norm, request_id, stance)

PREFIX = {1: "MN", 2: "BX", 3: "BK", 4: "QN", 5: "SI"}
MAXCB = {1: 12, 2: 12, 3: 18, 4: 14, 5: 3}            # 59 boards total
BASE = "https://raw.githubusercontent.com/NYCPlanning/labs-cd-needs-statements/master"
HERE = os.path.dirname(os.path.abspath(__file__))   # sibling pipeline scripts
FORM = "Submitting Budget Requests to Budget Committee (Responses) - Form Responses 1.csv"
FORM_YEAR = "2027"                                  # the year CB2's committee form covers

FY = sys.argv[sys.argv.index("--fy") + 1] if "--fy" in sys.argv else LATEST
# --reuse-parsed skips the download + PDF parse and rebuilds from the parsed CSVs
# already in the working directory. Use it when only the build logic after parsing
# or the committee labels changed. A full run re-downloads every PDF, since DCP does
# revise them (FY2027_Statement_QN02.pdf was revised in May 2026), and re-parses.
REUSE = "--reuse-parsed" in sys.argv
# PDFs and their pdftotext output are kept in the data directory, not /tmp, so a
# reboot cannot silently drop the text a reused build still needs.
CACHE = "statement_text"
os.makedirs(CACHE, exist_ok=True)
OUT_CSV = f"CB FY{FY} Requests (all boards, detailed, 2-stage).csv"
REGISTER = f"Register_FY{FY}_allboards.csv"

if FY not in PUBLICATIONS:
    sys.exit(f"Unknown fiscal year {FY}; known: {sorted(PUBLICATIONS)}")


def text_path(code):
    return f"{CACHE}/FY{FY}_{code}.txt"


def download_text(code):
    """Download one board's Statement PDF and convert it to layout text. Returns the
    text path, or None if the PDF does not exist."""
    pre = code[:2]
    url = f"{BASE}/{pre}%20DNS%20FY%20{FY}/FY{FY}_Statement_{code}.pdf"
    pdf, txt = f"{CACHE}/FY{FY}_{code}.pdf", text_path(code)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "research"})
        data = urllib.request.urlopen(req, timeout=90).read()
    except Exception:
        return None
    open(pdf, "wb").write(data)
    subprocess.run(["pdftotext", "-layout", pdf, txt], capture_output=True)
    return txt if os.path.exists(txt) else None


def ensure_text(code):
    return text_path(code) if os.path.exists(text_path(code)) else download_text(code)


def rows_in(csv_path):
    try:
        return len(pd.read_csv(csv_path, dtype=str))
    except Exception:                      # missing or empty file
        return 0


def fetch_parse(boro, cb):
    code = f"{PREFIX[boro]}{cb:02d}"
    out = f"parsed_FY{FY}_{code}.csv"
    txt = download_text(code)
    if not txt:
        return (boro, cb, code, "NO_PDF", 0)
    subprocess.run(["python3", os.path.join(HERE, "parse_statement_pdf.py"), txt, out], capture_output=True)
    n = rows_in(out)
    return (boro, cb, code, "PARSED" if n else "PARSE_FAIL", n)


# A board whose PDF has no per-request responses (every Bronx board in FY2026) gets
# that year's rows from the Register, which has the responses. Its PDF still has a
# four-column request table with the board's own titles, so those are restored. A
# board missing from the Register but present in its PDF (Bronx CB12 in FY2026) gets
# its requests from that table, with no responses.
def restore_titles(rows, table):
    """Set each Register row's Title to the board's own title from the PDF table.
    The row must match on section and priority and read like the same request, which
    keeps a wrong board's file (Manhattan CB7, FY2026) from supplying titles.
    Committees were assigned from the Register row, and its Label ID stays with it, so
    the labeling scripts keep reading the id the committee came from."""
    def sim(a, b):                      # autojunk misrates long, near-identical texts
        return difflib.SequenceMatcher(None, norm(a), norm(b), autojunk=False).ratio()
    rows = rows.copy()
    for i, r in rows.iterrows():
        cands = [t for t in table if t["section"] == r["Type"] and t["priority"] == r["Priority"]]
        best = max(cands, default=None, key=lambda t: sim(t["explanation"], r["Explanation"]))
        if best and best["title"] and sim(best["explanation"], r["Explanation"]) >= 0.6:
            rows.at[i, "Title"] = best["title"]
    return rows


def rows_from_table(table, board):
    labels = load_labels()
    out = []
    for t in table:
        agency = AGENCY.get(t["agency"], t["agency"])
        rid = request_id(board, t["title"], t["explanation"])
        out.append({"Priority": t["priority"], "Type": t["section"], "Board": board, "Agency": agency,
                    "Title": t["title"], "Explanation": t["explanation"], "Agency Response": "",
                    "OMB Executive Response": "", "Agency Stance (MZ added)": stance(""),
                    "Committees": "|".join(labels.get(rid) or infer_committees(t["title"], t["explanation"], t["agency"])),
                    "Label ID": rid})
    df = pd.DataFrame(out, columns=COLS)
    df["_t"] = df["Type"].map({"Capital": 0, "Expense": 1})
    df["_p"] = pd.to_numeric(df["Priority"], errors="coerce")
    return df.sort_values(["_t", "_p"]).drop(columns=["_t", "_p"]).reset_index(drop=True)


if not os.path.exists(REGISTER):
    sys.stderr.write(f"Downloading the FY{FY} Register ({' + '.join(PUBLICATIONS[FY])})...\n")
    fetch_register(FY, REGISTER)

tasks = [(b, cb) for b in PREFIX for cb in range(1, MAXCB[b] + 1)]
code_to_board = {f"{PREFIX[b]}{cb:02d}": BORO_ABBR[str(b)] + "CB" + str(cb) for b, cb in tasks}

if FY not in PDF_YEARS:
    # A Register year. A board the Register lacks can still list its requests in its
    # Statement (Brooklyn CB16 in FY2025); those are added without responses.
    out = build_from_register(FY, REGISTER)
    added, absent = [], []
    for code, board in code_to_board.items():
        if board in set(out["Board"]):
            continue
        txt = ensure_text(code)
        table = (parse_request_table(txt) or parse_five_column(txt)) if txt else []
        if table:
            out = pd.concat([out, rows_from_table(table, board)], ignore_index=True)
            added.append(f"{code} ({len(table)} requests)")
        else:
            absent.append(code)
    out["_b"] = out["Board"].map(lambda b: (BOARD_ORDER.index(b.split("CB")[0]), int(b.split("CB")[1])))
    out = out.sort_values("_b", kind="stable").drop(columns="_b")
    out.to_csv(OUT_CSV, index=False)
    lab = load_labels()
    n_lab = sum(i in lab for i in out["Label ID"])
    sys.stderr.write(f"COMBINED FY{FY}: {len(out)} rows across {out['Board'].nunique()} boards (Register"
                     f"{', plus Statement tables for ' + ', '.join(added) if added else ''}); committees from "
                     f"labels for {n_lab}, rule for {len(out) - n_lab}\n")
    if absent:
        sys.stderr.write(f"  in neither the Register nor a Statement: {absent}\n")
    sys.exit(0)


for _f in glob.glob(f"out_FY{FY}_*.csv") + ([] if REUSE else glob.glob(f"parsed_FY{FY}_*.csv")):
    os.remove(_f)
if REUSE:
    parsed = []
    for b, cb in tasks:
        code = f"{PREFIX[b]}{cb:02d}"
        n = rows_in(f"parsed_FY{FY}_{code}.csv")
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
        built[code] = pd.read_csv(out, dtype=str).fillna("")
        for line in r.stderr.strip().splitlines():   # label fallbacks, Register-only rows added
            sys.stderr.write(f"  {code}: {line.strip()}\n")
    else:
        # build_statement_sheet.py refuses a PDF whose requests don't match the board's
        # own Register entries (DCP's FY2026 Manhattan CB7 file holds CB6's requests);
        # such a board falls back to the Register below.
        sys.stderr.write(f"  {code}: {r.stderr.strip()[:200]}; using the Register\n")

missing = [c for c in code_to_board if c not in built]
if missing:
    reg_rows = build_from_register(FY, REGISTER, {code_to_board[c] for c in missing})
    via_reg, via_table, retitled = [], [], 0
    for c in missing:
        board = code_to_board[c]
        rows = reg_rows[reg_rows["Board"] == board]
        txt = ensure_text(c)
        table = parse_request_table(txt) if txt else []
        if len(rows):
            if table:
                new = restore_titles(rows, table)
                retitled += int((new["Title"] != rows["Title"]).sum())
                rows = new
            built[c] = rows
            via_reg.append(c)
        elif table:
            built[c] = rows_from_table(table, board)
            via_table.append(c)
    sys.stderr.write(f"  from the Register instead of the PDF: {len(via_reg)} boards {via_reg}"
                     f" ({retitled} titles restored from their PDF tables)\n")
    if via_table:
        sys.stderr.write(f"  from the PDF's request table only (no responses published): {via_table}\n")
    nodata = [c for c in missing if c not in built]
    if nodata:
        sys.stderr.write(f"  NO DATA in either source: {nodata}\n")

allb = pd.concat([built[c] for c in code_to_board if c in built], ignore_index=True).fillna("")
allb.to_csv(OUT_CSV, index=False)
sys.stderr.write(f"COMBINED FY{FY}: {len(allb)} rows across {allb['Board'].nunique()} boards\n")
sys.stderr.write(str(dict(sorted(collections.Counter(allb["Board"]).items()))) + "\n")
