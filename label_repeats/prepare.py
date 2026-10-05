#!/usr/bin/env python3
"""Pair requests that may be the same request reworded, for a model to judge.

    prepare.py DATA_DIR WORK_DIR [--floor 0.30 --per 1 --chunk 180]
    prepare.py DATA_DIR WORK_DIR --pilot N --board QCB2 --since 2026 --floor 0.15 --per 2

pipeline/enrich_years.py links a board's requests across years when the first 150
characters of one explanation appear in the other. A reworded request escapes that rule.
This script pairs each request that has no link to the year before with the same board's
most similar requests from that year, so a model can judge whether the two ask for the
same thing (rubric.md).

Similarity is the cosine of TF-IDF vectors over the title and explanation, so rare words
such as a park, school or street name count most. A request keeps its best candidate (--per)
at or above --floor. In the pilot (198 pairs, README.md), every true match was a request's
best candidate, and pairs below 0.30 were matches about 2% of the time.

Pairs already judged in pipeline/repeat_links.csv are left out, so a new fiscal year needs
only its own pairs judged. Writes WORK_DIR/chunks/pairs_NN.jsonl, --chunk pairs each. With --pilot, writes
WORK_DIR/chunks/pilot_NN.jsonl instead: every pair from --board whose later request is
from --since or after, and the rest of N drawn evenly from the similarity bands across the
other boards.
"""
import collections
import glob
import json
import math
import os
import random
import re
import sys

import pandas as pd

FLOOR, PER_REQUEST, CHUNK = 0.30, 1, 180
LINKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline", "repeat_links.csv")
BANDS = [(0.15, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.01)]
STOP = set("""the and for with from that this these those are was were been has have its our their there which who
will would should could can may must also all any more most other into onto over under within without about such
than then them they per via each both only very much many some request requests requested requesting provide
provides providing fund funds funding funded need needs needed board community district cb cd year years new
additional continue continued including include includes""".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOP]


def load(data):
    rows = []
    for path in sorted(glob.glob(os.path.join(data, "CB FY20*Requests (all boards, detailed, 2-stage).csv"))):
        fy = int(re.search(r"FY(\d{4})", path).group(1))
        d = pd.read_csv(path, dtype=str).fillna("")
        for r in d.to_dict("records"):
            rows.append({"fy": fy, "board": r["Board"], "label": r["Label ID"], "agency": r["Agency"], "type": r["Type"],
                         "title": " ".join(r["Title"].split()), "explanation": " ".join(r["Explanation"].split()),
                         "years": {int(y) for y in r["History Years"].split("|") if y.strip().isdigit()}})
    return rows


def vectors(rows):
    """TF-IDF vectors, L2-normalized, over every request in every year."""
    toks = [tokens(r["title"] + " " + r["explanation"]) for r in rows]
    df = collections.Counter(w for t in toks for w in set(t))
    n = len(rows)
    out = []
    for t in toks:
        v = {w: c * math.log(n / df[w]) for w, c in collections.Counter(t).items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        out.append({w: x / norm for w, x in v.items()})
    return out


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0) for w, x in a.items())


def pairs(rows, vecs, floor=FLOOR, per=PER_REQUEST):
    by = collections.defaultdict(list)                 # (board, fy) -> row indexes
    for k, r in enumerate(rows):
        by[(r["board"], r["fy"])].append(k)
    out, done = [], set()
    for (board, fy), ks in sorted(by.items()):
        prev = by.get((board, fy - 1), [])
        for k in ks:
            if fy - 1 in rows[k]["years"] or not prev:  # already linked to the year before
                continue
            scored = sorted(((cosine(vecs[k], vecs[j]), j) for j in prev), reverse=True)[:per]
            for sim, j in scored:
                key = (rows[j]["label"], rows[k]["label"], fy)  # a request a board listed twice
                if sim >= floor and key not in done:
                    done.add(key)
                    out.append((round(sim, 3), j, k))
    return out


def record(rows, sim, j, k):
    then, now = rows[j], rows[k]
    side = lambda r: {"fy": r["fy"], "agency": r["agency"], "type": r["type"], "title": r["title"],
                      "explanation": r["explanation"]}
    return {"id": f"{then['fy']}:{then['label']}>{now['fy']}:{now['label']}", "board": now["board"], "similarity": sim,
            "then": side(then), "now": side(now)}


def write(work, name, recs, size):
    os.makedirs(os.path.join(work, "chunks"), exist_ok=True)
    for f in glob.glob(os.path.join(work, "chunks", f"{name}_*.jsonl")):
        os.remove(f)
    for n, start in enumerate(range(0, len(recs), size)):
        with open(os.path.join(work, "chunks", f"{name}_{n:02d}.jsonl"), "w") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in recs[start:start + size])
    return math.ceil(len(recs) / size)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = lambda flag, default: sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default
    data, work = args[0], args[1]
    floor, per, chunk = float(opt("--floor", FLOOR)), int(opt("--per", PER_REQUEST)), int(opt("--chunk", CHUNK))
    rows = load(data)
    found = pairs(rows, vectors(rows), floor, per)
    print(f"{len(rows)} requests; {len(found)} candidate pairs at similarity >= {floor}")
    for lo, hi in BANDS:
        print(f"  {lo:.2f}-{min(hi, 1):.2f}: {sum(lo <= s < hi for s, _, _ in found)}")
    recs = [record(rows, *p) for p in found]
    if os.path.exists(LINKS) and "--pilot" not in sys.argv:
        old = pd.read_csv(LINKS, dtype=str)
        judged = set(old["then_fy"] + ":" + old["then_label"] + ">" + old["now_fy"] + ":" + old["now_label"])
        recs = [r for r in recs if r["id"] not in judged]
        print(f"{len(recs)} pairs not judged before ({len(judged)} in {os.path.basename(LINKS)})")
    if "--pilot" in sys.argv:
        n, board, since = int(opt("--pilot", 200)), opt("--board", "QCB2"), int(opt("--since", 2021))
        mine = [r for r in recs if r["board"] == board and r["now"]["fy"] >= since]
        rest = [r for r in recs if r["board"] != board]
        rnd, take = random.Random(2026), []
        per = max(0, n - len(mine)) // len(BANDS)
        for lo, hi in BANDS:
            band = [r for r in rest if lo <= r["similarity"] < hi]
            take += rnd.sample(band, min(per, len(band)))
        pilot = mine + take
        rnd.shuffle(pilot)
        print(f"pilot: {len(mine)} pairs from {board} + {len(take)} sampled = {len(pilot)}, "
              f"in {write(work, 'pilot', pilot, 50)} chunks")
    else:
        print(f"wrote {write(work, 'pairs', recs, chunk)} chunks of up to {chunk} pairs")


if __name__ == "__main__":
    main()
