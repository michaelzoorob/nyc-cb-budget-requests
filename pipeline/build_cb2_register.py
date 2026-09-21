#!/usr/bin/env python3
"""
Reproduce the "CB2 FYxxxx Requests and Agency Responses" spreadsheet from the
NYC Open Data "Register of Community Board Budget Requests" dataset (vn4m-mk4t),
filtered to Queens Community Board 2 (Borough 4, CB 2).

Produces a TWO-STAGE view of the most recent fiscal year: each request appears
twice -- the Executive (OMB-updated) response first, then the Preliminary
(agency) response -- matching the layout of the FY2026 source file.

Accepts either the NYC Open Data CSV-export headers (display names with trailing
spaces) or the SODA API field names (boro/board/tracking_code/...).

Reproduces the user's "Instruction (MZ added)" annotation by reverse-engineering
the labeling logic from the FY2026 file (84.9% match; residual cases are
non-template agency responses the original labeled by hand/inconsistently).
"""
import sys
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "cb2_live.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else \
    "CB2 FY2027 Requests and Agency Responses - most recent budget requests and city responses.csv"

# Map both header styles (CSV export display names AND SODA API field names) to
# the target file's exact headers (note the double space in "Tracking  Code").
CANON = {
    "publication": "Publication",
    "boro": "Borough", "borough": "Borough",
    "board": "Community Board", "community board": "Community Board",
    "priority": "Priority",
    "tracking_code": "Tracking  Code", "tracking  code": "Tracking  Code",
    "request": "Request",
    "explanation": "Explanation",
    "response": "Response",
    "responded_by": "Responded By", "responded by": "Responded By",
    "responsible_agency": "Responsible Agency",
    "responsible agency": "Responsible Agency",
}
TARGET_COLS = [
    "Publication", "Borough", "Community Board", "Priority", "Tracking  Code",
    "Request", "Explanation", "Response", "Instruction (MZ added)",
    "Responded By", "Responsible Agency", "Type",
]


def instruction(resp):
    """Reverse-engineered 'Instruction (MZ added)' rule. Handles Executive
    long-form ('...; resubmit request') and Preliminary short-form
    ('Agency supports but cannot accommodate') dispositions alike."""
    t = ("" if resp is None else str(resp)).strip().lower()
    if t in ("", "nan"):
        return "Remove"
    # Long-form explicit dispositions (Executive / OMB-updated responses)
    if "resubmit request" in t:
        return "Resubmit"
    if "remove request" in t:
        return "Remove"
    # Short-form agency dispositions (Preliminary responses)
    if "supports but cannot accommodate" in t:
        return "Resubmit"
    if "does not support and cannot accommodate" in t:
        return "Remove"
    if "does not support but can" in t:            # can address need alternatively
        return "Remove"
    if "supports and can accommodate" in t:        # agency will do it -> remove
        return "Remove"
    # Other clear-disposition phrasings (need is already met / not a request)
    if "already been completed" in t or "already completed" in t:
        return "Remove"
    if "already been funded" in t or "already funded" in t:
        return "Remove"
    if "not a budget request" in t:
        return "Remove"
    # Supported-but-deferred phrasings -> resubmit next cycle
    if "recommends funding this budget request" in t:
        return "Resubmit"
    if "further study by the agency" in t:
        return "Resubmit"
    # Everything else (contact-the-agency, further-investigation, fiscal
    # constraints, will-try-within-existing-resources, ...) is a judgment call.
    return "Unclear/Other"


def cap_or_exp(code):
    """C/E from tracking-code suffix. 'CS' (sited capital) -> C; only 'E' -> E."""
    c = "" if code is None else str(code).strip()
    return "E" if c.endswith("E") else "C"


df = pd.read_csv(SRC, dtype=str)
df = df.rename(columns=lambda c: CANON.get(c.strip().lower(), c))

# Filter to Queens CB2 (Borough 4, CB coded '2' in old rows / '02' in new ones).
df = df[(df["Borough"] == "4") & (df["Community Board"].isin(["2", "02"]))].copy()

# Fiscal year is embedded in the tracking code (e.g. 4|02|2027|01|E).
df["_fy"] = df["Tracking  Code"].str[3:7]
fy = sorted(df["_fy"].dropna().unique())[-1]            # most recent fiscal year
df = df[df["_fy"] == fy].copy()

# Classify the FY's publications by stage. Preliminary = agency responses;
# Executive/Adopted = OMB-updated. We keep Preliminary + Executive (the two
# stages in the source file) and drop Adopted if present.
omb_by_pub = df.groupby("Publication")["Responded By"].apply(lambda s: (s == "OMB").any())
omb_pubs = sorted(omb_by_pub[omb_by_pub].index)         # OMB pubs, earliest first
exec_pub = omb_pubs[0] if omb_pubs else None            # earliest OMB = Executive
prelim_pubs = list(omb_by_pub[~omb_by_pub].index)       # agency pubs = Preliminary
keep = set(prelim_pubs) | ({exec_pub} if exec_pub else set())
df = df[df["Publication"].isin(keep)].copy()
df["_stage"] = df["Publication"].map(lambda p: "Executive" if p == exec_pub else "Preliminary")

# Normalize numeric formats to match the target file (no leading zeros).
df["Community Board"] = df["Community Board"].str.lstrip("0")
df["Priority"] = df["Priority"].str.lstrip("0")

# Derived columns.
df["Type"] = df["Tracking  Code"].map(cap_or_exp)
df["Instruction (MZ added)"] = df["Response"].map(instruction)

# Sort to mirror the target: priority asc, Expense before Capital, then each
# request's Executive row before its Preliminary row.
df["_p"] = pd.to_numeric(df["Priority"], errors="coerce")
df["_t"] = df["Type"].map({"E": 0, "C": 1}).fillna(2)
df["_s"] = df["_stage"].map({"Executive": 0, "Preliminary": 1})
df = df.sort_values(["_p", "_t", "Tracking  Code", "_s"])

out = df[TARGET_COLS]
out.to_csv(OUT, index=False)

# ---- summary to stderr ----
print(f"SOURCE              : {SRC}", file=sys.stderr)
print(f"Fiscal Year         : {fy}", file=sys.stderr)
print(f"Stages kept         : Executive={exec_pub}  Preliminary={prelim_pubs}", file=sys.stderr)
print(f"Rows written        : {len(out)}  ({df['Tracking  Code'].nunique()} requests x stages)", file=sys.stderr)
print(f"Output              : {OUT}", file=sys.stderr)
print("Instruction (MZ added) distribution (overall):", file=sys.stderr)
for k, v in out["Instruction (MZ added)"].value_counts().items():
    print(f"   {k:14s} {v}", file=sys.stderr)
print("By stage:", file=sys.stderr)
print(df.groupby("_stage")["Instruction (MZ added)"].value_counts().to_string(), file=sys.stderr)
