#!/usr/bin/env python3
"""Parse the four-column request table that some Statements print instead of
per-request "Agency Response:" blocks (every Bronx board in FY2026).

    parse_request_table.py TXT [OUT_CSV]

The table follows the "SUMMARY OF PRIORITIZED BUDGET REQUESTS" heading, split into
CAPITAL and EXPENSE BUDGET REQUESTS sections under a "Title Agency Request
Explanation" header. Each row's first line reads
    <title>   <N / M>   <request category>   <explanation>
and its second line puts the agency code under the priority. Rows can continue
across a page break, and the columns shift by a character or two from page to
page, so every text fragment is assigned to the nearest column. The header line
fixes where the columns are, which also covers rows whose request cell is empty or
whose cells are separated by a single space.

There is no agency response column, so these rows carry the board's own title,
priority, agency and explanation only. build_all_boards.py uses them to restore
the Bronx boards' own titles and to add requests the Register never published.
"""
import csv
import re
import sys

from shared import join_wrapped

ANCHOR = "SUMMARY OF PRIORITIZED BUDGET REQUESTS"
SECTION = re.compile(r"^\s*(CAPITAL|EXPENSE) BUDGET REQUESTS\s*$", re.I)
HEADER = re.compile(r"^\s*Title\s+Agency\s+Request\s+Explanation\s*$")
SKIP = re.compile(r"^\s*(\d+|Priority)\s*$")
# One space is enough before a numeric priority ("Provide a new or 3 / 24"); "CS" needs two.
PRIORITY = re.compile(r"(?<=\S)(?:\s+(\d+\s*/\s*\d+)|\s{2,}(CS))(?=\s|$)")
FRAG = re.compile(r"\S+(?: \S+)*")          # runs of text separated by 2+ spaces


def fragments(line, lo=0):
    return [(m.start() + lo, m.group()) for m in FRAG.finditer(line[lo:])]


def split_across(frags, col):
    """Split a fragment that runs from before `col` to past it at the space nearest `col`."""
    out = []
    for s, t in frags:
        if s < col - 2 and s + len(t) > col + 2:
            cut = min((i for i, ch in enumerate(t) if ch == " "), key=lambda i: abs(s + i - col), default=None)
            if cut is not None:
                out += [(s, t[:cut]), (s + cut + 1, t[cut + 1:])]
                continue
        out.append((s, t))
    return out


def parse(path):
    # pdftotext starts each new page's first line with a form feed, which would hide
    # a row that begins a page and shift that line's columns by one.
    lines = open(path, encoding="utf-8").read().replace("\f", "").split("\n")
    starts = [i for i, l in enumerate(lines) if ANCHOR in l]
    if not starts:
        return []
    rows, cur, section, cols = [], None, None, None
    # Each section says how many rows it has ("N / M"). Once its last row has started,
    # that row ends at the next blank line; otherwise it would absorb whatever follows
    # the table (one Bronx file attaches a library's letter with staff contact details).
    expected, seen, closing = None, 0, False
    for line in lines[starts[-1] + 1:]:
        sm = SECTION.match(line)
        if sm:
            section, cur = sm.group(1).capitalize(), None
            expected, seen, closing = None, 0, False
            continue
        if closing and not line.strip():
            cur, closing = None, False
            continue
        if HEADER.match(line):
            cols = [line.index("Title"), line.index("Agency"), line.index("Request"), line.index("Explanation")]
            continue
        if not line.strip() or SKIP.match(line) or not cols:
            continue
        pm = PRIORITY.search(line)
        if section and pm and line[:1].strip() and abs(pm.start(pm.lastindex) - cols[1]) <= 6:
            cur = {"section": section, "priority": re.sub(r"\s", "", pm.group(pm.lastindex)),
                   "cells": [[line[:pm.start()].strip()], [], [], []]}
            rows.append(cur)
            of = cur["priority"].partition("/")[2]
            if expected is None and of.isdigit():
                expected = int(of)
            seen += 1
            closing = expected is not None and seen >= expected
            rest = split_across(fragments(line, pm.end()), cols[3])
            for s, t in rest:
                cur["cells"][2 if abs(s - cols[2]) < abs(s - cols[3]) else 3].append(t)
            continue
        if cur is None:
            continue
        for s, t in split_across(fragments(line), cols[3]):
            cur["cells"][min(range(4), key=lambda c: abs(s - cols[c]))].append(t)
    out = []
    for r in rows:
        title, agency, request, expl = (join_wrapped(c) for c in r["cells"])
        pr, _, of = r["priority"].partition("/")
        out.append({"section": r["section"], "priority": pr, "list_of": of,
                    "agency": agency.split()[0] if agency else "",
                    "title": title, "request": request, "explanation": expl})
    return out


# FY2025 Statements print the same summary as five columns, with the priority first
# and each row's other cells wrapping under their first line:
#     1/43       DPR       Reconstruct or        Reconstruction of Floyd ...     Location
# The columns drift a few characters from page to page, so each row takes its column
# positions from its own first line.
PRI5 = re.compile(r"^(\d+)\s*/\s*(\d+)(?=\s)|^(CS)(?=\s)")
HEADER5 = re.compile(r"^\s*Priority\s+Agency\s+Request\s+Explanation\s+Location\s*$")
SECTION5 = re.compile(r"^\s*(Capital|Expense) Budget Requests\s*$")


def parse_five_column(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    newpage = ["\f" in l for l in lines]
    lines = [l.replace("\f", "") for l in lines]
    starts = [i for i, l in enumerate(lines) if ANCHOR in l]
    if not starts:
        return []
    rows, cur, section, loc_gap = [], None, None, 53
    for k in range(starts[-1] + 1, len(lines)):
        line = lines[k]
        sm = SECTION5.match(line)
        if sm:
            section, cur = sm.group(1), None
            continue
        hm = HEADER5.match(line)
        if hm:
            loc_gap = line.index("Location") - line.index("Explanation")
            continue
        if not line.strip() or not section:
            continue
        if SKIP.match(line):
            nxt = next((x for x in range(k + 1, len(lines)) if lines[x].strip()), None)
            if nxt is None or newpage[nxt]:          # a page number
                continue
        pm = PRI5.match(line)
        if pm:
            frags = fragments(line)
            if len(frags) < 4:                       # priority, agency, request, explanation
                cur = None
                continue
            cols = [s for s, _ in frags[1:5]]
            if len(cols) == 3:
                cols.append(cols[2] + loc_gap)
            cur = {"section": section, "priority": pm.group(3) or pm.group(1), "list_of": pm.group(2) or "",
                   "cols": cols, "cells": [[frags[1][1]], [], [], []]}
            rows.append(cur)
            for s, t in split_across(frags[2:], cols[2]):
                cur["cells"][min(range(1, 4), key=lambda c: abs(s - cols[c]))].append(t)
            continue
        if cur is None:
            continue
        for s, t in split_across(fragments(line), cur["cols"][2]):
            cur["cells"][min(range(1, 4), key=lambda c: abs(s - cur["cols"][c]))].append(t)
    return [{"section": r["section"], "priority": r["priority"], "list_of": r["list_of"],
             "agency": " ".join(r["cells"][0]).split()[0], "title": join_wrapped(r["cells"][1]),
             "request": join_wrapped(r["cells"][1]), "explanation": join_wrapped(r["cells"][2]),
             "location": join_wrapped(r["cells"][3])} for r in rows]


if __name__ == "__main__":
    rows = parse(sys.argv[1]) or parse_five_column(sys.argv[1])
    if len(sys.argv) > 2 and rows:
        with open(sys.argv[2], "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(rows)} rows ({sum(r['section'] == 'Capital' for r in rows)} capital, "
          f"{sum(r['section'] == 'Expense' for r in rows)} expense)")
