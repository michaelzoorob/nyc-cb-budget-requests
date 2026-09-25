#!/usr/bin/env python3
"""Add each request's history and located council district to every year's CSV.

    enrich_years.py DATA_DIR

Run it after every year's CSV is built, and after locate_requests.py.

History. Two requests from one board count as the same
request when the first 150 characters of one's normalized explanation appear in the
other's. (The FY2026+ Statements put a location before the text, so an exact match
misses those.) Two columns follow from that:
- History Years: every fiscal year in which the board made the request, "|"-separated
- Prior Response: "<YEAR>: <text>", the agency response from the most recent earlier year

Location. From pipeline/request_locations.csv, by Label ID:
- Location Districts: the council district(s) holding the site the request names
- Location Match: the park or street intersection that placed it
"""
import glob
import os
import re
import sys

import pandas as pd

DATA = sys.argv[1] if len(sys.argv) > 1 else "."
LOCATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "request_locations.csv")
KEY_LEN, MIN_LEN = 150, 40


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


# A sentence ends at . ! or ? before a space, except after an abbreviation such as "U.S."
ABBR = re.compile(r"^(?:\(?[A-Z]\.|(?:[A-Za-z]\.){2,}|(?:St|Ave|Dept|No|Nos|Mr|Ms|Mrs|Dr|Inc|Co|Corp|Jr|Sr|vs|approx"
                  r"|Blvd|Rd|Pl|Pkwy|Bldg|Fl|Rm|Ste|Div)\.)$")


def sentences(s):
    s = " ".join(str(s).split())
    out, start = [], 0
    for m in re.finditer(r"[.!?]+(?=\s|$)", s):
        words = s[start:m.end()].split()
        if m.end() < len(s) and words and ABBR.match(words[-1]):
            continue
        out.append(s[start:m.end()].strip())
        start = m.end()
    if s[start:].strip():
        out.append(s[start:].strip())
    return out


def lead(s, n=2, cap=240):
    out = " ".join(sentences(s)[:n])
    return out if len(out) <= cap else out[:cap].rsplit(" ", 1)[0] + "…"


def main():
    files = {re.search(r"CB FY(\d{4})", f).group(1): f
             for f in glob.glob(os.path.join(DATA, "CB FY20*Requests (all boards, detailed, 2-stage).csv"))}
    frames = {fy: pd.read_csv(f, dtype=str).fillna("") for fy, f in files.items()}
    items = []                                 # (board, fy, row index, normalized explanation)
    for fy, d in frames.items():
        for i, (b, e) in enumerate(zip(d["Board"], d["Explanation"])):
            items.append((b, fy, i, norm(e)))
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_board = {}
    for k, it in enumerate(items):
        if len(it[3]) >= MIN_LEN:
            by_board.setdefault(it[0], []).append(k)
    for ks in by_board.values():
        for x, a in enumerate(ks):
            ta = items[a][3]
            for b in ks[x + 1:]:
                if items[a][1] == items[b][1]:
                    continue                    # the same year: different requests
                tb = items[b][3]
                if ta[:KEY_LEN] in tb or tb[:KEY_LEN] in ta:
                    parent[find(a)] = find(b)
    groups = {}
    for k in range(len(items)):
        groups.setdefault(find(k), []).append(k)
    for fy, d in frames.items():
        d["History Years"], d["Prior Response"] = "", ""
    for ks in groups.values():
        years = sorted({items[k][1] for k in ks})
        if len(years) < 2:
            continue
        for k in ks:
            b, fy, i, _ = items[k]
            frames[fy].at[i, "History Years"] = "|".join(years)
            earlier = [items[j] for j in ks if items[j][1] < fy]
            if earlier:
                pfy = max(e[1] for e in earlier)
                resp = next((frames[pfy].at[e[2], "Agency Response"] for e in earlier
                             if e[1] == pfy and frames[pfy].at[e[2], "Agency Response"].strip()), "")
                if resp:
                    frames[fy].at[i, "Prior Response"] = f"{pfy}: {lead(resp)}"
    loc = pd.read_csv(LOCATIONS, dtype=str).fillna("") if os.path.exists(LOCATIONS) else pd.DataFrame(
        columns=["label_id", "council_districts", "matched"])
    where = {r["label_id"]: r for r in loc.to_dict("records")}
    for fy, d in frames.items():
        d["Location Districts"] = [where[i]["council_districts"] if i in where else "" for i in d["Label ID"]]
        d["Location Match"] = [where[i]["matched"] if i in where else "" for i in d["Label ID"]]
        d.to_csv(files[fy], index=False)
        print(f"FY{fy}: {(d['History Years'] != '').sum()} of {len(d)} requests appear in another year; "
              f"{(d['Location Districts'] != '').sum()} located")


if __name__ == "__main__":
    main()
