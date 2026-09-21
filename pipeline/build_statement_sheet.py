#!/usr/bin/env python3
"""Build one community board's FY2027 two-stage detailed sheet.

Usage:
  build_statement_sheet.py BORO CB PDF_PARSED_CSV REGISTER_CSV OUT_CSV [COMMITTEE_FORM_CSV]

- Title / Explanation / Agency / full Agency Response  <- the Statement PDF parse.
- OMB Executive Response + Type (Capital/Expense)      <- the open Register (joined by
  the board's explanation text); Type comes from the register tracking-code suffix,
  which is board-independent (the PDF's own "N of M" numbering is not).
- Agency Stance (MZ added)                              <- from the agency response.
- Committees                                           <- CB2: from the committee form
  (when supplied); all other boards: inferred from the agency + request text using
  CB2's committee taxonomy.
"""
import re
import sys
import difflib
import pandas as pd

BORO = sys.argv[1]
CB = sys.argv[2]
PDF_CSV = sys.argv[3]
REG_CSV = sys.argv[4]
OUT = sys.argv[5]
FORM_CSV = sys.argv[6] if len(sys.argv) > 6 else None

BORO_ABBR = {"1": "M", "2": "BX", "3": "BK", "4": "Q", "5": "SI"}
# The open Register codes boroughs ALPHABETICALLY (1=Bronx, 2=Brooklyn, 3=Manhattan,
# 4=Queens, 5=Staten Island) -- NOT the standard 1=Manhattan. Map our standard code
# (used for the PDF/board label) to the Register's code for the join.
REG_BORO = {"1": "3", "2": "1", "3": "2", "4": "4", "5": "5"}
BOARD = BORO_ABBR.get(BORO, BORO) + "CB" + str(int(CB))         # e.g. QCB1, QCB2

AGENCY = {
    "DCP": "Department of City Planning", "DOT": "Department of Transportation",
    "DCAS": "Department of Citywide Administrative Services",
    "DEP": "Department of Environmental Protection",
    "DPR": "Department of Parks & Recreation", "NYPD": "Police Department",
    "FDNY": "Fire Department", "DSNY": "Department of Sanitation",
    "DOE": "Department of Education", "DOHMH": "Dept. of Health & Mental Hygiene",
    "HPD": "Housing Preservation & Development", "DOB": "Department of Buildings",
    "DOITT": "Office of Technology & Innovation (DoITT)",
    "DFTA": "Department for the Aging", "DYCD": "Youth & Community Development",
    "HRA": "Human Resources Administration", "HHC": "NYC Health + Hospitals",
    "DCLA": "Department of Cultural Affairs", "SBS": "Small Business Services",
    "QL": "Queens Public Library", "NYCTA": "MTA / NYC Transit",
    "SCA": "School Construction Authority", "EDC": "Economic Development Corporation",
    "NYCHA": "NYC Housing Authority", "NYPL": "New York Public Library",
    "BPL": "Brooklyn Public Library", "DHS": "Department of Homeless Services",
    "OMB": "Office of Management & Budget", "ACS": "Administration for Children's Services",
    "LPC": "Landmarks Preservation Commission", "MOCJ": "Mayor's Office of Criminal Justice",
    "NYCEM": "NYC Emergency Management", "DCWP": "Dept. of Consumer & Worker Protection",
    "MOME": "Mayor's Office of Media & Entertainment",
    "CECM": "Citywide Event Coordination & Management",
    "CUNY": "City University of New York",
}


def stance(resp):
    """Classify from the leading disposition sentence only -- incidental phrases
    later in the prose ("NYC supports 100,000 youth jobs...") must not count."""
    t = " ".join(("" if resp is None else str(resp)).split()).strip()
    if not t or t.lower() == "nan":
        return "Neutral/Unclear"
    first = re.split(r"(?<=[.!?])\s", t)[0].lower()
    if "does not support" in first:
        return "Oppose"
    if "supports" in first or "recommends funding" in first:
        return "Support"
    return "Neutral/Unclear"


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower()).strip()


# Citywide agency -> CB2-style committee defaults, following CB2's own form
# assignments (DOT->Transportation, HPD/DCP/DOB/SBS->Land Use, DEP/NYPD/QL->City
# Services, DCAS/DOITT->Engagement and Inclusion...) and extended to agencies CB2
# never used. Anything unlisted falls to "City Services".
AGENCY_COMMITTEE = {
    "DOT": "Transportation", "NYCTA": "Transportation",
    "DPR": "Parks and Environment",
    "DCP": "Land Use", "HPD": "Land Use", "DOB": "Land Use", "SBS": "Land Use",
    "NYCHA": "Land Use", "EDC": "Land Use", "LPC": "Land Use",
    "DCLA": "Arts and Culture", "MOME": "Arts and Culture",
    # (DCAS/DOITT intentionally NOT mapped to CB2's "Engagement and Inclusion" --
    # that reflects CB2's language-access asks; citywide their requests are
    # facilities/IT, i.e. City Services.)
    "DOHMH": "Health and Human Services", "HHC": "Health and Human Services",
    "HRA": "Health and Human Services", "DFTA": "Health and Human Services",
    "DYCD": "Health and Human Services", "ACS": "Health and Human Services",
    "DHS": "Health and Human Services",
}


def infer_committees(title, expl, ab):
    """CB2-taxonomy committee guess for boards without a committee form.
    Agency decides the primary committee; the language-access/immigrant keyword
    only APPENDS Engagement and Inclusion (never replaces the topic). No
    memorial/monument rule here -- citywide it false-positives on park names
    ("Flushing Memorial Field") and landmark mentions."""
    t = (str(title) + " " + str(expl)).lower()
    out = [AGENCY_COMMITTEE.get(ab, "City Services")]
    if ("esol" in t or "language access" in t or "immigrant" in t) \
            and "Engagement and Inclusion" not in out:
        out.append("Engagement and Inclusion")
    return out


# Hand overrides (MZ's judgment where the standardized leading disposition is
# misleading). Keyed by (board, normalized title).
STANCE_OVERRIDE = {
    # "Agency supports but cannot accommodate" -- but the prose says Parks only
    # supports IF a formalized dog-run group exists, and none does, so Parks
    # currently does not support the funding ask.
    ("QCB1", "whitey ford field dogpark request"): "Oppose",
}


# --- Register: per-request OMB Executive response + tracking code, this board ---
d = pd.read_csv(REG_CSV, dtype=str).fillna("")
d["fy"] = d["tracking_code"].str[3:7]
q = d[(d["boro"] == REG_BORO.get(BORO, BORO)) & (d["board"].isin([CB, str(int(CB))])) & (d["fy"] == "2027")]
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
    STANCE_OVERRIDE.get((BOARD, norm(t))) or stance(r)
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
        if "esol" in t or "language access" in t or "immigrant" in t:
            return ["Health and Human Services", "Engagement and Inclusion"]
        out = [ag_def.get(ab) or AGENCY_COMMITTEE.get(ab) or "City Services"]
        if ("memorial" in t or "monument" in t) and "Arts and Culture" not in out:
            out.append("Arts and Culture")
        return out[:3]

    p["Committees"] = ["|".join(committees(t, e, a))
                       for t, e, a in zip(p["Title"], p["Explanation"], p["agency"])]
else:
    p["Committees"] = ["|".join(infer_committees(t, e, a))
                       for t, e, a in zip(p["Title"], p["Explanation"], p["agency"])]

p["_t"] = p["Type"].map({"Capital": 0, "Expense": 1}).fillna(2)
p["_p"] = pd.to_numeric(p["Priority"], errors="coerce")
p = p.sort_values(["_t", "_p"])

COLS = ["Priority", "Type", "Board", "Agency", "Title", "Explanation",
        "Agency Response", "OMB Executive Response", "Agency Stance (MZ added)", "Committees"]
p[COLS].to_csv(OUT, index=False)

print(f"{BOARD}: {len(p)} rows -> {OUT}")
print("  Type:", p["Type"].value_counts().to_dict(),
      "| Stance:", p["Agency Stance (MZ added)"].value_counts().to_dict())
print("  OMB match: exact=%d fuzzy=%d none=%d"
      % ((p._score == 1).sum(), ((p._score < 1) & (p._score > 0)).sum(), (p._score == 0).sum()))
