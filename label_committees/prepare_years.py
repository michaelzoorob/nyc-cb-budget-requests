#!/usr/bin/env python3
"""Find every request, in any fiscal year, that still needs a committee label, and
write one labeling record per distinct request text.

    prepare_years.py DATA_DIR WORK_DIR [N_CHUNKS]

DATA_DIR holds the per-year "CB FY<YEAR> Requests (all boards, detailed, 2-stage).csv"
files. A request needs nothing if pipeline/committee_labels.csv already has its id.
Otherwise it reuses the committee of a request from the latest year with the same
board and the same explanation (boards resubmit heavily, and CB2's latest-year
committees come from its human committee form). What remains is grouped by board and
explanation, so a request resubmitted in several years is labeled once.

Writes WORK_DIR/chunks/chunk_NN.jsonl (one record per distinct text), keymap.json
(record id -> every request id it stands for) and reuse.csv (the reused labels).
assemble_years.py turns the labelers' output into rows of committee_labels.csv.
"""
import glob
import hashlib
import json
import math
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from shared import LATEST, YEARS, load_labels, norm, request_id  # noqa: E402

MIN_EXPL = 30   # shorter explanations ("see attached") are too generic to match on


def text_key(board, title, expl):
    """Requests sharing this key are the same request text and get one label."""
    e = norm(expl)
    k = f"E|{board}|{e}" if len(e) >= MIN_EXPL else f"R|{request_id(board, title, expl)}"
    return hashlib.sha1(k.encode()).hexdigest()[:12]


def main():
    data, work = sys.argv[1], sys.argv[2]
    n_chunks = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    csv = lambda fy: os.path.join(data, f"CB FY{fy} Requests (all boards, detailed, 2-stage).csv")
    labels = load_labels()
    latest = pd.read_csv(csv(LATEST), dtype=str).fillna("")
    by_expl = {(b, norm(e)): c for b, e, c in zip(latest.Board, latest.Explanation, latest.Committees)
               if len(norm(e)) >= MIN_EXPL}
    reuse, keymap, records = [], {}, {}
    for fy in YEARS:                       # newest first, so a record shows its latest wording
        if fy == LATEST or not os.path.exists(csv(fy)):
            continue
        d = pd.read_csv(csv(fy), dtype=str).fillna("")
        for _, r in d.iterrows():
            rid = request_id(r.Board, r.Title, r.Explanation)
            if rid in labels:
                continue
            hit = by_expl.get((r.Board, norm(r.Explanation)))
            if hit:
                p, s = (hit.split("|") + [""])[:2]
                reuse.append({"id": rid, "board": r.Board, "agency": r.Agency, "title": r.Title,
                              "primary": p, "secondary": s, "ei_reason": "",
                              "labeler": f"reused: same board and explanation as a FY{LATEST} request"})
                continue
            k = text_key(r.Board, r.Title, r.Explanation)
            keymap.setdefault(k, {})[rid] = {"board": r.Board, "agency": r.Agency, "title": r.Title}
            records.setdefault(k, {"id": k, "board": r.Board, "agency": r.Agency, "type": r.Type,
                                   "title": r.Title, "explanation": r.Explanation})
    reuse = pd.DataFrame(reuse).drop_duplicates("id")
    os.makedirs(f"{work}/chunks", exist_ok=True)
    for f in glob.glob(f"{work}/chunks/chunk_*.jsonl"):
        os.remove(f)
    recs = sorted(records.values(), key=lambda r: (r["board"], r["id"]))
    size = math.ceil(len(recs) / n_chunks) if recs else 0
    for i in range(n_chunks):
        part = recs[i * size:(i + 1) * size]
        if part:
            with open(f"{work}/chunks/chunk_{i:02d}.jsonl", "w") as f:
                for r in part:
                    f.write(json.dumps(r) + "\n")
    json.dump(keymap, open(f"{work}/keymap.json", "w"))
    reuse.to_csv(f"{work}/reuse.csv", index=False)
    n_req = sum(len(v) for v in keymap.values())
    print(f"reused {len(reuse)} request ids; {len(recs)} distinct texts to label "
          f"(covering {n_req} request ids) in chunks of <= {size}")


if __name__ == "__main__":
    main()
