#!/usr/bin/env python3
"""Build one community board's two-stage detailed sheet for a PDF year (FY2026, FY2027).

Usage:
  build_statement_sheet.py BORO CB PDF_PARSED_CSV REGISTER_CSV OUT_CSV [COMMITTEE_FORM_CSV]

- Title / Explanation / Agency / full Agency Response  <- the Statement PDF parse.
- OMB Executive Response + Type (Capital/Expense)      <- the open Register (joined by
  the board's explanation text); Type comes from the register tracking-code suffix,
  which is board-independent (the PDF's own "N of M" numbering is not).
- Agency Stance (MZ added)                              <- from the agency response.
- Committees                                           <- CB2: from the committee form
  (when supplied); otherwise from committee_labels.csv (model-assigned, see
  label_committees/README.md), falling back to an agency + keyword rule for any
  request that has no label yet.
"""
import os
import re
import sys
import difflib
import pandas as pd

from shared import (AGENCY, AGENCY_COMMITTEE, BORO_ABBR, COLS, EI_KEYWORDS, REG_BORO, STANCE_OVERRIDE,
                    infer_committees, load_labels, norm, request_id, stance)

BORO = sys.argv[1]
CB = sys.argv[2]
PDF_CSV = sys.argv[3]
REG_CSV = sys.argv[4]
OUT = sys.argv[5]
FORM_CSV = sys.argv[6] if len(sys.argv) > 6 else None

# Fiscal year: set by build_all_boards.py (CB_FY). Defaults to the latest year.
FY = os.environ.get("CB_FY", "2027")
BOARD = BORO_ABBR.get(BORO, BORO) + "CB" + str(int(CB))         # e.g. QCB1, QCB2


# --- Register: per-request OMB Executive response + tracking code, this board ---
d = pd.read_csv(REG_CSV, dtype=str).fillna("")
d["fy"] = d["tracking_code"].str[3:7]
q = d[(d["boro"] == REG_BORO.get(BORO, BORO)) & (d["board"].isin([CB, str(int(CB))])) & (d["fy"] == FY)]
omb = q[q["responded_by"] == "OMB"][["explanation", "response", "tracking_code"]]
reg = {norm(e): (r, tc) for e, r, tc in
       zip(omb["explanation"], omb["response"], omb["tracking_code"])}
keys = list(reg)
regw = [(kk, set(kk.split())) for kk in keys]


def lookup(k):
    if k in reg:
        return reg[k][0], reg[k][1], 1.0
    m = difflib.get_close_matches(k, keys, n=1, cutoff=0.7)
    if m:
        return reg[m[0]][0], reg[m[0]][1], difflib.SequenceMatcher(None, k, m[0]).ratio()
    pw = set(k.split())                       # word-overlap fallback: catches the PDF's
    if pw:                                     # "Location: <streets> <request>" wording where
        best, bestov = None, 0.0              # the register's words are mostly inside the PDF
        for kk, rw in regw:
            if len(rw) < 4:
                continue
            ov = len(rw & pw) / len(rw)
            if ov > bestov:
                bestov, best = ov, kk
        if best and bestov >= 0.8:
            return reg[best][0], reg[best][1], bestov
    return "", "", 0.0


def type_of(tc, title, expl):
    if tc:
        return "Expense" if str(tc).strip().endswith("E") else "Capital"
    t = (str(title) + " " + str(expl)).lower()            # fallback if unmatched
    return "Capital" if ("capital" in t and "expense" not in t) else "Expense"


# --- Statement PDF parse: detailed agency responses ---
p = pd.read_csv(PDF_CSV, dtype=str).fillna("")
p["key"] = p["explanation"].map(norm)
res = [lookup(k) for k in p["key"]]
p["OMB Executive Response"] = [x[0] for x in res]
tcs = [x[1] for x in res]
p["_score"] = [x[2] for x in res]
p["Type"] = p["track"].map(lambda t: t if t in ("Capital", "Expense") else "Expense")
p["Board"] = BOARD
p["Agency"] = p["agency"].map(lambda a: AGENCY.get(a, a))
p["Agency Stance (MZ added)"] = [
    STANCE_OVERRIDE.get((FY, BOARD, norm(t))) or stance(r)
    for t, r in zip(p["title"], p["response"])]
p = p.rename(columns={"priority": "Priority", "title": "Title",
                      "explanation": "Explanation", "response": "Agency Response"})

# --- Committees (only when a committee form is supplied; CB2-specific) ---
if FORM_CSV:
    form = pd.read_csv(FORM_CSV, dtype=str).fillna("")
    fcom, fexpl, ftitle, fag = form.columns[2], form.columns[6], form.columns[13], form.columns[5]

    def clean(c):
        return re.sub(r"\s*committee$", "", str(c).strip(), flags=re.I)

    def cabbr(n):
        m = re.search(r"\(([A-Za-z]+)\)", str(n))
        return m.group(1).upper() if m else ""

    by_e, by_t, votes = {}, {}, {}
    for _, fr in form.iterrows():
        c = clean(fr[fcom])
        if not c:
            continue
        if norm(fr[fexpl]):
            by_e.setdefault(norm(fr[fexpl]), c)
        if norm(fr[ftitle]):
            by_t.setdefault(norm(fr[ftitle]), c)
        ab = cabbr(fr[fag])
        if ab:
            votes.setdefault(ab, {})
            votes[ab][c] = votes[ab].get(c, 0) + 1
    ag_def = {ab: max(v, key=v.get) for ab, v in votes.items()}
    ekeys, tkeys = list(by_e), list(by_t)

    def committees(title, expl, ab):
        ke, kt = norm(expl), norm(title)
        if ke in by_e:
            return [by_e[ke]]
        if kt in by_t:
            return [by_t[kt]]
        mm = difflib.get_close_matches(ke, ekeys, n=1, cutoff=0.72)
        if mm:
            return [by_e[mm[0]]]
        mm = difflib.get_close_matches(kt, tkeys, n=1, cutoff=0.72)
        if mm:
            return [by_t[mm[0]]]
        t = (str(title) + " " + str(expl)).lower()
        if EI_KEYWORDS.search(t):
            return ["Health and Human Services", "Engagement and Inclusion"]
        out = [ag_def.get(ab) or AGENCY_COMMITTEE.get(ab) or "City Services"]
        if ("memorial" in t or "monument" in t) and "Arts and Culture" not in out:
            out.append("Arts and Culture")
        return out[:3]

    p["Committees"] = ["|".join(committees(t, e, a))
                       for t, e, a in zip(p["Title"], p["Explanation"], p["agency"])]
else:
    LABELS = load_labels()
    ids = [request_id(BOARD, t, e) for t, e in zip(p["Title"], p["Explanation"])]
    p["Committees"] = ["|".join(LABELS.get(i) or infer_committees(t, e, a))
                       for i, t, e, a in zip(ids, p["Title"], p["Explanation"], p["agency"])]
    n_lab = sum(i in LABELS for i in ids)
    if n_lab < len(ids):
        print(f"  committees: {n_lab} from committee_labels.csv, "
              f"{len(ids) - n_lab} fell back to the agency/keyword rule", file=sys.stderr)

p["_t"] = p["Type"].map({"Capital": 0, "Expense": 1}).fillna(2)
p["_p"] = pd.to_numeric(p["Priority"], errors="coerce")
p = p.sort_values(["_t", "_p"])

p[COLS].to_csv(OUT, index=False)

print(f"{BOARD}: {len(p)} rows -> {OUT}")
print("  Type:", p["Type"].value_counts().to_dict(),
      "| Stance:", p["Agency Stance (MZ added)"].value_counts().to_dict())
print("  OMB match: exact=%d fuzzy=%d none=%d"
      % ((p._score == 1).sum(), ((p._score < 1) & (p._score > 0)).sum(), (p._score == 0).sum()))
