#!/usr/bin/env python3
"""Parse a 'Statement of Community District Needs' PDF (as pdftotext -layout text)
into structured rows, for the years whose Statements carry per-request agency
responses (FY2026, FY2027). Each request is a header line ("N of M  Title  Agency",
or "CS  Title  Agency"), a few lines holding any wrapped title text and DCP's
request category, then a two-column block with the board's explanation on the left
and the agency's response (prefixed 'Agency Response:') on the right.

    parse_statement_pdf.py TXT OUT_CSV

Writes nothing, and exits 1, if no request is found. build_statement_sheet.py
separates wrapped title text from the category in `request_type`."""
import re
import sys
import csv

from shared import join_wrapped

TXT, OUT = sys.argv[1], sys.argv[2]

lines = open(TXT, encoding="utf-8").read().split("\n")
# pdftotext starts each page's first line with a form feed. Note where pages start,
# then drop the character, which would shift that line's columns by one.
newpage = ["\f" in l for l in lines]
lines = [l.replace("\f", "") for l in lines]
# A header can break after "of", leaving its total alone on the next line
# ("100 of   Trainings   DCAS" / "100"). Rejoin them; otherwise the request is lost
# and the bare "100" is dropped as a page number.
_SPLIT_HDR = re.compile(r"^(\s*\d+ of)(\s+\D.*)$")
_drop = set()
for _i in range(len(lines) - 1):
    _m, _n = _SPLIT_HDR.match(lines[_i]), re.match(r"^\s*(\d+)\s*$", lines[_i + 1])
    if _m and _n:
        lines[_i] = f"{_m.group(1)} {_n.group(1)}{_m.group(2)}"
        _drop.add(_i + 1)          # removed, not blanked: a blank would end the header block
newpage = [f for k, f in enumerate(newpage) if k not in _drop]
lines = [l for k, l in enumerate(lines) if k not in _drop]

# The right column ("Agency Response:") starts at a fixed character column.
def label_cols(l):
    return [m.start() for m in re.finditer("Agency Response:", l)]


cols = [c for l in lines for c in label_cols(l)]
if not cols:
    sys.exit(f"no 'Agency Response:' blocks in {TXT}")
SPLIT = max(set(cols), key=cols.count)

HDR = re.compile(r"^\s*(?:(\d+) of (\d+)|(CS))\s+(.*?)\s{2,}(\S.*?)\s*$")
# FY2026 Statements also have per-policy-area summary tables whose continued-support
# rows read "CS  <agency>  <title>". They match HDR but are not requests: the detailed
# entry appears later as "CS  <title>  <agency>". Reading them as entries swapped
# agency and title and duplicated requests. A CS match whose title slot is a bare
# agency code while its agency slot is prose is one of these summary rows.
AGENCY_CODE = re.compile(r"^[A-Z][A-Z0-9&+/.-]{1,7}$")
DIGITS = re.compile(r"^\s*\d+\s*$")


def is_pagenum(k):
    """A digits-only line is a page number when the next text is on a new page. Other
    digits-only lines are wrapped text (the "262" that ends a NYCHA tracker URL)."""
    if not DIGITS.match(lines[k]):
        return False
    nxt = next((x for x in range(k + 1, len(lines)) if lines[x].strip()), None)
    return nxt is None or newpage[nxt]


SKIP = re.compile(r"^\s*(CAPITAL BUDGET REQUESTS|EXPENSE BUDGET REQUESTS|Agency\s+Priority\s+Title)\s*$", re.I)
DIV = re.compile(r"^\s*(CAPITAL|EXPENSE) BUDGET REQUESTS\s*$", re.I)   # Capital/Expense section

def split_at_gap(b, col):
    """Split a body line into its left and right columns. The right column can start a
    character or two early after a page break, so a word that straddles `col` and is
    preceded by a column gap belongs to the right column; splitting at `col` would clip
    its first letters ("Parenting" -> "P" + "arenting")."""
    # The left column starts at the margin, so text that begins deep inside the left
    # area, after a long run of spaces, is right-column text shifted left.
    lead = len(b[:col]) - len(b[:col].lstrip())
    if b[:col].strip() and lead > col // 2:
        return b[:lead], b[lead:]
    if len(b) <= col or b[col - 1] == " ":
        return b[:col], b[col:]
    i = col - 1
    while i > 0 and b[i - 1] != " ":
        i -= 1
    if col - i <= 3 and (not b[:i].strip() or b[i - 2:i] == "  "):
        return b[:i], b[i:]
    return b[:col], b[col:]


def unshift(body, breaks, col):
    """pdftotext lays out each page from its leftmost text, so a page that holds only
    the continuation of a long agency response prints it at column 0, where it would
    read as explanation. Such a page is one narrow column. When the last line before
    the page break had text only in the response column, move the page back under it."""
    body = list(body)
    for a, b in zip(breaks, breaks[1:] + [len(body)]):
        seg = [x for x in body[a:b] if x.strip()]
        if not seg or any(len(x.rstrip()) > col - 10 for x in seg):
            continue
        prev = next((x for x in reversed(body[:a]) if x.strip()), "")
        if not prev.strip() or prev[:col].strip():
            continue
        for k in range(a, b):
            if body[k].strip():
                body[k] = " " * col + body[k].strip()
    return body


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
    if m.group(3) and AGENCY_CODE.match(m.group(4).strip()) and not AGENCY_CODE.match(m.group(5).strip()):
        i += 1                              # summary-table row, not a request
        continue
    entry_section = section
    if m.group(3):                      # "CS" = sited capital request (no "N of M")
        pri, denom = "CS", ""
    else:
        pri, denom = m.group(1), m.group(2)
    title, agency = m.group(4), m.group(5)
    # continuation lines of the title/type (indented, before the blank line). The body
    # can follow with no blank line when a page break falls there; its first line
    # carries the "Agency Response:" label.
    sub = []
    j = i + 1
    while j < len(lines) and lines[j].strip() and not HDR.match(lines[j]) and "Agency Response:" not in lines[j]:
        sub.append(lines[j].strip())
        j += 1
    req_type = " ".join(sub)
    while j < len(lines) and not lines[j].strip():   # skip blanks
        j += 1
    # collect the body block (until the next header), drop page-number lines
    body, breaks = [], []
    while j < len(lines) and not HDR.match(lines[j]):
        if newpage[j]:
            breaks.append(len(body))
        dm2 = DIV.match(lines[j])
        if dm2:
            section = "Capital" if dm2.group(1).upper() == "CAPITAL" else "Expense"
        elif not is_pagenum(j) and not SKIP.match(lines[j]):
            body.append(lines[j])
        j += 1
    # A real CS request always carries an "Agency Response:". A summary-table row
    # whose single-word title slipped past AGENCY_CODE ("CS  DEP  SE2Q") has none.
    if m.group(3) and not any("Agency Response:" in b for b in body):
        i += 1
        continue
    # pdftotext interleaves the two columns when an explanation overflows into the
    # response column, which also splits the label ("Agency" / "Response:").
    # build_statement_sheet.py takes such an entry's text from the Register.
    garbled = not any(label_cols(b) for b in body) and any("Response:" in b for b in body)
    # The right column starts where "Agency Response:" begins in THIS entry. A board
    # can quote the phrase in its own explanation, so take the label nearest the
    # document's usual column.
    arcol = min((c for b in body for c in label_cols(b)), key=lambda c: abs(c - SPLIT), default=SPLIT)
    body = unshift(body, breaks, arcol)
    left, right = [], []
    for b in body:
        lt, rt = split_at_gap(b, arcol)
        lt, rt = lt.rstrip(), rt.strip()
        if lt:
            left.append(lt)
        if rt:
            right.append(rt)
    response = re.sub(r"^Agency Response:\s*", "", join_wrapped(right)).strip()
    rows.append({
        "priority": pri,
        "list_of": denom,                         # 42 = expense list, else capital
        "track": entry_section if entry_section in ("Capital", "Expense") else "Capital",
        "agency": agency,
        "title": title.strip(),
        "request_type": req_type,
        "explanation": join_wrapped(left),
        "response": response,
        "garbled": int(garbled),
    })
    i = j

if not rows:
    sys.exit(f"no requests found in {TXT}")
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

from collections import Counter
print(f"Parsed entries: {len(rows)}; list_of distribution: {dict(Counter(r['list_of'] for r in rows))}; "
      f"rows with empty response: {sum(1 for r in rows if not r['response'])}")
