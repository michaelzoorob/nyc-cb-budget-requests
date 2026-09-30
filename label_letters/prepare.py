#!/usr/bin/env python3
"""Write the records that still need a plain-language description for the letters.

    prepare.py DATA_DIR WORK_DIR [MAX_KB] [--pilot]

DATA_DIR holds the per-year "CB FY<YEAR> Requests (all boards, detailed, 2-stage).csv"
files. Three kinds of record, each keyed by shared.text_key() of the text described:

  response  every distinct agency response, from every year
  request   every distinct FY2026 and later request (title and explanation); earlier
            years' titles are DCP categories, and the letters reword those requests by rule
  omb       OMB Executive Budget text that the letters would otherwise quote (text that
            is not one of OMB's stock phrases and does not restate the agency)

A record already in pipeline/letter_descriptions.csv or label_letters/hand.json is
skipped. Writes WORK_DIR/chunks/<kind>_NN.jsonl, each at most MAX_KB (default 110)
kilobytes. With --pilot, writes one mixed WORK_DIR/chunks/pilot.jsonl instead.
"""
import collections
import glob
import json
import os
import random
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
from shared import LETTER_CSV, PDF_YEARS, YEARS, request_text, text_key  # noqa: E402

HAND = os.path.join(HERE, "hand.json")
ws = lambda s: " ".join(str(s).split())

# OMB text the letters summarize with a stock phrase, or leave out (generate_cb2_html.py,
# OMB_SAYS and ombNote). Anything else would be quoted, so it gets a description.
OMB_STOCK = re.compile("|".join([
    r"brought to the attention of your elected officials", r"availability of funds is uncertain",
    r"funding for this request cannot be determined", r"available funds are insufficient",
    r"cannot be funded in FY ?\d{4}", r"not recommended for funding", r"has not submitted a proposal to increase funding",
    r"restoring and/or increasing funding is needed", r"depends on sufficient federal/state funds",
    r"approved if the city receives sufficient federal and/or state funds", r"citywide personnel/program/equipment funds are maintained",
    r"will accommodate part of this request", r"will try to accommodate this (issue|request)",
    r"will accommodate this request within existing resources", r"partially funded",
    r"funded in a prior fiscal year and the scope is now underway", r"funded in a prior fiscal year and the construction contract has been let",
    r"funded in a prior fiscal year and the (preliminary |final )?design contract has been let", r"has already been funded",
    r"included in the ten-year plan", r"project is ongoing", r"funding and/or headcount was recently added",
    r"includes a city-wide allocation for this work", r"has already been completed", r"not eligible for capital funding",
    r"not a budget request", r"does not seem to be applicable to the responsible agency",
    r"sidewalks are the responsibility of the adjacent property owner",
    r"more information is needed from the community board", r"requires additional information from the community board",
    r"includes more than one proposal", r"further (study|investigation)", r"requires further study",
    r"contact the (relevant |responsible )?(agency|borough commissioner|transit authority)", r"for more information",
    r"reach out to the agency"]), re.I)
OMB_RESTATES = re.compile(r"^(OMB (supports the agency.s position|agrees with the agency)|Agency (supports|does not support|will|has|is|cannot))", re.I)
nrm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def omb_quoted(agency_response, omb):
    if not omb or OMB_RESTATES.match(omb) or OMB_STOCK.search(omb):
        return False
    return not (nrm(omb)[:60] and nrm(omb)[:60] in nrm(agency_response))


def collect(data, skip):
    recs, agencies = {}, collections.defaultdict(collections.Counter)

    def add(kind, key, fields, agency):
        if key in skip:
            return
        r = recs.setdefault((kind, key), dict(id=key, kind=kind, n=0, **fields))
        r["n"] += 1
        agencies[(kind, key)][agency] += 1

    for fy in YEARS:
        path = os.path.join(data, f"CB FY{fy} Requests (all boards, detailed, 2-stage).csv")
        if not os.path.exists(path):
            continue
        d = pd.read_csv(path, dtype=str).fillna("")
        for _, row in d.iterrows():
            a, o, ag = ws(row["Agency Response"]), ws(row["OMB Executive Response"]), row["Agency"]
            if a:
                add("response", text_key(a), {"text": a}, ag)
            if omb_quoted(a, o):
                add("omb", text_key(o), {"text": o}, ag)
            if fy in PDF_YEARS or int(fy) >= 2026:
                t, e = ws(row["Title"]), ws(row["Explanation"])
                if t or e:
                    add("request", text_key(request_text(t, e)),
                        {"title": t, "explanation": e, "type": row["Type"], "board": row["Board"]}, ag)
    for k, r in recs.items():
        r["agencies"] = [a for a, _ in agencies[k].most_common(3)]
    return recs


def write_chunks(work, name, recs, max_bytes):
    chunks, cur, size = [], [], 0
    for r in recs:
        line = json.dumps(r, ensure_ascii=False) + "\n"
        if cur and size + len(line.encode()) > max_bytes:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(line)
        size += len(line.encode())
    if cur:
        chunks.append(cur)
    for i, lines in enumerate(chunks):
        with open(f"{work}/chunks/{name}_{i:02d}.jsonl", "w") as f:
            f.writelines(lines)
    return len(chunks)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    data, work = args[0], args[1]
    max_bytes = int(args[2] if len(args) > 2 else 110) * 1024
    skip = set(pd.read_csv(LETTER_CSV, dtype=str)["id"]) if os.path.exists(LETTER_CSV) else set()
    if os.path.exists(HAND):
        skip |= {x["id"] for x in json.load(open(HAND))}
    recs = collect(data, skip)
    os.makedirs(f"{work}/chunks", exist_ok=True)
    for f in glob.glob(f"{work}/chunks/*.jsonl"):
        os.remove(f)
    by = collections.defaultdict(list)
    for (kind, _), r in sorted(recs.items(), key=lambda kv: kv[0]):
        by[kind].append(r)
    if "--pilot" in sys.argv:
        rnd = random.Random(2026)
        resp = sorted(by["response"], key=lambda r: -r["n"])
        pick = resp[:15] + rnd.sample(resp[15:], 25) + rnd.sample(by["request"], 40) + rnd.sample(by["omb"], min(10, len(by["omb"])))
        with open(f"{work}/chunks/pilot.jsonl", "w") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in pick)
        print(f"pilot: {len(pick)} records -> {work}/chunks/pilot.jsonl")
        return
    for kind in ("response", "request", "omb"):
        n = write_chunks(work, kind, by[kind], max_bytes)
        print(f"{kind:8} {len(by[kind]):5} records (covering {sum(r['n'] for r in by[kind])} rows) in {n} chunks")
    print(f"skipped {len(skip)} already described")


if __name__ == "__main__":
    main()
