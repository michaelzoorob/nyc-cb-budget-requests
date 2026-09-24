#!/usr/bin/env python3
"""Build a fiscal year's all-boards sheet from NYC Open Data's Register alone.

    build_register_year.py FY OUT_CSV

Used for FY2020-FY2025, whose Statement PDFs either list requests with no agency
responses (FY2017-FY2023) or repeat the Register's text in a table (FY2024-FY2025).
Also used by build_all_boards.py for individual boards in a PDF year whose PDF has
no per-request responses (every Bronx board in FY2026).

Every column comes from the Register: Title is its "request" field (DCP's standard
request category; boards' own titles only appear in the FY2026+ PDFs), Agency
Response is the January agency round, OMB Executive Response the April/May round.
Output has the same columns as the PDF years.
"""
import os
import sys
import urllib.parse
import urllib.request

import pandas as pd

from shared import (AGENCY, AGENCY_ABBR, COLS, PUBLICATIONS, REG_BORO_ABBR, REGISTER_AGENCY_NAMES,
                    infer_committees, load_labels, request_id, stance)

BOARD_ORDER = ["M", "BX", "BK", "Q", "SI"]   # same board order as the PDF years


def fetch_register(fy, path):
    """This year's agency round + OMB Executive round, all boards."""
    where = " OR ".join(f"publication='{p}'" for p in PUBLICATIONS[fy])
    url = "https://data.cityofnewyork.us/resource/vn4m-mk4t.csv?" + urllib.parse.urlencode({
        "$select": "publication,boro,board,priority,tracking_code,request,explanation,"
                   "response,responded_by,responsible_agency",
        "$where": where, "$limit": "20000"})
    req = urllib.request.Request(url, headers={"User-Agent": "research"})
    open(path, "wb").write(urllib.request.urlopen(req, timeout=180).read())


def board_label(boro, board):
    return REG_BORO_ABBR[str(boro)] + "CB" + str(int(board))


def build(fy, register_csv, boards=None):
    """Rows for fiscal year fy; boards (e.g. {"BXCB1"}) restricts to those boards."""
    agency_round, omb_round = PUBLICATIONS[fy]
    d = pd.read_csv(register_csv, dtype=str).fillna("")
    d["Board"] = [board_label(b, c) for b, c in zip(d["boro"], d["board"])]
    if boards is not None:
        d = d[d["Board"].isin(boards)]
    ag = d[d["publication"] == agency_round].set_index("tracking_code")
    om = d[d["publication"] == omb_round].set_index("tracking_code")
    # Some requests appear in only one round; keep every tracking code from either.
    base = pd.concat([ag, om[~om.index.isin(ag.index)]])
    labels = load_labels()
    known = set(AGENCY.values())
    rows, unmapped = [], {}
    for tc, r in base.iterrows():
        agency = REGISTER_AGENCY_NAMES.get(r["responsible_agency"], r["responsible_agency"])
        if agency not in known:
            unmapped[agency] = unmapped.get(agency, 0) + 1
        pr = r["priority"].strip()
        title, expl = r["request"], r["explanation"]
        a_resp = ag.at[tc, "response"] if tc in ag.index else ""
        o_resp = om.at[tc, "response"] if tc in om.index else ""
        rid = request_id(r["Board"], title, expl)
        rows.append({
            "Priority": str(int(pr)) if pr.isdigit() else pr,
            "Type": "Expense" if tc.strip().endswith("E") else "Capital",
            "Board": r["Board"], "Agency": agency, "Title": title, "Explanation": expl,
            "Agency Response": a_resp, "OMB Executive Response": o_resp,
            "Agency Stance (MZ added)": stance(a_resp),
            "Committees": "|".join(labels.get(rid) or infer_committees(title, expl, AGENCY_ABBR.get(agency))),
        })
    out = pd.DataFrame(rows, columns=COLS)
    if unmapped:
        sys.stderr.write(f"  FY{fy}: agency names kept as they appear in the Register "
                         f"(not on the FY2027 dashboard): {unmapped}\n")
    out["_b"] = out["Board"].map(lambda b: (BOARD_ORDER.index(b.split("CB")[0]), int(b.split("CB")[1])))
    out["_t"] = out["Type"].map({"Capital": 0, "Expense": 1})
    out["_p"] = pd.to_numeric(out["Priority"], errors="coerce")
    return out.sort_values(["_b", "_t", "_p"]).drop(columns=["_b", "_t", "_p"]).reset_index(drop=True)


if __name__ == "__main__":
    fy, dest = sys.argv[1], sys.argv[2]
    reg = f"Register_FY{fy}_allboards.csv"
    if not os.path.exists(reg):
        sys.stderr.write(f"Downloading the FY{fy} Register ({' + '.join(PUBLICATIONS[fy])})...\n")
        fetch_register(fy, reg)
    out = build(fy, reg)
    out.to_csv(dest, index=False)
    lab = load_labels()
    n_lab = sum(request_id(b, t, e) in lab for b, t, e in zip(out.Board, out.Title, out.Explanation))
    sys.stderr.write(f"COMBINED FY{fy}: {len(out)} rows across {out['Board'].nunique()} boards "
                     f"(Register only); committees from labels for {n_lab}, rule for {len(out) - n_lab}\n")
