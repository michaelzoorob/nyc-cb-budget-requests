#!/usr/bin/env python3
"""Find the council district of requests that name a place, so a follow-up letter can
go to the Council Member whose district holds the site.

    locate_requests.py DATA_DIR [OUT_CSV]

Two official sources:
- Parks. A request that names a park or playground takes that property's council
  district(s) from NYC Parks Properties (NYC Open Data enfh-gkve). The park must be in
  the board's borough, and in the board's own district unless its name is specific
  (three words or more).
- Streets. An FY2026+ Statement explanation that begins "Location: <street> - <cross>
  & <cross>" is placed where the street meets the first cross street (NYC Street
  Centerline, NYC Open Data inkn-q76z), and takes the council district containing that
  point (DCP's council district boundaries).

A located site must fall in one of the board's own council districts
(contacts/board_council_districts.csv); matches elsewhere are dropped.

Writes OUT_CSV (default pipeline/request_locations.csv) with one row per located
Label ID: label_id, council_districts (pipe-separated), method, matched. Street
geometries are cached in DATA_DIR/streets_cache.json.
"""
import glob
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import geopandas as gpd
import pandas as pd
from shapely import make_valid
from shapely.geometry import shape
from shapely.ops import nearest_points, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "request_locations.csv")
CACHE = os.path.join(DATA, "streets_cache.json")
COUNCIL = ("https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/NYC_City_Council_Districts/"
           "FeatureServer/0/query?where=1%3D1&outFields=CounDist&outSR=4326&f=pgeojson")
PARKS = "https://data.cityofnewyork.us/resource/enfh-gkve.json"
CENTERLINE = "https://data.cityofnewyork.us/resource/inkn-q76z.geojson"
BORO_CODE = {"M": "1", "BX": "2", "BK": "3", "Q": "4", "SI": "5"}      # board prefix -> borough code
PARK_BORO = {"M": "M", "BX": "X", "BK": "B", "Q": "Q", "SI": "R"}     # board prefix -> Parks borough letter
SUFFIX = {"STREET": "ST", "STREETS": "ST", "AVENUE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD", "ROAD": "RD",
          "PLACE": "PL", "DRIVE": "DR", "PARKWAY": "PKWY", "EXPRESSWAY": "EXPY", "LANE": "LN", "TERRACE": "TER",
          "COURT": "CT", "HIGHWAY": "HWY", "TURNPIKE": "TPKE", "SQUARE": "SQ", "PLAZA": "PLZ",
          "SAINT": "ST", "FORT": "FT", "MOUNT": "MT"}
DIRECTION = {"EAST": "E", "WEST": "W", "NORTH": "N", "SOUTH": "S"}
NUMBER = {w: str(i) for i, w in enumerate(["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH",
                                            "EIGHTH", "NINTH", "TENTH", "ELEVENTH", "TWELFTH"], 1)}
ALIAS = {("1", "6 AVE"): "AVE OF THE AMERICAS"}


def fetch(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    return urllib.request.urlopen(req, timeout=120).read()


def board_parts(board):
    m = re.match(r"^(BX|BK|SI|M|Q)CB(\d+)$", board)
    return m.group(1), int(m.group(2))


def collapse(s):
    return " ".join(s.split())


def street_variants(s, boro):
    """Spellings to try against the Centerline names: '147th Avenue' -> '147 AVE';
    'West Houston Street' -> 'W HOUSTON ST' or 'WEST HOUSTON ST'; 'West Street' -> 'WEST ST'."""
    words = [NUMBER.get(w, w) for w in re.sub(r"[.,]", " ", s.upper()).split()]
    words = [SUFFIX.get(re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", w), re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", w)) for w in words]
    out = [" ".join(words)]
    if len(words) >= 3 and words[0] in DIRECTION:          # a leading direction on a longer name
        out.append(" ".join([DIRECTION[words[0]]] + words[1:]))
    out += [ALIAS[(boro, v)] for v in out if (boro, v) in ALIAS]
    if re.match(r"^\d+ (ST|AVE|PL|RD|DR)$", out[0]):       # Manhattan's "14 ST" is E 14 ST or W 14 ST
        out += ["E " + out[0], "W " + out[0]]
    if not re.search(r" (ST|AVE|BLVD|RD|PL|DR|PKWY|EXPY|LN|TER|CT|HWY|TPKE|SQ|PLZ|WAY|CONCOURSE|BROADWAY|LOOP)$", out[0]):
        out += [out[0] + " AVE", out[0] + " ST"]         # "Nostrand" -> NOSTRAND AVE
    return out


class Streets:
    def __init__(self):
        self.cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
        self.names = {}

    def resolve(self, boro, text):
        """The Centerline's exact spelling of a street, or None."""
        if boro not in self.names:
            rows = json.loads(fetch(CENTERLINE.replace(".geojson", ".json"),
                                    {"$select": "distinct full_street_name", "$where": f"boroughcode='{boro}'",
                                     "$limit": "50000"}))
            self.names[boro] = {collapse(r["full_street_name"]): r["full_street_name"] for r in rows
                                if r.get("full_street_name")}
        return [self.names[boro][v] for v in street_variants(text, boro) if v in self.names[boro]]

    def geom(self, boro, name):
        key = f"{boro}|{name}"
        if key not in self.cache:
            try:
                g = json.loads(fetch(CENTERLINE, {"$select": "the_geom", "$limit": "5000",
                                                  "$where": f"boroughcode='{boro}' AND full_street_name='{name.replace(chr(39), chr(39) * 2)}'"}))
                self.cache[key] = [f["geometry"] for f in g.get("features", []) if f.get("geometry")]
            except Exception:
                return None                       # leave uncached so a rerun tries again
        feats = self.cache[key]
        return unary_union([shape(f) for f in feats]) if feats else None

    def save(self):
        json.dump(self.cache, open(CACHE, "w"))


def main():
    council = gpd.read_file(io.BytesIO(fetch(COUNCIL)))
    council["geometry"] = council.geometry.apply(make_valid)
    parks = pd.DataFrame(json.loads(fetch(PARKS, {"$select": "signname,borough,communityboard,councildistrict",
                                                  "$limit": "10000"}))).fillna("")
    parks["key"] = parks["signname"].str.lower().str.replace(r"[^a-z0-9 ]", " ", regex=True).str.split().str.join(" ")
    parks = parks[parks["key"].str.split().str.len() >= 2]
    streets = Streets()
    # A site must lie in one of the board's own council districts; a match elsewhere is a
    # same-named street in another neighborhood, or part of a long parkway.
    ov = pd.read_csv(os.path.join(HERE, "contacts", "board_council_districts.csv"), dtype=str)
    board_districts = {b: set(map(int, g)) for b, g in ov.groupby("board")["council_district"]}

    rows, seen = [], set()
    for path in sorted(glob.glob(os.path.join(DATA, "CB FY20*Requests (all boards, detailed, 2-stage).csv"))):
        d = pd.read_csv(path, dtype=str).fillna("")
        for lid, board, title, expl in zip(d["Label ID"], d["Board"], d["Title"], d["Explanation"]):
            if lid in seen:
                continue
            seen.add(lid)
            pre, num = board_parts(board)
            hit = None
            boro = BORO_CODE[pre]
            m = re.match(r"\s*Location:\s*(.+?)\s+-\s+(.+?)\s+&\s+(\S+(?:\s+\S+){0,3})", expl)
            m2 = None if m else re.match(r"\s*Location:\s*(.+?)\s+&\s+(\S+(?:\s+\S+){0,3})", expl)
            # "A - B & C <text>": try B, then C (its first one to four words, since the
            # explanation follows it); "A & B <text>": B is the first one to four words.
            pairs = []
            if m:
                w = m.group(3).split()
                pairs = [(m.group(1), m.group(2))] + [(m.group(1), " ".join(w[:n])) for n in range(1, len(w) + 1)]
            elif m2:
                w = m2.group(2).split()
                pairs = [(m2.group(1), " ".join(w[:n])) for n in range(1, len(w) + 1)]
            near = None
            for sa, sb in pairs:
                for a in streets.resolve(boro, sa):
                    for b in streets.resolve(boro, sb):
                        ga, gb = streets.geom(boro, a), streets.geom(boro, b)
                        if ga is None or gb is None:
                            continue
                        x = ga.intersection(gb)
                        if not x.is_empty:
                            pt = x.representative_point()
                        else:                       # streets that come within ~100 m of each other
                            pa, pb = nearest_points(ga, gb)
                            if pa.distance(pb) > 0.0012 or near:
                                continue
                            pt = pa
                        cd = council[council.contains(pt)]["CounDist"].astype(int).tolist()
                        if cd and not x.is_empty:
                            hit = (cd, "intersection", f"{collapse(a)} & {collapse(b)}")
                            break
                        if cd and near is None:
                            near = (cd, "intersection", f"{collapse(a)} near {collapse(b)}")
                    if hit:
                        break
                if hit:
                    break
            hit = hit or near
            if hit is None:
                text = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", f"{title} {expl}".lower())) + " "
                own = f"{BORO_CODE[pre]}{num:02d}"
                cands = parks[(parks["borough"] == PARK_BORO[pre]) & parks["key"].map(lambda k: f" {k} " in text)]
                cands = cands[cands["communityboard"].str.contains(own) | (cands["key"].str.split().str.len() >= 3)]
                if len(cands):
                    best = cands.loc[cands["key"].str.len().idxmax()]
                    cd = sorted({int(c) for c in re.findall(r"\d+", best["councildistrict"])})
                    if cd:
                        hit = (cd, "park", best["signname"])
            if hit:
                inside = [c for c in hit[0] if c in board_districts.get(board, set())]
                if inside:
                    rows.append({"label_id": lid, "council_districts": "|".join(map(str, inside)),
                                 "method": hit[1], "matched": hit[2]})
    streets.save()
    out = pd.DataFrame(rows, columns=["label_id", "council_districts", "method", "matched"])
    out.to_csv(OUT, index=False)
    print(f"located {len(out)} of {len(seen)} requests "
          f"({(out['method'] == 'intersection').sum()} by street intersection, {(out['method'] == 'park').sum()} by park)")


if __name__ == "__main__":
    main()
