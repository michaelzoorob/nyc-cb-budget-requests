#!/usr/bin/env python3
"""Merge the output of a prepare_years.py labeling run into pipeline/committee_labels.csv.

    assemble_years.py WORK_DIR [LABELER_NOTE]

Reads WORK_DIR/chunks/*.jsonl, WORK_DIR/out/labels_*.json, keymap.json and reuse.csv.
Each label is written once for every request id its text stands for. Rows already in
committee_labels.csv are kept as they are. Nothing is written if any record is missing,
duplicated, unknown or labeled with a committee outside the seven.
"""
import glob
import json
import os
import sys

import pandas as pd

COMMITTEES = {"Land Use", "Transportation", "Parks and Environment", "Health and Human Services",
              "Arts and Culture", "Engagement and Inclusion", "City Services"}
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline", "committee_labels.csv")


def main():
    work = sys.argv[1]
    note = sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet"
    records = {}
    for f in sorted(glob.glob(f"{work}/chunks/chunk_*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            records[r["id"]] = r
    keymap = json.load(open(f"{work}/keymap.json"))
    labels, problems = {}, []
    for f in sorted(glob.glob(f"{work}/out/labels_*.json")):
        for x in json.load(open(f)):
            k = x.get("id")
            if k in labels:
                problems.append(f"duplicate id {k} ({os.path.basename(f)})")
            if k not in records:
                problems.append(f"unknown id {k} ({os.path.basename(f)})")
            if x.get("primary") not in COMMITTEES:
                problems.append(f"{k}: bad primary {x.get('primary')!r}")
            sec = x.get("secondary") or None
            if sec is not None and (sec not in COMMITTEES or sec == x.get("primary")):
                problems.append(f"{k}: bad secondary {sec!r}")
            labels[k] = x
    missing = set(records) - set(labels)
    if missing:
        problems.append(f"{len(missing)} records have no label, e.g. {sorted(missing)[:3]}")
    if problems:
        print("NOT WRITTEN -- fix these first:\n  " + "\n  ".join(problems[:40]), file=sys.stderr)
        sys.exit(1)

    rows = []
    for k, x in labels.items():
        for rid, m in keymap[k].items():
            rows.append({"id": rid, "board": m["board"], "agency": m["agency"], "title": m["title"],
                         "primary": x["primary"], "secondary": x.get("secondary") or "",
                         "ei_reason": x.get("ei_reason", ""), "labeler": note})
    new = pd.concat([pd.DataFrame(rows), pd.read_csv(f"{work}/reuse.csv", dtype=str).fillna("")])
    old = pd.read_csv(DEST, dtype=str).fillna("") if os.path.exists(DEST) else pd.DataFrame(columns=new.columns)
    new = new[~new["id"].isin(old["id"])].drop_duplicates("id")
    out = pd.concat([old, new]).sort_values(["board", "title"])
    out.to_csv(DEST, index=False)
    print(f"kept {len(old)} existing labels, added {len(new)} ({len(rows)} from {len(labels)} labeled "
          f"texts, the rest reused) -> {len(out)} in {os.path.normpath(DEST)}")


if __name__ == "__main__":
    main()
