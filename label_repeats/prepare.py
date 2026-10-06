#!/usr/bin/env python3
"""Pair requests that may be the same request reworded, for a model to judge.

    prepare.py DATA_DIR WORK_DIR [--floor 0.30 --per 1 --chunk 180] [--rejudge-located]
    prepare.py DATA_DIR WORK_DIR --sites [--chunk 180]
    prepare.py DATA_DIR WORK_DIR --gaps [--chunk 180]
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

A request from FY2020 to FY2025 carries the Register's site fields (its Location column),
which count toward the similarity and are shown to the judge. Pairs already judged in
pipeline/repeat_links.csv are left out, so a new fiscal year needs only its own pairs
judged. --rejudge-located also writes every judged pair in which either request has such
a site, to judge it again now that the site is shown (except pairs settled by hand in
resolved.json). A request with the same text the year before is left to --sites. When a
board sent one text for two sites in a year, a pair names that request by its site key
(shared.site_key), or by its Label ID and "@-" when it has no site, so the verdict says
which one it means.

--sites writes the pairs that enrich_years.py will not link on its own: the same text in
two years, where both requests name a site (shared.parse_site) and the sites are not
plainly one place (shared.site_match). A board may send one text for several sites, and
the Register may name one site in several ways, so a model judges these too. Their ids use
shared.site_key in place of the Label ID, and they carry "kind": "site".

--gaps writes requests a board skipped a year or two: a request with no link to the year
before, paired with its most similar request two or three years earlier (at or above
--floor), when neither request appears in the years between. They are judged as reworded
pairs.

Writes WORK_DIR/chunks/pairs_NN.jsonl, --chunk pairs each. With --pilot, writes
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from enrich_years import norm, same_text, text_pairs  # noqa: E402
from shared import parse_site, site_key, site_match  # noqa: E402

FLOOR, PER_REQUEST, CHUNK = 0.30, 1, 180
LINKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline", "repeat_links.csv")
RESOLVED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resolved.json")
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
            loc = " ".join(str(r.get("Location", "")).split())
            rows.append({"fy": fy, "board": r["Board"], "label": r["Label ID"], "agency": r["Agency"], "type": r["Type"],
                         "title": " ".join(r["Title"].split()), "explanation": " ".join(r["Explanation"].split()),
                         "location": loc, "key": site_key(r["Label ID"], loc), "n": norm(r["Explanation"]),
                         "site": parse_site(loc, r["Explanation"]),
                         "years": {int(y) for y in r["History Years"].split("|") if y.strip().isdigit()}})
    keys = collections.defaultdict(set)
    for r in rows:
        keys[(r["fy"], r["label"])].add(r["key"])
    for r in rows:                                     # the id a verdict uses for this request
        several = len(keys[(r["fy"], r["label"])]) > 1
        r["pid"] = (r["key"] if r["location"] else r["label"] + "@-") if several else r["label"]
    return rows


def vectors(rows):
    """TF-IDF vectors, L2-normalized, over every request in every year."""
    toks = [tokens(r["title"] + " " + r["explanation"] + " " + r["location"]) for r in rows]
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
            scored = sorted(((cosine(vecs[k], vecs[j]), j) for j in prev
                             if not same_text(rows[j]["n"], rows[k]["n"])),        # same text: left to --sites
                            reverse=True)[:per]
            for sim, j in scored:
                key = (rows[j]["pid"], rows[k]["pid"], fy)  # a request a board listed twice
                if sim >= floor and key not in done:
                    done.add(key)
                    out.append((round(sim, 3), j, k))
    return out


def gap_pairs(rows, vecs, floor=FLOOR):
    """A request the board skipped one or two years: (similarity, earlier, later) pairs."""
    by = collections.defaultdict(list)
    for k, r in enumerate(rows):
        by[(r["board"], r["fy"])].append(k)
    first = min(fy for _, fy in by)
    out, done = [], set()
    for (board, fy), ks in sorted(by.items()):
        for k in ks:
            if fy - 1 in rows[k]["years"]:
                continue
            for back in (2, 3):
                y, between = fy - back, set(range(fy - back + 1, fy))
                if y < first or y in rows[k]["years"] or between & rows[k]["years"]:
                    continue
                prev = [j for j in by.get((board, y), []) if not (between | {fy}) & rows[j]["years"]
                        and not same_text(rows[j]["n"], rows[k]["n"])]
                sim, j = max(((cosine(vecs[k], vecs[j]), j) for j in prev), default=(0, None))
                key = j is not None and (rows[j]["pid"], rows[k]["pid"], fy)
                if j is not None and sim >= floor and key not in done:
                    done.add(key)
                    out.append((round(sim, 3), j, k))
    return out


def site_pairs(rows):
    """The same text in two years at sites that are not plainly one place, earlier year first."""
    items = [(r["board"], r["fy"], k, r["n"]) for k, r in enumerate(rows)]
    return [(1.0, j, k) for j, k in text_pairs(items)
            if rows[j]["site"] and rows[k]["site"] and site_match(rows[j]["site"], rows[k]["site"]) == "judge"]


def record(rows, sim, j, k, sites=False):
    then, now = rows[j], rows[k]
    key = "key" if sites else "pid"
    side = lambda r: {"fy": r["fy"], "agency": r["agency"], "type": r["type"], "title": r["title"],
                      "explanation": r["explanation"], **({"location": r["location"]} if r["location"] else {})}
    return {"id": f"{then['fy']}:{then[key]}>{now['fy']}:{now[key]}", "board": now["board"], "similarity": sim,
            **({"kind": "site"} if sites else {}), "then": side(then), "now": side(now)}


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
    if "--sites" in sys.argv:
        recs = list({r["id"]: r for r in (record(rows, *p, sites=True) for p in site_pairs(rows))}.values())
        if os.path.exists(LINKS):
            old = pd.read_csv(LINKS, dtype=str)
            judged = set(old["then_fy"] + ":" + old["then_label"] + ">" + old["now_fy"] + ":" + old["now_label"])
            recs = [r for r in recs if r["id"] not in judged]
        print(f"{len(recs)} pairs of the same text at sites that are not plainly one place, not judged before; "
              f"wrote {write(work, 'pairs', recs, chunk)} chunks of up to {chunk} pairs")
        return
    if "--gaps" in sys.argv:
        recs = list({r["id"]: r for r in (record(rows, *p) for p in gap_pairs(rows, vectors(rows), floor))}.values())
        if os.path.exists(LINKS):
            old = pd.read_csv(LINKS, dtype=str)
            judged = set(old["then_fy"] + ":" + old["then_label"] + ">" + old["now_fy"] + ":" + old["now_label"])
            recs = [r for r in recs if r["id"] not in judged]
        print(f"{len(recs)} pairs across a skipped year or two, not judged before; "
              f"wrote {write(work, 'pairs', recs, chunk)} chunks of up to {chunk} pairs")
        return
    found = pairs(rows, vectors(rows), floor, per)
    print(f"{len(rows)} requests; {len(found)} candidate pairs at similarity >= {floor}")
    for lo, hi in BANDS:
        print(f"  {lo:.2f}-{min(hi, 1):.2f}: {sum(lo <= s < hi for s, _, _ in found)}")
    recs = [record(rows, *p) for p in found]
    if os.path.exists(LINKS) and "--pilot" not in sys.argv:
        old = pd.read_csv(LINKS, dtype=str)
        judged = set(old["then_fy"] + ":" + old["then_label"] + ">" + old["now_fy"] + ":" + old["now_label"])
        recs = [r for r in recs if r["id"] not in judged]
        if "--rejudge-located" in sys.argv:
            settled = {x["id"] for x in json.load(open(RESOLVED))} if os.path.exists(RESOLVED) else set()
            at = {}
            for k, r in enumerate(rows):
                at.setdefault((r["fy"], r["label"]), k)
            again = []
            for t_fy, t_l, n_fy, n_l, sim in zip(old.then_fy, old.then_label, old.now_fy, old.now_label, old.similarity):
                j, k = at.get((int(t_fy), t_l)), at.get((int(n_fy), n_l))
                if j is not None and k is not None and (rows[j]["location"] or rows[k]["location"]):
                    r = record(rows, float(sim), j, k)
                    if r["id"] not in settled:
                        again.append(r)
        print(f"{len(recs)} pairs not judged before ({len(judged)} in {os.path.basename(LINKS)})")
        if "--rejudge-located" in sys.argv:
            print(f"{len(again)} judged pairs to judge again with the Register's site shown")
            recs += again
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
