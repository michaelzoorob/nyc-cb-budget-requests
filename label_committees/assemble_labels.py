#!/usr/bin/env python3
"""Validate the labelers' JSON output and write pipeline/committee_labels.csv.

    assemble_labels.py WORK_DIR [LABELER_NOTE]

Reads WORK_DIR/chunks/chunk_NN.jsonl (the inputs) and WORK_DIR/out/labels_NN.json
(one JSON array per chunk). Fails loudly, without writing anything, if any input
id is missing, duplicated, unknown, or carries a committee name outside the
seven, so a truncated or sloppy labeler run can never reach the dashboard.
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
    inputs = {}
    # pilot_cb2.jsonl is included so a build WITHOUT CB2's private committee form
    # still gets model labels for CB2. When the form is present it always wins.
    for f in sorted(glob.glob(f"{work}/chunks/chunk_*.jsonl")) + glob.glob(f"{work}/pilot_cb2.jsonl"):
        for line in open(f):
            r = json.loads(line)
            inputs[r["id"]] = r
    labels, problems = {}, []
    for f in sorted(glob.glob(f"{work}/out/labels_*.json")) + glob.glob(f"{work}/out/pilot_labels.json"):
        for x in json.load(open(f)):
            i = x.get("id")
            if i in labels:
                problems.append(f"duplicate id {i} ({os.path.basename(f)})")
            if i not in inputs:
                problems.append(f"unknown id {i} ({os.path.basename(f)})")
            if x.get("primary") not in COMMITTEES:
                problems.append(f"{i}: bad primary {x.get('primary')!r}")
            sec = x.get("secondary") or None
            if sec is not None and (sec not in COMMITTEES or sec == x.get("primary")):
                problems.append(f"{i}: bad secondary {sec!r}")
            labels[i] = x
    missing = set(inputs) - set(labels)
    if missing:
        problems.append(f"{len(missing)} input ids have no label, e.g. {sorted(missing)[:3]}")
    if problems:
        print("NOT WRITTEN -- fix these first:\n  " + "\n  ".join(problems[:40]), file=sys.stderr)
        sys.exit(1)
    rows = [{"id": i, "board": inputs[i]["board"], "agency": inputs[i]["agency"],
             "title": inputs[i]["title"], "primary": x["primary"],
             "secondary": x.get("secondary") or "", "ei_reason": x.get("ei_reason", ""),
             "labeler": note} for i, x in labels.items()]
    out = pd.DataFrame(rows).sort_values(["board", "title"])
    out.to_csv(DEST, index=False)
    print(f"wrote {len(out)} labels -> {os.path.normpath(DEST)}")
    print(out["primary"].value_counts().to_string())


if __name__ == "__main__":
    main()
