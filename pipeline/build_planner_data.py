"""Build plan/planner.json, the data behind the next-cycle planner.

For each of the 59 boards it joins three sources on the board code (QCB2):

  - district conditions: 311 service requests per 1,000 residents for a hand-picked
    set of needs, over the last three 12-month windows, ranked among the 59 boards
  - the district profile: ACS 2020-2024 and other indicators from nyc-cd-atlas
  - the board's own requests: which Register requests (FY2020-FY2027 agency rounds)
    address each need

and adds, for every DCP request category, how agencies have answered it across all
boards and years ("what works").

    python3 build_planner_data.py [--data DIR] [--out PATH] [--refresh]

Downloads are cached in the data directory (default ~/Downloads, like update.sh);
--refresh downloads them again. Standard library only.
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from shared import BORO_ABBR, PUBLICATIONS, REG_BORO_ABBR, REGISTER_AGENCY_NAMES, stance

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
arg = lambda flag, default: sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default
DATA = os.path.expanduser(arg("--data", "~/Downloads"))
OUT = arg("--out", os.path.join(PROJ, "plan", "planner.json"))
REFRESH = "--refresh" in sys.argv

REGISTER_URL = "https://data.cityofnewyork.us/resource/vn4m-mk4t.csv"
SR311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
ATLAS_URL = "https://raw.githubusercontent.com/francisryansantos/nyc-cd-atlas/main/explorer/data/cd_profiles.json"
BORO_311 = {"MANHATTAN": "1", "BRONX": "2", "BROOKLYN": "3", "QUEENS": "4", "STATEN ISLAND": "5"}

# Each need pairs the 311 complaint types that measure it with the requests that
# address it. A request addresses a need when its DCP category is listed or its
# explanation matches the pattern. 311 renamed some types in 2025 ("Sewer" became
# "Sewer Maintenance", "Water System" became "Water Maintenance"), so both are listed.
# DCP renamed some categories after FY2025, so old names are listed too.
# This mapping is a judgment call: review it with a board member.
NEEDS = [
    {"id": "streets", "label": "Potholes and street condition",
     "types": ["Street Condition", "Highway Condition"],
     "categories": ["Reconstruct streets", "Roadway maintenance (resurfacing, trench restoration, etc.)",
                    "Roadway maintenance (i.e. pothole repair, resurfacing, trench restoration, etc.)"],
     "pattern": r"pot ?holes?|resurfac|repav|milling"},
    {"id": "signals", "label": "Traffic signals",
     "types": ["Traffic Signal Condition"],
     "categories": ["Provide new traffic or pedestrian signals"],
     "pattern": r"\bsignals?\b|traffic lights?"},
    {"id": "streetlights", "label": "Street lights",
     "types": ["Street Light Condition"],
     "categories": ["Repair or provide new street lights"],
     "pattern": r"street ?lights?|lamp ?posts?"},
    {"id": "sewers", "label": "Sewers, catch basins and flooding",
     "types": ["Sewer", "Sewer Maintenance", "Standing Water", "Green Infrastructure"],
     "categories": ["Clean catch basins",
                    "Develop a capital project for specific street segments currently lacking sanitary sewers",
                    "Inspect sanitary sewer on specific street segment and repair or replace as needed",
                    "Inspect sanitary sewer on specific street segment and repair or replace as needed (Capital)",
                    "Inspect storm sewer on specific street segment and service, repair or replace as needed",
                    "Evaluate a public location or property for green infrastructure, e.g. rain gardens, stormwater greenstreets, green playgrounds",
                    "Evaluate a street segment or intersection for green infrastructure, e.g. rain gardens, stormwater greenstreets, and plan for construction if feasible",
                    "Other capital budget request for DEP"],
     "pattern": r"sewers?|catch ?basins?|flood|drainage|stormwater|ponding"},
    {"id": "water", "label": "Water mains and hydrants",
     "types": ["Water System", "Water Maintenance", "Water Quality"],
     "categories": ["Inspect water main on specific street segment and repair or replace as needed",
                    "Inspect fire hydrant at a specific location and repair or replace as needed",
                    "Investigate and address water quality complaints at an address or on specific street segments"],
     "pattern": r"water ?mains?|hydrants?|water quality"},
    {"id": "trees", "label": "Street trees",
     "types": ["Damaged Tree", "Overgrown Tree/Branches", "Dead/Dying Tree", "New Tree Request",
               "Root/Sewer/Sidewalk Condition", "Illegal Tree Damage"],
     "categories": ["Forestry services, including street tree maintenance", "Plant new street trees",
                    "Other street trees and forestry services requests"],
     "pattern": r"\btrees?\b|forestry|pruning"},
    {"id": "sidewalks", "label": "Sidewalks and curbs",
     "types": ["Sidewalk Condition", "Curb Condition"],
     "categories": ["Repair or construct sidewalks, curbs, or pedestrian ramps",
                    "Repair or construct new curbs or pedestrian ramps"],
     "pattern": r"sidewalk (?:repair|reconstruct|replace)|(?:repair|reconstruct|replace|fix)\w* (?:\w+ ){0,4}(?:sidewalks?|curbs?)|pedestrian ramps?|curb cuts?"},
    {"id": "sanitation", "label": "Litter, dumping and missed collection",
     "types": ["Dirty Condition", "Illegal Dumping", "Missed Collection", "Litter Basket Complaint",
               "Litter Basket Request", "Residential Disposal Complaint", "Commercial Disposal Complaint",
               "Lot Condition", "Street Sweeping Complaint"],
     "categories": ["Other cleaning requests", "Provide more frequent litter basket collection",
                    "Provide more on-street trash cans and recycling containers",
                    "Improve trash removal and cleanliness", "Increase enforcement of illegal dumping laws",
                    "Increase enforcement of dirty sidewalk/dirty area/failure to clean area laws",
                    "Provide new or increase number of sanitation trucks and other equipment",
                    "Increase vacant lot cleaning", "Increase cleaning of dump-out/drop-off locations"],
     "pattern": r"litter|trash|garbage|dumping|sanitation|basket|street sweep"},
    {"id": "rodents", "label": "Rats and pests",
     "types": ["Rodent", "Mosquitoes", "Unsanitary Pigeon Condition"],
     "categories": ["Animal and pest control requests including reducing rat and mosquito populations",
                    "Reduce rat populations", "Other animal and pest control requests"],
     "pattern": r"\brats?\b|rodents?|\bpests?\b|mosquito|extermina"},
    {"id": "housing", "label": "Heat and apartment conditions",
     "types": ["HEAT/HOT WATER", "UNSANITARY CONDITION", "PAINT/PLASTER", "PLUMBING", "WATER LEAK",
               "DOOR/WINDOW", "ELECTRIC", "FLOORING/STAIRS", "GENERAL", "APPLIANCE", "SAFETY"],
     "categories": ["Provide, expand, or enhance programs for housing inspections to correct code violations",
                    "Expand programs for housing inspections to correct code violations",
                    "Expand code enforcement", "Other housing oversight and emergency housing programs"],
     "pattern": r"code enforcement|housing inspect|code violations|heat and hot water|hpd inspectors?"},
    {"id": "buildings", "label": "Construction and illegal building use",
     "types": ["General Construction/Plumbing", "Building/Use", "Special Projects Inspection Team (SPIT)"],
     "categories": ["Assign additional building inspectors (including expanding training programs)"],
     "pattern": r"building inspectors?|illegal conversions?|\bdob\b inspect|construction safety"},
    {"id": "parking", "label": "Illegal parking and blocked driveways",
     "types": ["Illegal Parking", "Blocked Driveway"],
     "categories": ["Hire additional traffic enforcement agents", "Improve parking operations",
                    "Conduct traffic or parking studies"],
     "pattern": r"illegal(?:ly)? park|double[- ]park|parking enforcement|traffic enforcement agents?|blocked driveways?"},
    {"id": "vehicles", "label": "Abandoned and derelict vehicles",
     "types": ["Abandoned Vehicle", "Derelict Vehicles"],
     "categories": [],
     "pattern": r"abandoned (?:vehicles?|cars?)|derelict (?:vehicles?|cars?)"},
    {"id": "noise", "label": "Noise",
     "types": ["Noise - Residential", "Noise - Street/Sidewalk", "Noise - Commercial", "Noise - Vehicle",
               "Noise", "Noise - Park", "Noise - Helicopter"],
     "categories": ["Investigate noise complaints at specific location"],
     "pattern": r"\bnoise\b"},
    {"id": "homeless", "label": "Homelessness and encampments",
     "types": ["Homeless Person Assistance", "Encampment"],
     "categories": ["Expand street outreach", "Provide, expand, or enhance street outreach services",
                    "Other request for services for the homeless", "Other facilities for the homeless requests"],
     "pattern": r"homeless|encampments?|street outreach|drop-in cent"},
    {"id": "parks", "label": "Park maintenance",
     "types": ["Maintenance or Facility"],
     "categories": ["Other park maintenance and safety requests", "Provide better park maintenance"],
     "pattern": r"park maintenance|comfort stations?|park (?:staff|workers)"},
    {"id": "graffiti", "label": "Graffiti",
     "types": ["Graffiti"],
     "categories": ["Increase Graffiti Removal/Cleaning",
                    "Expand clean space initiatives for public sites and graffiti free removal program for private sites along commercial business corridors"],
     "pattern": r"graffiti"},
]
for n in NEEDS:
    n["regex"] = re.compile(n["pattern"], re.I)

# District profile indicators from nyc-cd-atlas: key -> (label, unit, source, margin-of-error key)
INDICATORS = {
    "pop_acs": ("Population", "people", "ACS 2020-2024", None),
    "mdn_hh_inc_interp": ("Median household income", "$", "ACS 2020-2024", None),
    "poverty_rate": ("Below the poverty line", "%", "ACS 2020-2024", "moe_poverty_rate"),
    "pct_hh_rent_burd": ("Renters paying 30%+ of income on rent", "%", "ACS 2020-2024", "moe_hh_rent_burd"),
    "unemployment": ("Unemployment", "%", "ACS 2020-2024", "moe_unemployment"),
    "lep_rate": ("Limited English proficiency", "%", "ACS 2020-2024", "moe_lep_rate"),
    "pct_foreign_born": ("Foreign-born", "%", "ACS 2020-2024", "moe_foreign_born"),
    "under18_rate": ("Under 18", "%", "ACS 2020-2024", None),
    "over65_rate": ("65 and over", "%", "ACS 2020-2024", None),
    "pct_bach_deg": ("Bachelor's degree or higher", "%", "ACS 2020-2024", "moe_bach_deg"),
    "crime_per_1000": ("Major felonies per 1,000 residents", "per 1,000", "NYPD 2024", None),
    "count_parks": ("Parks", "count", "NYC Parks Properties, Mar 2026", None),
}

# First sentences that send the board somewhere other than the City's budget.
REDIRECT = re.compile(r"transit authority|\bmta\b|responsibility of the (?:adjacent )?property owner|"
                      r"not (?:a|an) (?:capital|expense|budget) (?:budget )?request|state (?:agency|jurisdiction)|"
                      r"should be (?:directed|referred) to|borough commissioner|contact the transit|\b311\b", re.I)
FUNDED = re.compile(r"already (?:been )?funded|has been completed|will be (?:completed|finished)|"
                    r"funding is in place|included in the", re.I)


def first_sentence(t):
    t = " ".join((t or "").split())
    t = re.sub(r"^OMB supports the agency's position as follows:\s*", "", t)
    return re.split(r"(?<=[.!?])\s", t)[0]


def fetch(url, dest, timeout=600):
    """Download url to dest in the data directory, unless it is already there."""
    path = os.path.join(DATA, dest)
    if REFRESH or not os.path.exists(path):
        sys.stderr.write(f"  downloading {dest}\n")
        with urllib.request.urlopen(url, timeout=timeout) as r, open(path + ".part", "wb") as f:
            f.write(r.read())
        os.replace(path + ".part", path)
    return path


def windows(today):
    """The last three 12-month windows ending at the start of this month, newest last."""
    end = dt.date(today.year, today.month, 1)
    return [(dt.date(end.year - k - 1, end.month, 1), dt.date(end.year - k, end.month, 1)) for k in (2, 1, 0)]


def fetch_311(need, start, end):
    types = ",".join("'" + t.replace("'", "''") + "'" for t in need["types"])
    q = {"$select": "community_board, count(*) as n",
         "$where": f"created_date >= '{start}' AND created_date < '{end}' AND complaint_type in ({types})",
         "$group": "community_board", "$limit": "1000"}
    path = fetch(SR311_URL + "?" + urllib.parse.urlencode(q), f"311_{need['id']}_{start}_{end}.json")
    counts = {}
    for row in json.load(open(path)):
        m = re.match(r"(\d\d) (.+)$", row.get("community_board", ""))
        if m and m.group(2) in BORO_311:
            counts[f"{BORO_ABBR[BORO_311[m.group(2)]]}CB{int(m.group(1))}"] = int(row["n"])
    return counts


def rank_desc(values):
    """Rank 1 = highest value. Ties share a rank."""
    order = sorted(values.values(), reverse=True)
    return {k: order.index(v) + 1 for k, v in values.items()}


def main():
    os.makedirs(DATA, exist_ok=True)
    wins = windows(dt.date.today())

    # --- district profiles -------------------------------------------------------
    atlas = json.load(open(fetch(ATLAS_URL, "nyc_cd_atlas_profiles.json")))
    boards = {}
    for p in atlas["profiles"]:
        bc = str(p["borocd"])
        code = f"{BORO_ABBR[bc[0]]}CB{int(bc[1:])}"
        boards[code] = {"code": code, "borocd": p["borocd"], "borough": p["borough"], "name": p["name"],
                        "neighborhoods": p["neighborhoods"],
                        "statementIssues": [p[k] for k in ("son_issue_1", "son_issue_2", "son_issue_3") if p.get(k)],
                        "sharedPuma": p.get("puma_partner") if p.get("shared_puma") else None,
                        "profile": {}, "needs": {}}
    pop = {c: float(p["pop_acs"]) for c, p in zip(boards, atlas["profiles"])}
    for key, (label, unit, source, moe) in INDICATORS.items():
        vals = {c: p[key] for c, p in zip(boards, atlas["profiles"]) if p.get(key) is not None}
        ranks = rank_desc(vals)
        for c, p in zip(boards, atlas["profiles"]):
            if c in vals:
                boards[c]["profile"][key] = {"value": vals[c], "rank": ranks[c],
                                             "moe": p.get(moe) if moe else None}
    medians = {k: v for k, v in atlas["medians"].items() if k in INDICATORS}

    # --- 311 conditions ----------------------------------------------------------
    jobs = [(n, s, e) for n in NEEDS for s, e in wins]
    with ThreadPoolExecutor(8) as ex:
        results = dict(zip([(n["id"], s) for n, s, _ in jobs], ex.map(lambda j: fetch_311(*j), jobs)))
    citywide = {}
    for n in NEEDS:
        series = {c: [results[(n["id"], s)].get(c, 0) for s, _ in wins] for c in boards}
        rate = {c: round(series[c][-1] / pop[c] * 1000, 2) for c in boards}
        ranks = rank_desc(rate)
        # Per-resident rates overstate districts with few residents and many workers or
        # visitors (Midtown ranks first on most needs), so the raw count is ranked too.
        count_ranks = rank_desc({c: series[c][-1] for c in boards})
        med = sorted(rate.values())[len(rate) // 2]
        citywide[n["id"]] = {"medianRate": med, "total": sum(s[-1] for s in series.values())}
        for c in boards:
            boards[c]["needs"][n["id"]] = {"counts": series[c], "rate": rate[c], "rank": ranks[c], "countRank": count_ranks[c],
                                           "vsMedian": round(rate[c] / med, 2) if med else None,
                                           "requests": [], "yearsRequested": [], "yearsMentioned": []}

    # --- the Register ------------------------------------------------------------
    reg_path = fetch(REGISTER_URL + "?" + urllib.parse.urlencode({"$limit": "1000000"}),
                     "Register_all_publications.csv")
    agency_round = {pub: fy for fy, (pub, _) in PUBLICATIONS.items()}
    omb_round = {pub: fy for fy, (_, pub) in PUBLICATIONS.items()}
    omb = {}
    rows = []
    for r in csv.DictReader(open(reg_path, encoding="utf-8")):
        code = f"{REG_BORO_ABBR.get(r['boro'], '?')}CB{int(r['board'])}" if r["board"].isdigit() else None
        if code not in boards:
            continue
        if r["publication"] in omb_round:
            omb[(omb_round[r["publication"]], r["tracking_code"])] = r["response"]
        elif r["publication"] in agency_round:
            rows.append((agency_round[r["publication"]], code, r))

    cats = defaultdict(lambda: {"n": 0, "stance": Counter(), "redirect": 0, "funded": 0,
                                "responses": Counter(), "agencies": Counter(), "fys": Counter(), "examples": []})
    latest = max(PUBLICATIONS)
    board_requests = Counter()
    board_categories = defaultdict(Counter)
    for fy, code, r in rows:
        agency = REGISTER_AGENCY_NAMES.get(r["responsible_agency"], r["responsible_agency"])
        st = stance(r["response"])
        first = first_sentence(r["response"])
        omb_resp = omb.get((fy, r["tracking_code"]), "")
        cap = "Capital" if r["tracking_code"].endswith("C") else "Expense"

        c = cats[r["request"]]
        c["n"] += 1
        c["stance"][st] += 1
        c["redirect"] += bool(REDIRECT.search(first))
        c["funded"] += bool(FUNDED.search(first_sentence(omb_resp)))
        c["responses"][first] += 1
        c["agencies"][agency] += 1
        c["fys"][fy] += 1
        c["type"] = cap
        if st == "Support" and 150 <= len(r["explanation"] or "") <= 700:
            c["examples"].append({"board": code, "fy": fy, "explanation": r["explanation"],
                                  "response": first})

        if fy == latest:
            board_requests[code] += 1
            board_categories[code][r["request"]] += 1
        text = f"{r['request']} {r['explanation']}"
        for n in NEEDS:
            if r["request"] in n["categories"] or n["regex"].search(text):
                need = boards[code]["needs"][n["id"]]
                direct = r["request"] in n["categories"]
                years = need["yearsRequested" if direct else "yearsMentioned"]
                if fy not in years:
                    years.append(fy)
                if fy == latest:
                    need["requests"].append({
                        "trackingCode": r["tracking_code"], "priority": r["priority"], "type": cap,
                        "category": r["request"], "agency": agency,
                        "explanation": (r["explanation"] or "")[:300], "stance": st,
                        "response": first, "matchedBy": "category" if direct else "keyword"})

    for code, b in boards.items():
        b["requestCount"] = board_requests[code]
        b["categories"] = dict(board_categories[code].most_common())
        for need in b["needs"].values():
            need["yearsRequested"].sort()
            need["yearsMentioned"] = sorted(set(need["yearsMentioned"]) - set(need["yearsRequested"]))

    categories = {}
    for name, c in cats.items():
        categories[name] = {
            "n": c["n"], "type": c["type"],
            "support": round(c["stance"]["Support"] / c["n"], 3),
            "oppose": round(c["stance"]["Oppose"] / c["n"], 3),
            "redirect": round(c["redirect"] / c["n"], 3),
            "funded": round(c["funded"] / c["n"], 3),
            "agency": c["agencies"].most_common(1)[0][0],
            "topResponses": c["responses"].most_common(3),
            "byYear": dict(sorted(c["fys"].items())),
            # the two most recent supported requests, as models of wording
            "examples": sorted(c["examples"], key=lambda e: e["fy"], reverse=True)[:2] if c["n"] >= 20 else [],
        }

    out = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "latestFy": latest,
        "windows": [[str(s), str(e)] for s, e in wins],
        "sources": {
            "311": {"name": "311 Service Requests from 2010 to Present", "url": "https://data.cityofnewyork.us/d/erm2-nwe9"},
            "register": {"name": "Register of Community Board Budget Requests", "url": "https://data.cityofnewyork.us/d/vn4m-mk4t"},
            "profile": {"name": "nyc-cd-atlas (updated DCP Community District Profiles)", "url": "https://github.com/francisryansantos/nyc-cd-atlas"},
        },
        "needs": [{k: n[k] for k in ("id", "label", "types", "categories", "pattern")} | citywide[n["id"]] for n in NEEDS],
        "indicators": {k: {"label": l, "unit": u, "source": s, "median": medians.get(k)}
                       for k, (l, u, s, _) in INDICATORS.items()},
        "categories": categories,
        "boards": boards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    sys.stderr.write(f"Wrote {OUT} ({os.path.getsize(OUT) // 1024} KB): {len(boards)} boards, "
                     f"{len(NEEDS)} needs, {len(categories)} categories, {len(rows)} agency-round requests\n")


if __name__ == "__main__":
    main()
