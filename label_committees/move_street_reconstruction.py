#!/usr/bin/env python3
"""Move street reconstruction from City Services to Transportation.

In September 2026 the rule changed so that street reconstruction belongs to
Transportation. rubric.md now says so. Resurfacing, pothole repair and street lighting
stay in City Services. This script applies the change to the existing labels without
relabeling everything.

    move_street_reconstruction.py prepare DATA_DIR WORK_DIR [N_CHUNKS]
    move_street_reconstruction.py apply WORK_DIR

prepare: finds every request labeled City Services that could be a street
reconstruction (addressed to DOT or DDC, or its text mentions reconstructing or
rebuilding), groups them by board and explanation as prepare_years.py does, and writes
WORK_DIR/chunks/chunk_NN.jsonl and keymap.json. Each labeler reads rubric.md, answers
for each record whether it is street reconstruction under the rubric's "Street
reconstruction versus road upkeep" rule, and writes WORK_DIR/out/answers_NN.json as
[{"id": ..., "street_reconstruction": true or false}, ...].

apply: checks that every record has exactly one true/false answer, then gives each
"true" request's labels a primary committee of Transportation in
pipeline/committee_labels.csv. A secondary of Transportation is dropped, and any other
secondary is kept. Nothing is written if an answer is missing, duplicated or unknown.
"""
import glob
import json
import math
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
sys.path.insert(0, HERE)
from prepare_years import text_key  # noqa: E402
from shared import LABELS_CSV, YEARS  # noqa: E402

STREET_AGENCIES = {"Department of Transportation", "Department of Design and Construction"}
MENTIONS = re.compile(r"reconstruct|rebuild|re-build", re.I)
NOTE = "moved to Transportation as street reconstruction, 2026-09-25"


def prepare(data, work, n_chunks):
    lab = pd.read_csv(LABELS_CSV, dtype=str).fillna("")
    city = set(lab.loc[lab["primary"] == "City Services", "id"])
    records, keymap = {}, {}
    for fy in YEARS:
        path = os.path.join(data, f"CB FY{fy} Requests (all boards, detailed, 2-stage).csv")
        if not os.path.exists(path):
            continue
        d = pd.read_csv(path, dtype=str).fillna("")
        for _, r in d.iterrows():
            if r["Label ID"] not in city:
                continue
            if r["Agency"] not in STREET_AGENCIES and not MENTIONS.search(f"{r.Title} {r.Explanation}"):
                continue
            k = text_key(r.Board, r.Title, r.Explanation)
            keymap.setdefault(k, set()).add(r["Label ID"])
            records.setdefault(k, {"id": k, "board": r.Board, "agency": r.Agency, "type": r.Type,
                                   "title": r.Title, "explanation": r.Explanation})
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
    json.dump({k: sorted(v) for k, v in keymap.items()}, open(f"{work}/keymap.json", "w"))
    print(f"{len(recs)} distinct request texts (covering {sum(len(v) for v in keymap.values())} "
          f"label ids) in chunks of <= {size}")


def apply(work):
    keymap = json.load(open(f"{work}/keymap.json"))
    answers, problems = {}, []
    for f in sorted(glob.glob(f"{work}/out/answers_*.json")):
        for x in json.load(open(f)):
            k = x.get("id")
            if k in answers:
                problems.append(f"duplicate id {k} ({os.path.basename(f)})")
            if k not in keymap:
                problems.append(f"unknown id {k} ({os.path.basename(f)})")
            if not isinstance(x.get("street_reconstruction"), bool):
                problems.append(f"{k}: street_reconstruction is not true or false")
            answers[k] = x.get("street_reconstruction")
    missing = set(keymap) - set(answers)
    if missing:
        problems.append(f"{len(missing)} records have no answer, e.g. {sorted(missing)[:3]}")
    if problems:
        print("NOT WRITTEN -- fix these first:\n  " + "\n  ".join(problems[:40]), file=sys.stderr)
        sys.exit(1)
    move = {i for k, yes in answers.items() if yes for i in keymap[k]}
    lab = pd.read_csv(LABELS_CSV, dtype=str).fillna("")
    hit = lab["id"].isin(move) & (lab["primary"] == "City Services")
    lab.loc[hit, "secondary"] = lab.loc[hit, "secondary"].where(lab.loc[hit, "secondary"] != "Transportation", "")
    lab.loc[hit, "primary"] = "Transportation"
    lab.loc[hit, "labeler"] = lab.loc[hit, "labeler"] + "; " + NOTE
    lab.to_csv(LABELS_CSV, index=False)
    print(f"{sum(answers.values())} of {len(answers)} request texts are street reconstruction; "
          f"{int(hit.sum())} labels moved from City Services to Transportation")


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8)
    elif sys.argv[1] == "apply":
        apply(sys.argv[2])
    else:
        sys.exit(__doc__)
