#!/usr/bin/env python3
"""Check the verdicts and write pipeline/repeat_links.csv.

    assemble.py WORK_DIR

Reads the pairs in WORK_DIR/chunks/pairs_*.jsonl (prepare.py) and the verdicts in
WORK_DIR/out/pairs_*.json (rubric.md). Writes nothing if a pair has no verdict, a verdict
names an unknown pair, or a verdict is not "same", "different" or "unsure". A pair listed
more than once (a board that lists the identical request twice in a year) needs one verdict
per listing; if they disagree, it counts as "unsure".

A request links to at most one request the year before. When two of its candidates were
judged the same, only the more similar one counts. (In the pilot, the less similar one was
wrong both times: a board's separate street and sewer requests for the same blocks.)

A pair in which neither request has an explanation counts as "unsure": a DCP category title
alone in both years does not show what was asked. (When one year has an explanation, the
other year's title usually carries the ask, often in the board's own words.) label_repeats/resolved.json holds verdicts settled by
hand where a blind check disagreed with the first judge ({"id", "verdict", "why"}). They
replace the first verdict.

Adds to pipeline/repeat_links.csv, one row per judged pair: board, then_fy, then_label,
now_fy, now_label, similarity, verdict, why, judge ("sonnet", "rule" or "resolved"). Rows already
there are kept, and a pair judged again replaces its row. A pair dropped by the one-match rule keeps its
verdict with "superseded" added to why. pipeline/enrich_years.py links the pairs whose
verdict is "same".
"""
import glob
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "pipeline", "repeat_links.csv")
RESOLVED = os.path.join(HERE, "resolved.json")
VERDICTS = {"same", "different", "unsure"}


def main():
    work = sys.argv[1]
    pairs, listed = {}, {}
    for f in sorted(glob.glob(os.path.join(work, "chunks", "pairs_*.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            pairs[r["id"]] = r
            listed[r["id"]] = listed.get(r["id"], 0) + 1
    got, seen, problems = {}, {}, []
    for f in sorted(glob.glob(os.path.join(work, "out", "pairs_*.json"))):
        for x in json.load(open(f)):
            i = x.get("id")
            if i not in pairs:
                problems.append(f"unknown pair {i} ({os.path.basename(f)})")
            elif x.get("verdict") not in VERDICTS:
                problems.append(f"{i}: verdict {x.get('verdict')!r}")
            else:
                seen[i] = seen.get(i, 0) + 1
                if seen[i] > listed[i]:
                    problems.append(f"{i}: more verdicts than listings")
                elif i in got and got[i]["verdict"] != x["verdict"]:
                    got[i] = {**got[i], "verdict": "unsure", "why": "repeated listing judged both ways"}
                else:
                    got.setdefault(i, x)
    for i, r in pairs.items():
        if i in got and got[i]["verdict"] == "same" and not (r["then"]["explanation"].strip() or r["now"]["explanation"].strip()):
            got[i] = {**got[i], "verdict": "unsure", "why": "no explanation in either year", "judge": "rule"}
    for x in json.load(open(RESOLVED)) if os.path.exists(RESOLVED) else []:
        if x["id"] not in pairs:
            problems.append(f"resolved.json names an unknown pair {x['id']}")
        elif x["verdict"] not in VERDICTS:
            problems.append(f"resolved.json: {x['id']} verdict {x['verdict']!r}")
        else:
            got[x["id"]] = {**x, "judge": "resolved"}
    missing = set(pairs) - set(got)
    if missing:
        problems.append(f"{len(missing)} pairs have no verdict, e.g. {sorted(missing)[:3]}")
    if problems:
        sys.exit("NOT WRITTEN\n  " + "\n  ".join(problems[:40]))
    rows = []
    for i, r in pairs.items():
        (then_fy, then_label), (now_fy, now_label) = (s.split(":") for s in i.split(">"))
        rows.append({"board": r["board"], "then_fy": int(then_fy), "then_label": then_label, "now_fy": int(now_fy),
                     "now_label": now_label, "similarity": r["similarity"], "verdict": got[i]["verdict"],
                     "why": " ".join(str(got[i].get("why", "")).split()), "judge": got[i].get("judge", "sonnet")})
    d = pd.DataFrame(rows)
    if os.path.exists(DEST):                 # earlier years' verdicts stay
        old = pd.read_csv(DEST)
        key = lambda x: x["then_fy"].astype(str) + ":" + x["then_label"] + ">" + x["now_fy"].astype(str) + ":" + x["now_label"]
        d = pd.concat([old[~key(old).isin(key(d))], d], ignore_index=True)
    d = d.sort_values(["board", "now_fy", "now_label", "similarity"], ascending=[True, True, True, False]).reset_index(drop=True)
    # One match per request per year: the most similar "same" pair.
    same = d["verdict"] == "same"
    first = ~d[same].duplicated(["now_fy", "now_label", "then_fy"])
    drop = first[~first].index
    d.loc[drop, "verdict"] = "different"
    d.loc[drop, "why"] = d.loc[drop, "why"] + " (superseded by a closer match)"
    d.to_csv(DEST, index=False)
    print(f"wrote {len(d)} judged pairs to {os.path.normpath(DEST)}: " +
          ", ".join(f"{k} {v}" for k, v in d["verdict"].value_counts().items()) +
          (f"; {len(drop)} superseded" if len(drop) else ""))


if __name__ == "__main__":
    main()
