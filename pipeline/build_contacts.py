#!/usr/bin/env python3
"""Build the elected-official half of the follow-up contact directory.

    build_contacts.py [OUT_DIR]

Writes to OUT_DIR (default pipeline/contacts/):
- board_council_districts.csv: for each community board, the council districts that
  cover at least 1% of its land area, with that share. Computed from DCP's community
  district and city council district boundaries (Bytes of the Big Apple).
- council_members.csv: each council district's member, email and page, parsed from
  council.nyc.gov/districts/.

Rerun it after council elections or redistricting. Agency and Borough President
contacts are curated by hand in agency_contacts.csv and borough_presidents.csv, since
no official source lists them in one place.
"""
import datetime
import html
import io
import json
import os
import re
import sys
import urllib.request

import geopandas as gpd
import pandas as pd
from shapely import make_valid

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts")
LAYER = ("https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/{}/FeatureServer/0/query"
         "?where=1%3D1&outFields=*&outSR=4326&f=pgeojson")
COUNCIL = "https://council.nyc.gov/districts/"
BORO = {1: "M", 2: "BX", 3: "BK", 4: "Q", 5: "SI"}
LEADERSHIP = ("Deputy Speaker", "Majority Leader", "Minority Leader", "Majority Whip", "Minority Whip", "Speaker")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    return urllib.request.urlopen(req, timeout=120).read()


def overlaps():
    def layer(name):
        g = gpd.read_file(io.BytesIO(fetch(LAYER.format(name)))).to_crs(2263)   # NY State Plane, feet
        g["geometry"] = g.geometry.apply(make_valid)   # both layers ship invalid rings
        return g
    cd, cc = layer("NYC_Community_Districts"), layer("NYC_City_Council_Districts")
    cd = cd[cd["BoroCD"].astype(int) % 100 <= 18]           # drop joint interest areas (parks, airports)
    rows = []
    for _, c in cd.iterrows():
        b = int(c["BoroCD"])
        board = f"{BORO[b // 100]}CB{b % 100}"
        for _, k in cc.iterrows():
            share = c.geometry.intersection(k.geometry).area / c.geometry.area
            if share >= 0.01:
                rows.append({"board": board, "council_district": int(k["CounDist"]), "share": round(share, 3)})
    out = pd.DataFrame(rows).sort_values(["board", "share"], ascending=[True, False])
    if out["board"].nunique() != 59:
        sys.exit(f"expected 59 community boards, got {out['board'].nunique()}")
    return out


def council_members():
    t = fetch(COUNCIL).decode("utf-8", "replace")
    rows = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        cells = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if not cells or not cells[0].isdigit():
            continue
        full = cells[1]
        lead = next((p for p in LEADERSHIP if full.startswith(p + " ")), "")
        name = full[len(lead):].strip()
        plain = re.sub(r"^Dr\.\s+", "", name)
        email = re.findall(r"[A-Za-z0-9._%+-]+@council\.nyc\.gov", r)
        page = re.findall(r'href="(https://council\.nyc\.gov/district-\d+/?)"', r)
        rows.append({"council_district": int(cells[0]), "name": name, "leadership": lead,
                     "salutation": f"{'Speaker' if lead == 'Speaker' else 'Council Member'} {plain}",
                     "email": email[0] if email else "", "url": page[0] if page else COUNCIL})
    out = pd.DataFrame(rows).sort_values("council_district")
    if len(out) != 51 or (out["email"] == "").any():
        sys.exit(f"expected 51 members with emails, got {len(out)} ({(out['email'] == '').sum()} without)")
    out["source"] = COUNCIL
    out["as_of"] = datetime.date.today().isoformat()
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ov = overlaps()
    ov.to_csv(os.path.join(OUT, "board_council_districts.csv"), index=False)
    cm = council_members()
    cm.to_csv(os.path.join(OUT, "council_members.csv"), index=False)
    print(f"{len(ov)} board-district overlaps for {ov['board'].nunique()} boards; {len(cm)} council members -> {OUT}")
