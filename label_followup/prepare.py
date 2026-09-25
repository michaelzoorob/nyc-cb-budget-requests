#!/usr/bin/env python3
"""Write one labeling record per distinct pair of responses that still needs a
follow-up label.

    prepare.py DATA_DIR WORK_DIR [MAX_KB]

DATA_DIR holds the per-year "CB FY<YEAR> Requests (all boards, detailed, 2-stage).csv"
files. Requests that got the same agency response and the same OMB response share one
label, keyed by shared.response_key(). A pair already in pipeline/followup_labels.csv
is skipped, so a new fiscal year only labels its new responses. Pairs with no response
at all need no labeler; assemble.py labels them Contact agency (no_response).

Writes WORK_DIR/chunks/chunk_NN.jsonl, each at most MAX_KB (default 100) kilobytes.
Each record carries the two responses, the number of requests that share them and up
to three agencies that gave them.
"""
import collections
import glob
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from shared import YEARS, response_key  # noqa: E402

LABELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline", "followup_labels.csv")


def main():
    data, work = sys.argv[1], sys.argv[2]
    max_bytes = int(sys.argv[3] if len(sys.argv) > 3 else 100) * 1024
    done = set(pd.read_csv(LABELS, dtype=str)["id"]) if os.path.exists(LABELS) else set()
    recs, agencies = {}, collections.defaultdict(collections.Counter)
    for fy in YEARS:
        path = os.path.join(data, f"CB FY{fy} Requests (all boards, detailed, 2-stage).csv")
        if not os.path.exists(path):
            continue
        d = pd.read_csv(path, dtype=str).fillna("")
        for a, o, ag in zip(d["Agency Response"], d["OMB Executive Response"], d["Agency"]):
            if not a.strip() and not o.strip():
                continue
            k = response_key(a, o)
            if k in done:
                continue
            r = recs.setdefault(k, {"id": k, "agency_response": " ".join(a.split()),
                                    "omb_response": " ".join(o.split()), "n": 0})
            r["n"] += 1
            agencies[k][ag] += 1
    for k, r in recs.items():
        r["agencies"] = [a for a, _ in agencies[k].most_common(3)]
    os.makedirs(f"{work}/chunks", exist_ok=True)
    for f in glob.glob(f"{work}/chunks/chunk_*.jsonl"):
        os.remove(f)
    chunks, cur, size = [], [], 0
    for r in sorted(recs.values(), key=lambda r: r["id"]):
        line = json.dumps(r) + "\n"
        if cur and size + len(line) > max_bytes:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(line)
        size += len(line)
    if cur:
        chunks.append(cur)
    for i, lines in enumerate(chunks):
        with open(f"{work}/chunks/chunk_{i:02d}.jsonl", "w") as f:
            f.writelines(lines)
    print(f"{len(recs)} response pairs to label (covering {sum(r['n'] for r in recs.values())} requests) "
          f"in {len(chunks)} chunks of at most {max_bytes // 1024} KB; {len(done)} already labeled")


if __name__ == "__main__":
    main()
