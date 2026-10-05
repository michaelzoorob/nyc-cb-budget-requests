#!/usr/bin/env python3
"""Local facts for the follow-up letters.

    letter_facts.py [DATA_DIR] [--refresh]

A letter about a request can say what the City's own open data show about its place or
its need: how NYC Parks inspectors rated a playground, how many crashes police reported
at an intersection, how full a school is. Each fact is a sentence or two that names its
period and its source. A fact is written only where it clearly applies to the request
and supports it, so most requests get none. Seven kinds:

  park_inspection  a Parks request about one named park: overall and feature ratings from
                   the Parks Inspection Program (yg3y-7juh, 5mma-5n3h)
  school           a school request that names one school: the School Construction
                   Authority's Enrollment, Capacity and Utilization report (gkd7-3vk7)
  crashes          a traffic-safety request at a located intersection or stretch of
                   street: NYPD crash reports (h9gi-nx95)
  site_311         a request about flooding, sewer backups, street lights, a broken signal
                   or speeding at a located site: 311 service requests nearby (erm2-nwe9)
  park_access      a request for a new park or open space: residents beyond walking
                   distance of a park (Walk to a Park, 99ii-hwh9, with 2020 Census blocks)
  street_trees     a tree-planting request: empty street tree beds in the district
                   (Forestry Planting Spaces, 82zj-84is)
  district_311     a request on a need that 311 measures, where the district ranks in the
                   top quarter or complaints rose: the planner's counts (plan/planner.json)

A site comes from the request's "Location:" line (FY2026 and later statements), from the
Register's site fields in the Location column (FY2020 to FY2025), or from its park match
in request_locations.csv. A request gets at most two facts. Downloads are
cached in DATA_DIR/letter_facts/ (DATA_DIR defaults to ~/Downloads), by month for data
that change, so a rebuild in a new month gets the latest; --refresh downloads them all
again. Writes pipeline/letter_facts.csv.
"""
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import LineString, Point
from shapely.ops import transform, unary_union

import locate_requests as loc
from shared import YEARS, site_key

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
DATA = os.path.expanduser(_args[0] if _args else "~/Downloads")
CACHE = os.path.join(DATA, "letter_facts")
OUT = os.path.join(HERE, "letter_facts.csv")
REFRESH = "--refresh" in sys.argv
TODAY = dt.date.today()
MONTH_TAG = TODAY.strftime("%Y-%m")       # caches of data that change are named by month

SODA = "https://data.cityofnewyork.us/resource/{}.json"
DATASET = "https://data.cityofnewyork.us/d/{}"
TIGERWEB = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/12/query"
TO_FT = Transformer.from_crs(4326, 2263, always_xy=True).transform     # Long Island state plane, feet
ECU_BORO = {"M": "M", "BX": "X", "BK": "K", "Q": "Q", "SI": "R"}        # board prefix -> school borough letter
COUNTY = ["005", "047", "061", "081", "085"]                          # census county codes of the five boroughs
MONTH = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
         "October", "November", "December"]
ORDINAL = ["", "", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
# Facts about the site come before facts about the district; a request keeps the first two.
ORDER = ["park_inspection", "school", "crashes", "site_311", "park_access", "street_trees", "district_311"]


# ---- downloads ---------------------------------------------------------------------

def get_json(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))


def cached(name):
    path = os.path.join(CACHE, name)
    return path, os.path.exists(path) and not REFRESH


def soda(ds, name, **params):
    """Every row of a SODA query, cached as DATA_DIR/letter_facts/<name>.csv."""
    path, have = cached(name + ".csv")
    if not have:
        rows, page = [], 50000
        params.setdefault("$order", ":id")
        while True:
            q = dict(params, **{"$limit": page, "$offset": len(rows)})
            batch = get_json(SODA.format(ds) + "?" + urllib.parse.urlencode(q))
            rows += batch
            if len(batch) < page:
                break
        pd.DataFrame(rows).to_csv(path + ".part", index=False)
        os.replace(path + ".part", path)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def geo(ds, name, **params):
    """A SODA dataset's features as a GeoDataFrame in feet, cached as <name>.geojson."""
    path, have = cached(name + ".geojson")
    if not have:
        feats, page = [], 50000
        params.setdefault("$order", ":id")
        while True:
            q = dict(params, **{"$limit": page, "$offset": len(feats)})
            batch = get_json(SODA.format(ds).replace(".json", ".geojson") + "?" + urllib.parse.urlencode(q))["features"]
            feats += batch
            if len(batch) < page:
                break
        json.dump({"type": "FeatureCollection", "features": feats}, open(path + ".part", "w"))
        os.replace(path + ".part", path)
    return gpd.read_file(path).to_crs(2263)


def points(df, lat="latitude", lon="longitude"):
    """Rows with usable coordinates, as points in feet."""
    df = df[pd.to_numeric(df[lat], errors="coerce").between(40.4, 41.0)
            & pd.to_numeric(df[lon], errors="coerce").between(-74.3, -73.6)]
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon].astype(float), df[lat].astype(float)),
                            crs=4326).to_crs(2263)


def within(gdf, area):
    """The rows of gdf inside area."""
    return gdf.iloc[gdf.sindex.query(area, predicate="intersects")]


# ---- wording -----------------------------------------------------------------------

def first_of_month(d, add=0):
    m = d.year * 12 + d.month - 1 + add
    return dt.date(m // 12, m % 12 + 1, 1)


def span(start, end):
    """'from June 2023 through May 2026' for the months from start up to end."""
    last = end - dt.timedelta(days=1)
    return f"from {MONTH[start.month - 1]} {start.year} through {MONTH[last.month - 1]} {last.year}"


def nth(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def highest(rank):
    return "the highest" if rank == 1 else f"the {ORDINAL[rank] if rank < len(ORDINAL) else nth(rank)} highest"


def count(n, one, many=None):
    return f"{n:,} {one if n == 1 else many or one + 's'}"


def and_list(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


SUFFIX = [("St", "Street"), ("Ave", "Avenue"), ("Av", "Avenue"), ("Blvd", "Boulevard"), ("Pkwy", "Parkway"),
          ("Expwy", "Expressway"), ("Expy", "Expressway"), ("Rd", "Road"), ("Pl", "Place"), ("Dr", "Drive"),
          ("Ln", "Lane"), ("Hwy", "Highway"), ("Tpke", "Turnpike"), ("Ter", "Terrace"), ("Ct", "Court")]


def street_name(s):
    """A street as the board wrote it, tidied for a sentence: '74th st' -> '74th Street',
    'E 72 St' -> 'East 72nd Street'."""
    s = " ".join(s.split()).strip(" .,;:()")
    if s.isupper() or s.islower():
        s = re.sub(r"(\d)(St|Nd|Rd|Th)\b", lambda m: m.group(1) + m.group(2).lower(), s.title())
    for a, b in SUFFIX:
        s = re.sub(rf"\b{a}\.?(?=$| (?:North|South|East|West)$)", b, s, flags=re.I)
    s = re.sub(r" (north|south|east|west)$", lambda m: " " + m.group(1).title(), s, flags=re.I)
    s = re.sub(r"^([NSEW])(?:\.\s*|\s+)(?=\d|\S+ \S)", lambda m: {"N": "North ", "S": "South ", "E": "East ", "W": "West "}[m.group(1)], s)
    s = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", lambda m: nth(int(m.group(1))), s, flags=re.I)     # "34st" -> "34th"
    return re.sub(r"\b(\d+) (Street|Avenue|Road|Place|Drive|Lane|Terrace|Court)\b",
                  lambda m: f"{nth(int(m.group(1)))} {m.group(2)}", s)


# ---- requests and sites ------------------------------------------------------------

def load_requests():
    frames = []
    for fy in YEARS:                      # newest first, so a request keeps its latest text
        p = os.path.join(DATA, f"CB FY{fy} Requests (all boards, detailed, 2-stage).csv")
        if os.path.exists(p):
            frames.append(pd.read_csv(p, dtype=str, keep_default_na=False).assign(FY=fy))
    d = pd.concat(frames).fillna("")
    if "Location" not in d:
        d["Location"] = ""
    # Facts are keyed by site: the same text can name two sites (shared.site_key).
    d["Label ID"] = [site_key(i, l) for i, l in zip(d["Label ID"], d["Location"])]
    d = d.drop_duplicates("Label ID").reset_index(drop=True)
    d["text"] = (d["Title"] + " || " + d["Explanation"]).str.replace(r"\s+", " ", regex=True)
    # What the request is about: its title and the first two sentences of its explanation.
    # A fact's topic must appear here, not only further down.
    sentences = [re.split(r"(?<=[.!?])\s+", " ".join(e.split())) for e in d["Explanation"]]
    d["first"] = d["Title"] + " || " + [x[0][:300] for x in sentences]
    d["lead"] = [" ".join(x[:2])[:400] for x in sentences]
    d["main"] = d["Title"] + " || " + d["lead"]
    parts = d["Board"].map(loc.board_parts)
    d["prefix"] = parts.str[0]
    d["borocd"] = [int(loc.BORO_CODE[p]) * 100 + n for p, n in parts]
    places = pd.read_csv(os.path.join(HERE, "request_locations.csv"), dtype=str, keep_default_na=False)
    return d.merge(places.rename(columns={"label_id": "Label ID"}), on="Label ID", how="left").fillna("")


def lead_words(s, most=4):
    """The first one to `most` words of s, longest first, since the explanation runs on
    after the last street name."""
    w = s.split()
    return [" ".join(w[:k]).strip(" .,;:()") for k in range(min(most, len(w)), 0, -1)]


def parse_location(expl):
    """(A, B choices, C choices) from 'Location: A - B & C ...', 'A & B ...' or 'A - B ...'."""
    m = re.match(r"\s*Location:\s*(.*)", expl, re.S)
    if not m:
        return None
    s = " ".join(m.group(1).split())
    m3 = re.match(r"(.+?) - (.+?) & (.+)", s)
    if m3 and len(m3.group(1).split()) <= 6 and len(m3.group(2).split()) <= 5:
        return m3.group(1), [m3.group(2)], lead_words(m3.group(3))
    m2 = re.match(r"(.+?) & (.+)", s)
    if m2 and len(m2.group(1).split()) <= 6 and " - " not in m2.group(1):
        return m2.group(1), lead_words(m2.group(2)), []
    m1 = re.match(r"(.+?) - (.+)", s)
    if m1 and len(m1.group(1).split()) <= 6:
        return m1.group(1), lead_words(m1.group(2)), []
    return None


class Sites:
    """Where a request's "Location:" line puts it: one intersection, or a stretch of a street
    between two cross streets. Both must lie in the board's own district."""

    def __init__(self):
        self.streets = loc.Streets(os.path.join(DATA, "streets_cache.json"))
        cds = geo("5crt-au7u", "community_districts")
        self.cd = {int(float(b)): g for b, g in zip(cds["boro_cd"], cds.geometry)}

    def street(self, boro, text):
        names = self.streets.resolve(boro, text)
        gs = [g for g in (self.streets.geom(boro, n) for n in names) if g is not None]
        return (transform(TO_FT, unary_union(gs)), names) if gs else (None, names)

    def crossing(self, a, boro, choices, home):
        """The first choice (longest first) that crosses street a inside the district."""
        for text in choices:
            b, names = self.street(boro, text)
            if b is None:
                continue
            x = a.intersection(b)
            pts = [p for p in getattr(x, "geoms", [x]) if p.geom_type == "Point" and home.contains(p)]
            if not pts:
                continue
            # Divided roadways cross at a few nearby points; a street that crosses twice far
            # apart is ambiguous.
            if max(p.distance(q) for p in pts for q in pts) > 400:
                return None
            return text, names, unary_union(pts).centroid
        return None

    def locate(self, r):
        site = str(r.get("Location", "")).strip()      # the Register's site fields, FY2020-FY2025
        p = parse_location(f"Location: {site}" if site else r["Explanation"])
        if not p:
            return None
        a_text, b_choices, c_choices = p
        boro = loc.BORO_CODE[r["prefix"]]
        home = self.cd.get(r["borocd"])
        a, a_names = self.street(boro, a_text)
        if a is None or home is None:
            return None
        home = home.buffer(300)                 # district lines run down the middle of streets
        b = self.crossing(a, boro, b_choices, home)
        if not b:
            return None
        c = self.crossing(a, boro, c_choices, home) if c_choices else None
        if c_choices and not c:
            return None                          # a stretch whose far end we cannot place
        A, B = street_name(a_text), street_name(b[0])
        if not c or set(c[1]) & set(b[1]) or c[2].distance(b[2]) < 150:
            return {"kind": "intersection", "point": b[2], "label": f"the intersection of {A} and {B}"}
        line = LineString([b[2], c[2]])
        if not 300 <= line.length <= 10560:     # under a short block, or over two miles
            return None
        part = a.intersection(line.buffer(250, cap_style="flat"))
        if not line.length * 0.8 <= part.length <= line.length * 3.5:
            return None                          # street A does not run between B and C
        return {"kind": "stretch", "line": part, "ends": [b[2], c[2]],
                "label": f"{A} between {B} and {street_name(c[0])}"}


# ---- park_inspection ---------------------------------------------------------------

PARK_FEATURES = [  # PIP feature, words in a letter, words in a request that point to it
    ("Play Equipment", "play equipment", r"playgrounds?|play (?:equipment|areas?|structures?|spaces?)|tot lots?|swings?|slides|jungle gym|spray (?:showers?|features?)"),
    ("Safety Surface", "safety surfacing", r"safety surfac|rubber (?:surfac|mat)|play surfac"),
    ("Athletic Fields", "athletic fields", r"athletic fields?|ball ?fields?|turf|soccer|baseball|softball|football|running track"),
    ("Benches", "benches", r"\bbench(?:es)?\b"),
    ("Paved Surfaces", "paved surfaces", r"\bpath(?:way)?s?\b|walkways?|asphalt|pavement|paving"),
    ("Fences", "fences", r"\bfenc(?:e|es|ing)\b"),
    ("Lawns", "lawns", r"\blawns?\b"),
]
PARK_WORK = re.compile(r"repair|reconstruct|renovat|upgrad|replac|restor|rehabilitat|refurbish|resurfac|install|"
                       r"improve|maint|clean|fix|deteriorat|broken|damaged|unsafe|condition", re.I)
FACILITY = re.compile(r"comfort stations?|bathrooms?|restrooms?|rec(?:reation)? cent(?:er|re)s?|nature cent|\bpools?\b|"
                      r"\bdocks?\b|kayak|boat ?house|field ?house|\blighting\b|\blights\b|\bbuildings?\b|seawall|bulkhead|"
                      r"\bpiers?\b|cameras?|irrigation|dog runs?|skate ?park|stairs?|staircase|step street|drainage|erosion|"
                      r"\bwalls?\b|roof|boiler|elevator|\bHVAC\b|electric", re.I)
CLEAN = re.compile(r"\bclean|litter|trash|garbage|maintenance (?:workers?|staff)|park (?:workers?|staff)|"
                   r"city park workers?|\bCPWs?\b|gardeners?|seasonal (?:workers?|staff)|playground associates?", re.I)


def park_key(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def park_inspections(reqs):
    since = first_of_month(TODAY, -36).isoformat()
    ins = soda("yg3y-7juh", f"pip_inspections_{since}", **{
        "$select": "prop_id,inspection_id,date,overall_condition,cleanliness",
        "$where": f"inspectiontype = 'PIP' AND date >= '{since}'"})
    ins["date"] = pd.to_datetime(ins["date"]).dt.date
    end = first_of_month(max(ins["date"]), 1)
    start = first_of_month(end, -24)
    ins = ins[(ins["date"] >= start) & ins["overall_condition"].isin(["A", "U"])]
    feats = soda("5mma-5n3h", f"pip_features_{since}", **{
        "$select": "inspection_id,feature_1,rating",
        "$where": f"inspection_id >= {ins['inspection_id'].astype(int).min()} AND rating in ('A', 'U')"})
    feats = feats[feats["inspection_id"].isin(set(ins["inspection_id"]))]
    props = soda("enfh-gkve", f"parks_properties_{MONTH_TAG}", **{"$select": "gispropnum,signname,borough,communityboard"})
    props["key"] = props["signname"].map(park_key)
    named = props[props["key"].str.split().str.len() >= 2]
    when = span(start, end)

    out = {}
    for r in reqs[(reqs["method"] == "park") & reqs["Agency"].str.contains("Parks")].to_dict("records"):
        text = r["text"]
        if not (PARK_WORK.search(r["main"]) or CLEAN.search(r["main"])):
            continue                              # programs and events, not the park itself
        boro = loc.PARK_BORO[r["prefix"]]
        here = props[(props["signname"] == r["matched"]) & (props["borough"] == boro)]
        if here["gispropnum"].nunique() > 1:
            here = here[here["communityboard"].str.contains(str(r["borocd"]))]
        if here["gispropnum"].nunique() != 1:
            continue                              # a name shared by several properties
        # A request about several parks gets no single park's ratings.
        low = " " + park_key(text) + " "
        keys = {k for k in named[named["borough"] == boro]["key"] if f" {k} " in low}
        if len({k for k in keys if not any(k != j and k in j for j in keys)}) > 1:
            continue
        pid, name, main = here["gispropnum"].iloc[0], r["matched"], r["main"]
        # A large park is inspected zone by zone, and a zone's ratings may say nothing about
        # the part of the park a request is about, so those parks get no fact.
        mine = ins[ins["prop_id"] == pid]
        n, u = len(mine), int((mine["overall_condition"] == "U").sum())
        if n < 3:
            continue
        sentences = []
        # The overall rating speaks to a request about the park itself, not one about a
        # building or fixture in it.
        if u >= 2 and not FACILITY.search(main):
            sentences.append(f"NYC Parks inspectors rated {name} unacceptable overall in {u} of {n} inspections {when}.")
        if CLEAN.search(main):
            c = int((mine["cleanliness"] == "U").sum())
            if c >= 2:
                sentences.append(f"They rated it unacceptable for cleanliness in {c} of {n} inspections." if sentences else
                                 f"NYC Parks inspectors rated {name} unacceptable for cleanliness in {c} of {n} inspections {when}.")
        its = feats[feats["inspection_id"].isin(set(mine["inspection_id"]))]
        for feature, words, rx in PARK_FEATURES:
            if len(sentences) >= 2 or not re.search(rx, main, re.I):
                continue
            f = its[its["feature_1"] == feature]
            fu, fn = int((f["rating"] == "U").sum()), len(f)
            if fu >= 2:
                sentences.append(f"They rated its {words} unacceptable in {fu} of {fn} inspections." if sentences else
                                 f"NYC Parks inspectors rated the {words} at {name} unacceptable in {fu} of {fn} inspections {when}.")
        if sentences:
            out[r["Label ID"]] = " ".join(sentences)
    return out


# ---- school ------------------------------------------------------------------------

SCHOOL_REF = re.compile(r"\b(P\.? ?S|I\.? ?S|M\.? ?S|J\.? ?H\.? ?S|P\.? ?S\.? ?/ ?I\.? ?S|I\.? ?S\.? ?/ ?P\.? ?S|"
                        r"P\.? ?S\.? ?/ ?M\.? ?S)\.? ?#? ?(\d{1,3})(?! ?(?:years?|yrs|percent|%|students|seats|feet|ft|"
                        r"degrees|hours|minutes|days|million|thousand|k\b))\b")
CAPACITY = re.compile(r"overcrowd|capacity|\bseats?\b|annex|addition|expan|new school|extension|trailers?|"
                      r"\bTCUs?\b|portable classrooms?|enrollment", re.I)


def school_kind(ref):
    k = re.sub(r"[.\s]", "", ref).upper()
    return {"PS"} if k == "PS" else {"IS", "MS", "JHS"} if k in ("IS", "MS", "JHS") else {"PS", "IS", "MS"}


def schools(reqs):
    ecu = soda("gkd7-3vk7", f"ecu_{MONTH_TAG}", **{"$select": "data_as_of,org_id,organization_name,org_enroll,org_target_cap"})
    ecu = ecu[ecu["data_as_of"] == ecu["data_as_of"].max()].copy()
    for c in ("org_enroll", "org_target_cap"):
        ecu[c] = pd.to_numeric(ecu[c], errors="coerce").fillna(0)
    ecu["name"] = ecu["organization_name"].str.replace(r"\s+-\s+[MXKQR]$", "", regex=True)
    ecu["kind"] = ecu["name"].str.extract(r"^(P\.S\./I\.S\.|P\.S\./M\.S\.|I\.S\./P\.S\.|P\.S\.|I\.S\.|M\.S\.|J\.H\.S\.) \d+$")[0]
    ecu = ecu[ecu["kind"].notna()]
    org = ecu.groupby("org_id").agg(name=("name", "first"), kind=("kind", "first"),
                                    enroll=("org_enroll", "sum"), cap=("org_target_cap", "sum"))
    out = {}
    edu = reqs[reqs["Agency"].str.contains("Education|School Construction")]
    for r in edu.to_dict("records"):
        refs = {(int(n), ref) for ref, n in SCHOOL_REF.findall(r["text"])}
        if len({n for n, _ in refs}) != 1:
            continue
        num, ref = next(iter(refs))
        oid = f"{ECU_BORO[r['prefix']]}{num:03d}"
        if oid not in org.index:
            continue
        s = org.loc[oid]
        if not school_kind(ref) & school_kind(s["kind"]) or not s["cap"]:
            continue                              # "IS 5" in the request, but Q005 is a P.S.
        util, enroll = round(100 * s["enroll"] / s["cap"]), int(s["enroll"])
        report = "The School Construction Authority's latest Enrollment, Capacity and Utilization report"
        if util >= 100:
            out[r["Label ID"]] = (f"{report} shows {s['name']} with {count(enroll, 'student')}, {util}% of its "
                                  f"target capacity.")
        elif not CAPACITY.search(r["text"]):            # a school under capacity does not need seats
            out[r["Label ID"]] = f"{report} shows {count(enroll, 'student')} at {s['name']}."
    return out


# ---- crashes and site_311 ----------------------------------------------------------

SAFETY = re.compile(r"traffic signals?|\bsignals?\b|stop signs?|all[- ]way stop|speed (?:humps?|bumps?|cushions?|tables?|"
                    r"cameras?|reducers?|limits?)|traffic calming|calm(?:ing)? traffic|pedestrian (?:safety|islands?|"
                    r"refuges?|crossings?|plazas?)|crosswalks?|curb extensions?|bulb[- ]?outs?|neckdowns?|daylight|"
                    r"leading pedestrian|\bLPIs?\b|left[- ]turn|turn (?:arrows?|signals?|lanes?|bans?)|(?:traffic|pedestrian|street|road) "
                    r"safety|safety improvements|safer streets|accidents?|crash(?:es)?|collisions?|fatal|vision zero|"
                    r"traffic study|bike lanes?|road diet|redesign|speeding", re.I)
SITE_311 = [  # name, agencies, words in the request, 311 types, descriptors (None = all), feet around a point and
             # along a street, the fewest worth citing, what
    ("flooding", "Environmental|Transportation", r"flood|ponding|catch ?basins?|drainage|standing water",
     ["Sewer", "Sewer Maintenance"], ["Catch Basin Clogged/Flooding (Use Comments) (SC)", "Street Flooding (SJ)",
                                      "Highway Flooding (SH)", "Catch Basin Clogged", "Flooding on Street", "Flooding on Highway"],
     300, 100, 5, "reports of street flooding or clogged catch basins"),
    ("backups", "Environmental", r"back ?ups?|sewage|sewer capacity|basements?",
     ["Sewer", "Sewer Maintenance"], ["Sewer Backup (Use Comments) (SA)", "Manhole Overflow (Use Comments) (SA1)",
                                      "Backup", "Manhole Overflow"], 300, 100, 5, "reports of sewer backups or manhole overflows"),
    ("signal", "Transportation", r"(?:repair|replac|fix|upgrad|malfunction|broken)\w*\W+(?:\w+\W+){0,5}signals?|"
                                 r"signals?\W+(?:\w+\W+){0,5}(?:repair|replac|fix|upgrad|malfunction|broken)",
     ["Traffic Signal Condition"], None, 150, 60, 3, "reports of a broken or malfunctioning traffic signal"),
    ("lights", "Transportation", r"\bstreet ?lights?\b|\blamp ?posts?\b|\blighting\b|\bdark\b",
     ["Street Light Condition"], None, 150, 60, 5, "reports of street lights out or damaged"),
    ("speeding", "Transportation|Police", r"\bspeed(?:ing)?\b|speed (?:humps?|bumps?|cushions?)|traffic calming|calm traffic|drag rac",
     ["Traffic"], ["Chronic Speeding"], 300, 100, 3, "complaints about chronic speeding"),
]
NEW_SIGNAL = re.compile(r"new (?:traffic )?signal|install\w* (?:a |an )?(?:new )?(?:traffic )?(?:signal|light)|signal study|warrant", re.I)


def catchment(site, at_point, along):
    if site["kind"] == "intersection":
        return site["point"].buffer(at_point)
    return unary_union([site["line"].buffer(along)] + [p.buffer(at_point / 2) for p in site["ends"]])


def where_phrase(site, at_point):
    if site["kind"] == "intersection":
        return f"within {at_point} feet of {site['label']}"
    return f"along {site['label']}"


def crashes(reqs, sites):
    since = first_of_month(TODAY, -40).isoformat()
    cr = soda("h9gi-nx95", f"crashes_{since}", **{
        "$select": "crash_date,latitude,longitude,number_of_persons_injured,number_of_persons_killed,"
                   "number_of_pedestrians_injured,number_of_cyclist_injured",
        "$where": f"crash_date >= '{since}'"})
    cr["crash_date"] = pd.to_datetime(cr["crash_date"]).dt.date
    end = first_of_month(max(cr["crash_date"]))     # whole months only
    start = first_of_month(end, -36)
    cr = points(cr[(cr["crash_date"] >= start) & (cr["crash_date"] < end)])
    for c in ("number_of_persons_injured", "number_of_persons_killed", "number_of_pedestrians_injured", "number_of_cyclist_injured"):
        cr[c] = pd.to_numeric(cr[c], errors="coerce").fillna(0).astype(int)
    when = span(start, end)
    out = {}
    for lid, (r, site) in sites.items():
        if not (re.search("Transportation|Police", r["Agency"]) and SAFETY.search(r["main"])):
            continue
        hit = within(cr, catchment(site, 150, 60))
        n, inj, dead = len(hit), int(hit["number_of_persons_injured"].sum()), int(hit["number_of_persons_killed"].sum())
        if n < 3 or inj + dead == 0:
            continue
        where = (f"at or near {site['label']}" if site["kind"] == "intersection" else f"on {site['label']}")
        s = f"NYPD crash reports show {count(n, 'crash', 'crashes')} {where} {when}."
        ped, cyc = int(hit["number_of_pedestrians_injured"].sum()), int(hit["number_of_cyclist_injured"].sum())
        who = [x for x in (count(ped, "pedestrian") if ped else "", count(cyc, "cyclist") if cyc else "") if x]
        hurt = f"injured {count(inj, 'person', 'people')}" + (f", including {and_list(who)}" if who and inj else "")
        if dead:
            hurt = (hurt + ", and " if inj else "") + f"killed {count(dead, 'person', 'people')}"
        out[lid] = s + f" Those crashes {hurt}."
    return out


def site_311(reqs, sites):
    wins = json.load(open(os.path.join(PROJ, "plan", "planner.json")))["windows"]
    start, end = dt.date.fromisoformat(wins[0][0]), dt.date.fromisoformat(wins[-1][1])
    types = sorted({t for x in SITE_311 for t in x[3]})
    sr = soda("erm2-nwe9", f"311_sites_{start}_{end}", **{
        "$select": "created_date,complaint_type,descriptor,latitude,longitude",
        "$where": f"created_date >= '{start}' AND created_date < '{end}' AND complaint_type in ("
                  + ",".join(f"'{t}'" for t in types) + ")"})
    sr = points(sr)
    when = span(start, end)
    out = {}
    for lid, (r, site) in sites.items():
        for name, agencies, words, tps, descs, at_point, along, least, what in SITE_311:
            if not (re.search(agencies, r["Agency"]) and re.search(words, r["main"], re.I)):
                continue
            if name == "signal" and NEW_SIGNAL.search(r["text"]):
                continue                          # 311 logs broken signals, not requests for new ones
            pool = sr[sr["complaint_type"].isin(tps) & (sr["descriptor"].isin(descs) if descs else True)]
            n = len(within(pool, catchment(site, at_point, along)))
            if n >= least:
                out[lid] = f"311 received {n:,} {what} {where_phrase(site, at_point)} {when}."
                break
    return out


# ---- park_access -------------------------------------------------------------------

NEW_PARK = re.compile(r"\b(?:new|additional|more)\s+(?:public\s+)?(?:parks?|open spaces?|green spaces?|parkland)\b"
                      r"(?!\s+(?:staff|workers?|enforcement|maintenance|department|dept|personnel|programs?|officers?))|"
                      r"\b(?:create|creating|establish|establishing|build|building|develop|developing|acquire|acquiring|"
                      r"acquisition of|convert|converting)\s+(?:(?:a|an|the|this|that)\s+)?(?:new\s+)?(?:public\s+)?"
                      r"(?:parks?|open spaces?|green spaces?|parkland)\b(?!\s+(?:building|facilit))|"
                      r"lack of (?:parks?|open space|green space)|(?:park|open space)[- ](?:poor|deficient|starved)|"
                      r"underserved by parks|open space (?:deficit|shortage)", re.I)
NOT_NEW_PARK = re.compile(r"comfort stations?|bathrooms?|restrooms?|rec(?:reation)? cent|field ?house|\bpools?\b|"
                          r"building in a park", re.I)


def census_blocks():
    """2020 Census blocks in the five boroughs: population and the Census Bureau's interior
    point, from TIGERweb (the Census API now needs a key)."""
    path, have = cached("census_blocks_2020.csv")
    if not have:
        rows = []
        for county in COUNTY:
            off = 0
            while True:
                q = {"where": f"STATE='36' AND COUNTY='{county}'", "outFields": "GEOID,POP100,INTPTLAT,INTPTLON",
                     "returnGeometry": "false", "resultOffset": off, "resultRecordCount": 50000, "f": "json"}
                d = get_json(TIGERWEB + "?" + urllib.parse.urlencode(q))
                rows += [f["attributes"] for f in d["features"]]
                off += len(d["features"])
                if not d.get("exceededTransferLimit"):
                    break
        pd.DataFrame(rows).to_csv(path, index=False)
    b = pd.read_csv(path, dtype={"GEOID": str})
    return gpd.GeoDataFrame(b, geometry=gpd.points_from_xy(b["INTPTLON"], b["INTPTLAT"]), crs=4326).to_crs(2263)


def park_access(reqs):
    """Share of each district's residents beyond walking distance of a park, as NYC Parks
    measures it: 2020 Census block populations weighted by the share of each block's area
    inside the Walk to a Park service area. Citywide this gives 83.8% within walking
    distance, against the 83.9% NYC Parks reported for FY2023 with the same service area
    (Mayor's Management Report indicator 10769). A block counts toward the district that
    holds its Census interior point."""
    path, have = cached("park_access.csv")
    if not have:
        area = unary_union([make_valid(g) for g in geo("99ii-hwh9", "walk_to_a_park").geometry])
        pts = census_blocks()
        cds = geo("5crt-au7u", "community_districts")
        pts = gpd.sjoin(pts, cds[["boro_cd", "geometry"]], predicate="within", how="left")
        shapes = geo("wmsu-5muw", "census_blocks_2020", **{"$select": "geoid,the_geom"})
        b = shapes.merge(pts[["GEOID", "POP100", "boro_cd"]], left_on="geoid", right_on="GEOID")
        b["geometry"] = b.geometry.map(make_valid)
        near = (b.geometry.intersection(area).area / b.geometry.area).clip(0, 1).fillna(0)
        b["far"] = b["POP100"] * (1 - near)
        b["borocd"] = b["boro_cd"].fillna(0).astype(float).astype(int)
        t = b.groupby("borocd")[["POP100", "far"]].sum().reset_index().rename(columns={"POP100": "pop"})
        t = t[t["borocd"] > 0]
        t = pd.concat([t, pd.DataFrame([{"borocd": 0, "pop": b["POP100"].sum(), "far": b["far"].sum()}])])  # 0 is the city
        t.to_csv(path, index=False)
    t = pd.read_csv(path).set_index("borocd")
    city = t.loc[0, "far"] / t.loc[0, "pop"]
    out = {}
    for r in reqs[reqs["Agency"].str.contains("Parks") & (reqs["method"] != "park")].to_dict("records"):
        if r["borocd"] not in t.index or not NEW_PARK.search(r["main"]) or NOT_NEW_PARK.search(r["main"]):
            continue
        far, pop = t.loc[r["borocd"], "far"], t.loc[r["borocd"], "pop"]
        share = far / pop
        if share < city or far < 1000:
            continue
        out[r["Label ID"]] = (f"By NYC Parks' Walk to a Park measure, about {round(far, -2):,.0f} of our district's "
                              f"residents, or {share:.0%}, live beyond walking distance of a park. Citywide the share "
                              f"is {city:.0%}.")
    return out, city


# ---- street_trees ------------------------------------------------------------------

PLANTING = re.compile(r"plant\w*\s+(?:\w+\s+){0,3}trees?|tree[- ]planting|new (?:street )?trees|replace (?:missing|dead|"
                      r"removed) (?:street )?trees", re.I)


def street_trees(reqs):
    t = soda("82zj-84is", f"planting_spaces_empty_{MONTH_TAG}", **{
        "$select": "communityboard, count(*) as n, max(updateddate) as asof",
        "$where": "psstatus = 'Empty' AND pssite = 'Street'", "$group": "communityboard", "$order": "communityboard"})
    t = t[pd.to_numeric(t["communityboard"], errors="coerce").notna()]
    n = {int(float(b)): int(c) for b, c in zip(t["communityboard"], t["n"])}
    asof = pd.to_datetime(t["asof"]).max().date()
    out = {}
    for r in reqs[reqs["Agency"].str.contains("Parks")].to_dict("records"):
        if (r["Title"] == "Plant new street trees" or PLANTING.search(r["first"])) and n.get(r["borocd"], 0) >= 50:
            out[r["Label ID"]] = (f"As of {MONTH[asof.month - 1]} {asof.year}, NYC Parks' tree inventory listed "
                                  f"{n[r['borocd']]:,} empty street tree beds in our district.")
    return out


# ---- district_311 ------------------------------------------------------------------

# A need whose words are marked "lead" must appear in the explanation's first two
# sentences: DCP category titles such as "Forestry services, including street tree
# maintenance" cover requests that are about something else.
NEED_RULES = {  # planner need: agencies, words in the request, what 311 received
    "streets": ("Transportation", r"pot ?holes?|resurfac|repav|milling", "complaints about potholes and other street conditions"),
    "streetlights": ("Transportation", r"street ?lights?|lamp ?posts?", "complaints about street lights"),
    "sewers": ("Environmental|Transportation", r"sewers?|catch ?basins?|flood\w*|drainage|ponding", "complaints about sewers, catch basins and flooding"),
    "water": ("Environmental", r"water ?mains?|hydrants?|(?:tap|drinking) water|water pressure|discolou?red water",
              "complaints about water mains, hydrants and water quality"),
    "trees": ("Parks", r"lead:prun\w*|tree (?:removal|maintenance|care|inspection)s?|stumps?|dead (?:street )?trees?|damaged trees?|"
              r"forestry", "complaints about street trees"),
    "sidewalks": ("Transportation", r"sidewalk (?:repair|reconstruct|replace)|(?:repair|reconstruct|replace|fix)\w* (?:\w+ ){0,4}(?:sidewalks?|curbs?)|"
                                    r"pedestrian ramps?|curb cuts?", "complaints about sidewalks and curbs"),
    "sanitation": ("Sanitation", r"litter|trash|garbage|dumping|baskets?|street sweep|cleaning", "complaints about litter, dumping and missed collection"),
    "rodents": ("Health|Sanitation|Parks", r"\brats?\b|rodents?|extermina", "complaints about rats and other pests"),
    "housing": ("Housing Preservation", r"code enforcement|housing inspect|code violations|heat and hot water|hpd inspectors?",
                "complaints about heat, hot water and other apartment conditions"),
    "buildings": ("Buildings", r"building inspectors?|illegal conversions?|\bdob\b inspect|construction safety",
                  "complaints about construction and illegal building use"),
    "parking": ("Police|Transportation", r"illegal(?:ly)? park|double[- ]park|parking enforcement|traffic enforcement agents?|blocked driveways?",
                "complaints about illegal parking and blocked driveways"),
    "vehicles": ("Police|Sanitation", r"abandoned (?:vehicles?|cars?)|derelict (?:vehicles?|cars?)", "complaints about abandoned and derelict vehicles"),
    "noise": ("Police|Environmental", r"\bnoise\b", "noise complaints"),
    "homeless": ("Homeless|Human Resources|Social Services", r"homeless|encampments?|street outreach|unsheltered",
                 "requests for help for homeless people or about encampments"),
    "parks": ("Parks", r"lead:maintenance (?:workers?|staff|crews?)|park (?:workers?|staff)|city park workers?|\bCPWs?\b|"
              r"gardeners?|parks? staff|seasonal (?:workers?|staff)|staffing|(?:hire|more|additional) (?:\w+ )?(?:workers?|staff)",
              "complaints about park maintenance"),
    "graffiti": ("Sanitation|Economic Development|Police|Small Business", r"graffiti", "complaints about graffiti"),
}


def district_311(reqs):
    P = json.load(open(os.path.join(PROJ, "plan", "planner.json")))
    start, end = dt.date.fromisoformat(P["windows"][-1][0]), dt.date.fromisoformat(P["windows"][-1][1])
    when = span(start, end)
    by_borocd = {b["borocd"]: b for b in P["boards"].values()}
    out = {}
    for r in reqs.to_dict("records"):
        b = by_borocd.get(r["borocd"])
        for need, (agencies, words, what) in NEED_RULES.items():
            where = r["lead"] if words.startswith("lead:") else r["main"]
            if not (re.search(agencies, r["Agency"]) and re.search(words.removeprefix("lead:"), where, re.I)):
                continue
            x = b["needs"].get(need) if b else None
            if not x:
                break
            c = x["counts"]
            s = f"311 received {c[-1]:,} {what} in our district {when}."
            if x["rank"] <= 15:
                s += f" That is {highest(x['rank'])} rate per resident among the city's 59 community districts."
            elif x["countRank"] <= 15:
                s += f" That is {highest(x['countRank'])} number among the city's 59 community districts."
            elif not (c[0] and c[-1] >= 1.25 * c[0] and c[-1] - c[0] >= 50):
                break
            if c[0] and c[-1] >= 1.25 * c[0] and c[-1] - c[0] >= 50:
                s += f" Two years earlier the number was {c[0]:,}."
            out[r["Label ID"]] = s
            break
    return out


# ---- all together ------------------------------------------------------------------

SOURCES = {
    "park_inspection": ("NYC Parks, Parks Inspection Program", "yg3y-7juh"),
    "school": ("School Construction Authority, Enrollment, Capacity and Utilization", "gkd7-3vk7"),
    "crashes": ("NYPD, Motor Vehicle Collisions", "h9gi-nx95"),
    "site_311": ("311 Service Requests", "erm2-nwe9"),
    "park_access": ("NYC Parks, Walk to a Park Service Area, with 2020 Census blocks", "99ii-hwh9"),
    "street_trees": ("NYC Parks, Forestry Planting Spaces", "82zj-84is"),
    "district_311": ("311 Service Requests, as counted for the planner", "erm2-nwe9"),
}


def main():
    os.makedirs(CACHE, exist_ok=True)
    reqs = load_requests()
    print(f"{len(reqs)} requests")
    sites, finder = {}, Sites()
    for r in reqs[reqs["Explanation"].str.match(r"\s*Location:") | (reqs["Location"].str.strip() != "")].to_dict("records"):
        s = finder.locate(r)
        if s:
            sites[r["Label ID"]] = (r, s)
    finder.streets.save()
    print(f"{len(sites)} sites from Location lines "
          f"({sum(s['kind'] == 'intersection' for _, s in sites.values())} intersections)")
    facts = {}
    access, city = park_access(reqs)
    print(f"Walk to a Park: {city:.1%} of New Yorkers live beyond walking distance of a park")
    for kind, found in [("park_inspection", park_inspections(reqs)), ("school", schools(reqs)),
                        ("crashes", crashes(reqs, sites)), ("site_311", site_311(reqs, sites)),
                        ("park_access", access), ("street_trees", street_trees(reqs)),
                        ("district_311", district_311(reqs))]:
        print(f"  {kind:16} {len(found):5}")
        for lid, text in found.items():
            facts.setdefault(lid, []).append((kind, text))
    rows = []
    for lid, fs in facts.items():
        for kind, text in sorted(fs, key=lambda f: ORDER.index(f[0]))[:2]:
            src, ds = SOURCES[kind]
            rows.append({"label_id": lid, "kind": kind, "text": text, "source": src, "url": DATASET.format(ds)})
    out = pd.DataFrame(rows, columns=["label_id", "kind", "text", "source", "url"]).sort_values(["label_id", "kind"])
    out.to_csv(OUT, index=False)
    print(f"wrote {len(out)} facts for {out['label_id'].nunique()} requests -> {os.path.relpath(OUT, PROJ)}")


if __name__ == "__main__":
    main()
