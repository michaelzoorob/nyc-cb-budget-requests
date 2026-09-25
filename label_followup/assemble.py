#!/usr/bin/env python3
"""Validate the labelers' output and merge it into pipeline/followup_labels.csv.

    assemble.py WORK_DIR [LABELER_NOTE]

Reads WORK_DIR/chunks/chunk_NN.jsonl (the inputs) and WORK_DIR/out/labels_*.json (JSON
arrays). Writes nothing if any input is missing, duplicated or unknown, or if an
action or purpose is outside rubric.md, or the pair of them is not allowed. Rows
already in followup_labels.csv are kept. The label for "no response at all" is added
here, since no labeler is needed for it.
"""
import glob
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from shared import response_key  # noqa: E402

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline", "followup_labels.csv")
ALLOWED = {
    "Contact agency": {"clarify", "study", "discuss", "reconsider", "no_response"},
    "Contact elected officials": {"funding", "advocacy"},
    "Contact agency and elected officials": {"funding", "advocacy", "discuss", "clarify", "study"},
    "Track with agency": {"status"},
    "Use 311 or another channel": {"channel"},
    "No follow-up needed": {"none"},
}
COLUMNS = ["id", "action", "purpose", "why", "contact", "url", "labeler"]


def main():
    work = sys.argv[1]
    note = sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet"
    inputs = {}
    for f in sorted(glob.glob(f"{work}/chunks/chunk_*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            inputs[r["id"]] = r
    labels, problems = {}, []
    for f in sorted(glob.glob(f"{work}/out/labels_*.json")):
        for x in json.load(open(f)):
            i = x.get("id")
            if i in labels:
                problems.append(f"duplicate id {i} ({os.path.basename(f)})")
            if i not in inputs:
                problems.append(f"unknown id {i} ({os.path.basename(f)})")
            act, pur = x.get("action"), x.get("purpose")
            if act not in ALLOWED:
                problems.append(f"{i}: bad action {act!r}")
            elif pur not in ALLOWED[act]:
                problems.append(f"{i}: purpose {pur!r} is not allowed with {act!r}")
            labels[i] = x
    missing = set(inputs) - set(labels)
    if missing:
        problems.append(f"{len(missing)} inputs have no label, e.g. {sorted(missing)[:3]}")
    if problems:
        print(f"NOT WRITTEN -- {len(problems)} problems:\n  " + "\n  ".join(problems[:60]), file=sys.stderr)
        sys.exit(1)
    # A URL never contains whitespace; the PDFs sometimes break one across lines.
    rows = [{"id": i, "action": x["action"], "purpose": x["purpose"], "why": x.get("why") or "",
             "contact": x.get("contact") or "", "url": re.sub(r"\s+", "", x.get("url") or ""), "labeler": note}
            for i, x in labels.items()]
    rows.append({"id": response_key("", ""), "action": "Contact agency", "purpose": "no_response",
                 "why": "No agency or OMB response was published.", "contact": "", "url": "",
                 "labeler": "rule: no response published"})
    new = pd.DataFrame(rows, columns=COLUMNS)
    old = pd.read_csv(DEST, dtype=str).fillna("") if os.path.exists(DEST) else pd.DataFrame(columns=COLUMNS)
    new = new[~new["id"].isin(old["id"])]
    out = pd.concat([old, new]).sort_values("id")
    out.to_csv(DEST, index=False)
    print(f"kept {len(old)} labels, added {len(new)} -> {len(out)} in {os.path.normpath(DEST)}")
    print(out["action"].value_counts().to_string())


if __name__ == "__main__":
    main()
