#!/usr/bin/env python3
"""Build one community board's two-stage detailed sheet for a PDF year (FY2026, FY2027).

Usage:
  build_statement_sheet.py BORO CB PDF_PARSED_CSV REGISTER_CSV OUT_CSV [COMMITTEE_FORM_CSV]

- Title / Explanation / Agency / full Agency Response  <- the Statement PDF parse.
  A title that wraps in the PDF is completed from the lines under it, which also
  hold DCP's request category.
- Type (Capital/Expense)                                <- the PDF's capital and expense sections.
- OMB Executive Response                                <- the open Register, matched one-to-one
  to each PDF request by its explanation text (then type and priority). A request
  whose text cannot be compared pairs on type, priority and DCP category when that
  combination is unique.
- Register requests that appear nowhere in the PDF are added from the Register.
- Agency Stance (MZ added)                              <- from the agency response.
- Committees                                           <- CB2: from the committee form
  (when supplied); otherwise from committee_labels.csv (model-assigned, see
  label_committees/README.md), falling back to an agency + keyword rule for any
  request that has no label yet.
- Label ID                                             <- the request id the committee label is keyed by.
"""
import collections
import os
import re
import sys
import difflib
from collections import defaultdict

import pandas as pd

from shared import (AGENCY, AGENCY_ABBR, AGENCY_COMMITTEE, BORO_ABBR, COLS, EI_KEYWORDS, LATEST, REG_BORO,
                    REGISTER_AGENCY_NAMES, STANCE_OVERRIDE, infer_committees, load_labels, norm, request_id, stance)

BORO = sys.argv[1]
CB = sys.argv[2]
PDF_CSV = sys.argv[3]
REG_CSV = sys.argv[4]
OUT = sys.argv[5]
FORM_CSV = sys.argv[6] if len(sys.argv) > 6 else None

# Fiscal year: set by build_all_boards.py (CB_FY). Defaults to the latest year.
FY = os.environ.get("CB_FY", LATEST)
BOARD = BORO_ABBR.get(BORO, BORO) + "CB" + str(int(CB))         # e.g. QCB1, QCB2


def jk(s):
    """Join key: norm() plus collapsed whitespace. The Register often puts two spaces
    after a period where the PDF has one. (norm() itself must stay as it is, because
    request_id() depends on it.)"""
    return re.sub(r"\s+", " ", norm(s)).strip()


def ratio(a, b):
    # autojunk=False: difflib's default treats frequent characters in long strings as
    # junk and badly underrates near-identical explanations.
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def reg_priority(pr, tc):
    """The Register numbers continued-support (CS) requests; the PDFs print "CS"."""
    if str(tc).strip().endswith("CS"):
        return "CS"
    pr = str(pr).strip()
    return str(int(pr)) if pr.isdigit() else pr


# --- Register: this board's requests for the year ---
d = pd.read_csv(REG_CSV, dtype=str).fillna("")
d["fy"] = d["tracking_code"].str[3:7]
q = d[(d["boro"] == REG_BORO.get(BORO, BORO)) & (d["board"].isin([CB, str(int(CB))])) & (d["fy"] == FY)]
omb = q[q["responded_by"] == "OMB"].reset_index(drop=True)
agency_round = {tc: r for tc, r in zip(q.loc[q["responded_by"] != "OMB", "tracking_code"],
                                       q.loc[q["responded_by"] != "OMB", "response"])}
omb["type"] = omb["tracking_code"].str.strip().str.endswith("E").map({True: "Expense", False: "Capital"})
omb["pri"] = [reg_priority(p, tc) for p, tc in zip(omb["priority"], omb["tracking_code"])]
omb["key"] = omb["explanation"].map(jk)
omb["cat"] = omb["request"].map(lambda c: re.sub(r"\s+", " ", c).strip().lower())
# DCP's request categories, used to split a wrapped title from the category line under it.
CATEGORIES = sorted({re.sub(r"\s+", " ", c).strip() for c in d["request"] if c.strip()}, key=len, reverse=True)

# --- Statement PDF parse ---
p = pd.read_csv(PDF_CSV, dtype=str).fillna("")


def split_category(request_type):
    """The lines under a PDF header hold any wrapped title text followed by DCP's
    category. Return (wrapped title text, category), or ("", "") when no known
    category ends the block, in which case the title is left as it is."""
    t = re.sub(r"\s+", " ", str(request_type)).strip()
    tl = t.lower()
    for c in CATEGORIES:
        if tl.endswith(c.lower()):
            return t[:len(t) - len(c)].strip(), c.lower()
    return "", ""


cont = p["request_type"].map(lambda r: split_category(r)[0])
p["cat"] = p["request_type"].map(lambda r: split_category(r)[1])
p["title"] = [(ti + " " + c).strip() if c else ti for ti, c in zip(p["title"], cont)]
n_retitled = int((cont != "").sum())
p["Type"] = p["track"].map(lambda t: t if t in ("Capital", "Expense") else "Expense")
p["pri"] = p["priority"]
# DCP printed a few explanations as a spreadsheet error, "#NAME?". Such a row has no
# text to match on, and after matching it takes the Register's explanation.
name_err = p["explanation"].str.strip() == "#NAME?"
p["key"] = ["" if bad else jk(e) for bad, e in zip(name_err, p["explanation"])]

# --- One-to-one match of PDF requests to Register requests ---
match = {}                                   # PDF row -> Register row
used = set()
by_key = defaultdict(list)
for j, (k, ty) in enumerate(zip(omb["key"], omb["type"])):
    by_key[k].append(j)
# 1. identical explanation (type and then priority break ties between duplicates)
for i, (k, ty, pr) in enumerate(zip(p["key"], p["Type"], p["pri"])):
    cands = [j for j in by_key.get(k, []) if j not in used] if k else []
    if cands:
        cands.sort(key=lambda j: (omb.at[j, "type"] != ty, omb.at[j, "pri"] != pr))
        match[i] = cands[0]
        used.add(cands[0])
# 2. near-identical explanation, same type, best pairs first
pairs = []
for i in range(len(p)):
    if i in match or not p.at[i, "key"]:
        continue
    for j in range(len(omb)):
        if j in used or omb.at[j, "type"] != p.at[i, "Type"]:
            continue
        s = ratio(p.at[i, "key"], omb.at[j, "key"])
        if s >= 0.7:
            pairs.append((s, omb.at[j, "pri"] == p.at[i, "pri"], i, j))
for s, _, i, j in sorted(pairs, reverse=True):
    if i not in match and j not in used:
        match[i] = j
        used.add(j)
# 3. the PDF's "Location: <streets> <request>" wording around a Register text too
#    short to score ("Repave Roadway.")
for i in range(len(p)):
    if i in match or not p.at[i, "key"]:
        continue
    pk = " " + p.at[i, "key"]
    cands = [j for j in range(len(omb)) if j not in used and omb.at[j, "type"] == p.at[i, "Type"]
             and len(omb.at[j, "key"].split()) >= 2 and pk.endswith(" " + omb.at[j, "key"])]
    if cands:
        cands.sort(key=lambda j: (omb.at[j, "pri"] != p.at[i, "pri"], -len(omb.at[j, "key"])))
        match[i] = cands[0]
        used.add(cands[0])
# 4. the same wording: the Register's words mostly appear inside the PDF explanation
for i in range(len(p)):
    if i in match:
        continue
    pw = set(p.at[i, "key"].split())
    best, bestov = None, 0.0
    for j in range(len(omb)):
        if j in used or omb.at[j, "type"] != p.at[i, "Type"]:
            continue
        rw = set(omb.at[j, "key"].split())
        if len(rw) >= 4 and pw:
            ov = len(rw & pw) / len(rw)
            if ov > bestov:
                best, bestov = j, ov
    if best is not None and bestov >= 0.8:
        match[i] = best
        used.add(best)
# 5. what is left pairs on type, priority and DCP category, when that combination is
#    unique on both sides ("#NAME?" rows, text too garbled to compare)
slot = lambda ty, pr, cat: (ty, pr, cat) if cat else None
left_p = collections.Counter(slot(p.at[i, "Type"], p.at[i, "pri"], p.at[i, "cat"]) for i in range(len(p)) if i not in match)
left_r = collections.defaultdict(list)
for j in range(len(omb)):
    if j not in used:
        left_r[slot(omb.at[j, "type"], omb.at[j, "pri"], omb.at[j, "cat"])].append(j)
n_slot = 0
for i in range(len(p)):
    k = slot(p.at[i, "Type"], p.at[i, "pri"], p.at[i, "cat"])
    if i not in match and k and left_p[k] == 1 and len(left_r.get(k, [])) == 1:
        match[i] = left_r[k][0]
        used.add(match[i])
        n_slot += 1

# A PDF must describe this board's own requests. A correct file matches ~98% of its
# requests to the board's Register entries; DCP's FY2026 file for Manhattan CB7 holds
# CB6's requests and matches none. Refuse such a file (only PDF rows count here, not
# the Register-only rows added below), and build_all_boards.py uses the Register.
if len(omb) and len(p) and len(match) / len(p) < 0.5:
    sys.exit(f"{BOARD}: PDF requests match only {len(match)}/{len(p)} of this board's Register "
             f"entries (wrong board's file?)")

p["OMB Executive Response"] = [omb.at[match[i], "response"] if i in match else "" for i in range(len(p))]
p["Tracking Code"] = [omb.at[match[i], "tracking_code"].strip() if i in match else "" for i in range(len(p))]
p["explanation"] = [(omb.at[match[i], "explanation"] if i in match else "") if bad else e
                    for i, (bad, e) in enumerate(zip(name_err, p["explanation"]))]
# An entry whose columns pdftotext interleaved (the parser flags it; one FY2027 entry)
# takes its text from the Register: the board's explanation, and the agency's
# disposition, which the OMB round repeats with the agency's explanation.
for i in [i for i in match if str(p.at[i, "garbled"] if "garbled" in p else 0) == "1"]:
    j = match[i]
    disp = agency_round.get(omb.at[j, "tracking_code"], "").strip()
    o = omb.at[j, "response"]
    p.at[i, "explanation"] = omb.at[j, "explanation"]
    p.at[i, "response"] = " ".join(o.replace("Explanation:", " ").split()) if disp and o.startswith(disp) else disp
    print(f"  {BOARD}: text for {p.at[i, 'title']!r} taken from the Register (columns interleaved in the PDF)",
          file=sys.stderr)
p["Board"] = BOARD
p["Agency"] = p["agency"].map(lambda a: AGENCY.get(a, a))
p["Agency Stance (MZ added)"] = [
    STANCE_OVERRIDE.get((FY, BOARD, norm(t))) or stance(r)
    for t, r in zip(p["title"], p["response"])]
p = p.rename(columns={"priority": "Priority", "title": "Title",
                      "explanation": "Explanation", "response": "Agency Response"})

# --- Register requests the PDF does not list ---
# Added from the Register, unless the request resembles a PDF row even loosely
# (which would make it a duplicate the matcher failed to pair).
extra = []
for j in range(len(omb)):
    if j in used:
        continue
    k = omb.at[j, "key"]
    if any(ratio(k, pk) >= 0.6 for pk in p["key"] if pk):
        continue
    r = omb.iloc[j]
    agency = REGISTER_AGENCY_NAMES.get(r["responsible_agency"], r["responsible_agency"])
    a_resp = agency_round.get(r["tracking_code"], "")
    extra.append({"Priority": r["pri"], "Type": r["type"], "Board": BOARD, "Agency": agency,
                  "Title": r["request"], "Explanation": r["explanation"], "Agency Response": a_resp,
                  "OMB Executive Response": r["response"], "Agency Stance (MZ added)": stance(a_resp),
                  "Tracking Code": r["tracking_code"].strip(),
                  "agency": AGENCY_ABBR.get(agency, "")})
if extra:
    p = pd.concat([p, pd.DataFrame(extra)], ignore_index=True).fillna("")

p["Label ID"] = [request_id(BOARD, t, e) for t, e in zip(p["Title"], p["Explanation"])]

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
    p["Committees"] = ["|".join(LABELS.get(i) or infer_committees(t, e, a))
                       for i, t, e, a in zip(p["Label ID"], p["Title"], p["Explanation"], p["agency"])]
    n_lab = sum(i in LABELS for i in p["Label ID"])
    if n_lab < len(p):
        print(f"  committees: {n_lab} from committee_labels.csv, "
              f"{len(p) - n_lab} fell back to the agency/keyword rule", file=sys.stderr)

p["_t"] = p["Type"].map({"Capital": 0, "Expense": 1}).fillna(2)
p["_p"] = pd.to_numeric(p["Priority"], errors="coerce")
p = p.sort_values(["_t", "_p"], kind="stable")

p[COLS].to_csv(OUT, index=False)

print(f"{BOARD}: {len(p)} rows -> {OUT}")
print(f"  OMB matched {len(match)} of {len(p) - len(extra)} PDF rows ({n_slot} by type, priority and category "
      f"alone); {len(extra)} Register-only rows added; {n_retitled} wrapped titles completed")
if extra:
    print(f"  added from the Register (not in the PDF): {len(extra)}", file=sys.stderr)
