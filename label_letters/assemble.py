#!/usr/bin/env python3
"""Validate the descriptions and merge them into pipeline/letter_descriptions.csv.

    assemble.py WORK_DIR [--strict] [--allow-missing]

Reads WORK_DIR/chunks/*.jsonl (the records) and WORK_DIR/out/*.json (JSON arrays of
{"id", "text"}), plus label_letters/hand.json (written by hand). Files named fix_*.json
are read last and replace earlier descriptions (a second pass on long or flawed ones). Writes nothing if a
record is missing, duplicated or unknown, or if a description has the wrong form
(responses and OMB text must start with "said"; a request must not start with "to").
A trailing period or stray whitespace is fixed. Style slips (quotation marks, colons,
semicolons, parentheses, dashes, web or email addresses, too long) are listed; with
--strict they also stop the write. Rows already in the CSV are kept unless relabeled.
"""
import glob
import json
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "pipeline", "letter_descriptions.csv")
HAND = os.path.join(HERE, "hand.json")
COLUMNS = ["id", "kind", "text", "labeler"]
MAX = {"response": 320, "omb": 320, "request": 260}
STYLE = [(re.compile(r"[\"“”:;()]"), "quote, colon, semicolon or parenthesis"),
         (re.compile(r"\s[-–—]\s|[–—]"), "dash between words"),
         (re.compile(r"https?://|www\.|\S+@\S+\.\w|\b\d{3}[-.)\s]\d{3}[-.\s]\d{4}\b"), "web, email or phone"),
         (re.compile(r"\b(unfortunately|we understand|we appreciate)\b", re.I), "editorializing")]


def clean(t):
    t = " ".join(str(t).split())
    return re.sub(r"[.\s]+$", "", t)


def main():
    work = sys.argv[1]
    strict = "--strict" in sys.argv
    partial = "--allow-missing" in sys.argv   # write what exists; the letters fall back for the rest
    inputs = {}
    for f in sorted(glob.glob(f"{work}/chunks/*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            inputs[r["id"]] = r
    out, problems, slips = {}, [], []
    # fix_*.json files come last and may replace a description written earlier.
    files = sorted(glob.glob(f"{work}/out/*.json"), key=lambda f: (os.path.basename(f).startswith("fix_"), f))
    for f in files:
        fix = os.path.basename(f).startswith("fix_")
        try:
            batch = json.load(open(f))
        except ValueError:
            if not partial:
                raise
            print(f"skipped {os.path.basename(f)} (not valid JSON yet)", file=sys.stderr)
            continue
        for x in batch:
            i = x.get("id")
            if i in out and not fix:
                (slips if partial else problems).append(f"duplicate id {i} ({os.path.basename(f)})")
            if i not in inputs:
                problems.append(f"unknown id {i} ({os.path.basename(f)})")
                continue
            out[i] = clean(x.get("text", ""))
    missing = set(inputs) - set(out)
    if missing and not partial:
        problems.append(f"{len(missing)} records have no description, e.g. {sorted(missing)[:3]}")
    elif missing:
        print(f"{len(missing)} records have no description yet (--allow-missing)", file=sys.stderr)
    for i, t in out.items():
        kind = inputs[i]["kind"]
        if not t:
            problems.append(f"{i}: empty")
        elif kind in ("response", "omb") and not t.startswith("said "):
            problems.append(f"{i} ({kind}): does not start with 'said': {t[:60]}")
        elif kind == "request" and re.match(r"(?i)to\s", t):
            problems.append(f"{i} (request): starts with 'to': {t[:60]}")
        for rx, what in STYLE:
            if rx.search(t):
                slips.append(f"{i} ({kind}) {what}: {t[:90]}")
        if len(t) > MAX[kind]:
            slips.append(f"{i} ({kind}) {len(t)} chars: {t[:60]}...")
    if slips:
        print(f"{len(slips)} style slips:\n  " + "\n  ".join(slips[:80]), file=sys.stderr)
    if problems or (strict and slips):
        print(f"NOT WRITTEN -- {len(problems)} problems:\n  " + "\n  ".join(problems[:60]), file=sys.stderr)
        sys.exit(1)
    rows = [{"id": i, "kind": inputs[i]["kind"], "text": t, "labeler": "claude-sonnet"} for i, t in out.items()]
    if os.path.exists(HAND):
        rows += [{"id": h["id"], "kind": h["kind"], "text": clean(h["text"]), "labeler": "hand-written"}
                 for h in json.load(open(HAND))]
    new = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates(["kind", "id"], keep="last")
    old = pd.read_csv(DEST, dtype=str).fillna("") if os.path.exists(DEST) else pd.DataFrame(columns=COLUMNS)
    keep = old[~(old["kind"] + "|" + old["id"]).isin(new["kind"] + "|" + new["id"])]
    res = pd.concat([keep, new]).sort_values(["kind", "id"])
    res.to_csv(DEST, index=False)
    print(f"kept {len(keep)}, wrote {len(new)} -> {len(res)} descriptions in {os.path.normpath(DEST)}")
    print(res.groupby(["kind", "labeler"]).size().to_string())


if __name__ == "__main__":
    main()
