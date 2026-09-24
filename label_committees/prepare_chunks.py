#!/usr/bin/env python3
"""Split the combined all-boards CSV into JSONL chunks for the committee labelers.

    prepare_chunks.py COMBINED_CSV OUT_DIR [N_CHUNKS]

Writes OUT_DIR/chunks/chunk_NN.jsonl (every board except QCB2, whose committees
come from its own committee form) and OUT_DIR/pilot_cb2.jsonl (QCB2's requests,
used to score a labeler blind against CB2's human assignments). Each record
carries the same id that pipeline/build_statement_sheet.py computes, so labels
join back to requests.
"""
import hashlib
import json
import math
import os
import re
import sys

import pandas as pd


def norm(s):   # must stay identical to norm() in pipeline/build_statement_sheet.py
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower()).strip()


def request_id(board, title, expl):
    return hashlib.sha1(f"{board}|{norm(title)}|{norm(expl)}".encode()).hexdigest()[:12]


def main():
    src, out = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 13
    d = pd.read_csv(src, dtype=str).fillna("")
    d["id"] = [request_id(b, t, e) for b, t, e in zip(d.Board, d.Title, d.Explanation)]
    # Requests with identical board + title + text share an id and get one label.
    d = d.drop_duplicates("id")
    rec = lambda r: {"id": r.id, "board": r.Board, "agency": r.Agency, "type": r.Type,
                     "title": r.Title, "explanation": r.Explanation}
    os.makedirs(f"{out}/chunks", exist_ok=True)
    with open(f"{out}/pilot_cb2.jsonl", "w") as f:
        for _, r in d[d.Board == "QCB2"].iterrows():
            f.write(json.dumps(rec(r)) + "\n")
    o = d[d.Board != "QCB2"].reset_index(drop=True)
    size = math.ceil(len(o) / n)
    for i in range(n):
        with open(f"{out}/chunks/chunk_{i:02d}.jsonl", "w") as f:
            for _, r in o.iloc[i * size:(i + 1) * size].iterrows():
                f.write(json.dumps(rec(r)) + "\n")
    print(f"{len(o)} requests in {n} chunks of <= {size}; "
          f"{(d.Board == 'QCB2').sum()} QCB2 requests in pilot_cb2.jsonl")


if __name__ == "__main__":
    main()
