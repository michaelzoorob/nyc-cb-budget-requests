#!/usr/bin/env python3
"""Add each request's history and located council district to every year's CSV.

    enrich_years.py DATA_DIR

Run it after every year's CSV is built, and after locate_requests.py.

History. Two requests from one board count as the same request when the first 150
characters of one's normalized explanation appear in the other's. (The FY2026+ Statements
put a location before the text, so an exact match misses those.) A board may send one text
for several sites, so when both requests name a site (shared.parse_site) and the sites are
not plainly one place (shared.site_match), the pair links only if a model judged it the same
request. Two requests also count as the same when a model judged them the same request
reworded. Both kinds of verdict are in pipeline/repeat_links.csv, written by label_repeats/.
When a board sent one text for two sites in a year, a verdict must name the site, by its
shared.site_key or by the Label ID and "@-" for the request with no site. A verdict that
names only the Label ID is not used.

Two requests judged different never end up in one history through a third, and neither do
two identical requests (one Label ID) that a board listed in one year for sites that are not
plainly one place. A request without a site does not link to the same text that the board
sent for several sites in another year. Links are made in order of certainty, nearer years
first. Two columns follow:
- History Years: every fiscal year in which the board made the request, "|"-separated
- Prior Response: "<YEAR>: <text>", the agency response from the most recent earlier year

Location. From pipeline/request_locations.csv, by shared.site_key:
- Location Districts: the council district(s) holding the site the request names
- Location Match: the park or street intersection that placed it
"""
import glob
import os
import re
import sys

import pandas as pd

from shared import parse_site, site_key, site_match

DATA = sys.argv[1] if len(sys.argv) > 1 else "."
LOCATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "request_locations.csv")
LINKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "repeat_links.csv")
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


def same_text(a, b):
    """Whether two normalized explanations are the same text (the rule above)."""
    return len(a) >= MIN_LEN and len(b) >= MIN_LEN and (a[:KEY_LEN] in b or b[:KEY_LEN] in a)


def text_pairs(items):
    """Index pairs (earlier year first) of one board's requests from two years with the same text."""
    by_board = {}
    for k, it in enumerate(items):
        if len(it[3]) >= MIN_LEN:
            by_board.setdefault(it[0], []).append(k)
    for ks in by_board.values():
        for x, a in enumerate(ks):
            for b in ks[x + 1:]:
                if items[a][1] != items[b][1] and same_text(items[a][3], items[b][3]):
                    yield (a, b) if items[a][1] < items[b][1] else (b, a)


def load_items(frames):
    """Every request as (board, fy, row index, normalized explanation), with its site and site key."""
    items, sites, keys = [], [], []
    for fy, d in frames.items():
        loc = d["Location"] if "Location" in d else [""] * len(d)
        for i, (b, e, lid, l) in enumerate(zip(d["Board"], d["Explanation"], d["Label ID"], loc)):
            items.append((b, fy, i, norm(e)))
            sites.append(parse_site(l, e))
            keys.append(site_key(lid, l))
    return items, sites, keys


def main():
    files = {re.search(r"CB FY(\d{4})", f).group(1): f
             for f in sorted(glob.glob(os.path.join(DATA, "CB FY20*Requests (all boards, detailed, 2-stage).csv")))}
    frames = {fy: pd.read_csv(f, dtype=str).fillna("") for fy, f in files.items()}
    items, sites, keys = load_items(frames)
    links = pd.read_csv(LINKS, dtype=str).fillna("") if os.path.exists(LINKS) else pd.DataFrame(
        columns=["then_fy", "then_label", "now_fy", "now_label", "verdict", "kind"])
    if "kind" not in links:
        links["kind"] = "reworded"
    verdict = {(a, b, c, d): v for a, b, c, d, v in
               zip(links.then_fy, links.then_label, links.now_fy, links.now_label, links.verdict)}
    # The same text in two years: linked at once when the sites are plainly one place or
    # either names none, otherwise only when judged the same request. Links are made in
    # order of certainty, so a doubtful one cannot block a plain one, and nearer years
    # first, so a request without a site joins the request of the year before.
    plain, judged, loose, apart, waiting = [], [], [], [], 0
    for a, b in text_pairs(items):
        if sites[a] is None or sites[b] is None:
            loose.append((a, b))
        elif site_match(sites[a], sites[b]) == "same":
            plain.append((a, b))
        else:
            v = verdict.get((items[a][1], keys[a], items[b][1], keys[b]))
            (judged if v == "same" else apart).append((a, b))
            waiting += v is None
    parent = list(range(len(items)))
    group = {k: {k} for k in range(len(items))}
    avoid = {k: set() for k in range(len(items))}   # rows a group may not take in
    by_label, sited = {}, {}
    for k, (b, fy, i, _) in enumerate(items):
        by_label.setdefault((fy, frames[fy].at[i, "Label ID"]), []).append(k)
        if sites[k] is not None:
            sited.setdefault((b, fy), []).append(k)
    label = lambda k: frames[items[k][1]].at[items[k][2], "Label ID"]
    for ks in sited.values():                       # one request listed for two sites in one year
        apart += [(a, b) for x, a in enumerate(ks) for b in ks[x + 1:] if keys[a] != keys[b]
                  and label(a) == label(b) and site_match(sites[a], sites[b]) == "judge"]
    for a, b in apart:
        avoid[a].add(b)
        avoid[b].add(a)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(a, b):
        ra, rb = find(a), find(b)
        if ra == rb or avoid[ra] & group[rb]:
            return
        parent[ra] = rb
        group[rb] |= group.pop(ra)
        avoid[rb] |= avoid.pop(ra)

    # A request without a site whose text the board sent for several sites in another year
    # is not any one of them (a general request and a specific one, rubric.md).
    seen_at = {}
    for a, b in loose:
        for u, k in ((a, b), (b, a)):
            if sites[u] is None and sites[k] is not None:
                seen_at.setdefault((u, items[k][1]), []).append(k)
    unclear = {key for key, ks in seen_at.items()
               if any(site_match(sites[x], sites[y]) == "judge" for i, x in enumerate(ks) for y in ks[i + 1:])}
    vague = lambda u, k: sites[u] is None and sites[k] is not None and (u, items[k][1]) in unclear
    n_vague = sum(1 for a, b in loose if vague(a, b) or vague(b, a))
    loose = [(a, b) for a, b in loose if not (vague(a, b) or vague(b, a))]
    gap = lambda p: int(items[p[1]][1]) - int(items[p[0]][1])
    plain, judged, loose = (sorted(x, key=gap) for x in (plain, judged, loose))
    for a, b in plain + judged:
        join(a, b)
    # Reworded requests a model judged the same request, by fiscal year and Label ID, or by
    # site key when the board sent the text for two sites that year.
    at = {}
    for (fy, lab), ks in by_label.items():
        several = len({keys[k] for k in ks}) > 1
        for k in ks:
            at.setdefault((fy, lab), []).append(k)
            if "@" in keys[k]:
                at.setdefault((fy, keys[k]), []).append(k)
            elif several:
                at.setdefault((fy, lab + "@-"), []).append(k)
    n_links = unnamed = 0
    for r in links[(links.verdict == "same") & (links.kind == "reworded")].to_dict("records"):
        then, now = at.get((r["then_fy"], r["then_label"]), []), at.get((r["now_fy"], r["now_label"]), [])
        if not (then and now):
            continue
        if len({keys[k] for k in then}) > 1 or len({keys[k] for k in now}) > 1:
            unnamed += 1                              # the verdict does not say which site
            continue
        for a in then:
            for b in now:
                join(a, b)
        n_links += 1
    for a, b in loose:
        join(a, b)
    n_site = int((links.kind == "site").sum())
    print(f"{n_links} reworded requests linked from {os.path.basename(LINKS)}"
          + (f" ({unnamed} not used: the text was sent for two sites that year)" if unnamed else "")
          + f". Same text at sites not plainly one place: {n_site} pairs judged"
          + (f", {waiting} await a judge (label_repeats/prepare.py --sites)" if waiting else "")
          + f". {n_vague} links left out from a request without a site to one of several sites.")
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
        at_site = [site_key(i, l) for i, l in zip(d["Label ID"], d["Location"] if "Location" in d else [""] * len(d))]
        d["Location Districts"] = [where[k]["council_districts"] if k in where else "" for k in at_site]
        d["Location Match"] = [where[k]["matched"] if k in where else "" for k in at_site]
        d.to_csv(files[fy], index=False)
        print(f"FY{fy}: {(d['History Years'] != '').sum()} of {len(d)} requests appear in another year; "
              f"{(d['Location Districts'] != '').sum()} located")


if __name__ == "__main__":
    main()
