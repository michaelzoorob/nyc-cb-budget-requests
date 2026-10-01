#!/usr/bin/env python3
"""Build the site's home page (index.html at the repo root): a zoomable Leaflet map of NYC's 59 community districts
(plus the 12 non-board park/airport/cemetery areas DCP includes in the same
shapefile) overlaid on OpenStreetMap tiles, in the style of boundaries.beta.nyc.

Source: NYC Open Data, "Community Districts" (5crt-au7u), fetched live from the
Socrata GeoJSON endpoint each time this script runs (not committed as raw data,
same pattern as pipeline/ for the CSV builds).

Unlike the rest of this site, this page is not fully self-contained: it loads
Leaflet from a CDN and OpenStreetMap tile images over the network at view time,
since an offline basemap isn't practical to embed. The district boundaries
themselves are still embedded inline (no backend, no data fetch for those).

    python3 build_map.py [OUT]   # OUT defaults to the repo root's index.html
"""
import json
import math
import os
import sys
import urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
SRC_URL = "https://data.cityofnewyork.us/resource/5crt-au7u.geojson?$limit=100"
SIMPLIFY_EPS = 0.00005          # degrees; ~97k input points -> ~17k after simplifying

LEAFLET_VERSION = "1.9.4"
LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="

BORO = {"1": ("M", "Manhattan"), "2": ("BX", "Bronx"), "3": ("BK", "Brooklyn"),
        "4": ("Q", "Queens"), "5": ("SI", "Staten Island")}
BORO_COLOR = {"M": "#3b82f6", "BX": "#ef4444", "BK": "#f59e0b", "Q": "#22c55e", "SI": "#8b5cf6"}
# The shapefile carries 12 non-community-board areas (parks, airports, a cemetery)
# alongside the 59 real districts. Identified here by matching each area's computed
# centroid and acreage against the well-known NYC landmarks at that location.
SPECIAL_NAMES = {
    "164": "Central Park", "226": "Van Cortlandt Park", "227": "Bronx Park",
    "228": "Pelham Bay Park", "355": "Prospect Park",
    "356": "Jamaica Bay / Floyd Bennett Field", "480": "LaGuardia Airport",
    "481": "Flushing Meadows Corona Park", "482": "Forest Park",
    "483": "John F. Kennedy International Airport", "484": "Jamaica Bay (Queens)",
    "595": "Parkland / federal land",
}


def fetch():
    with urllib.request.urlopen(SRC_URL) as r:
        return json.load(r)


def dp_simplify(points, eps):
    """Douglas-Peucker, iterative stack version to avoid recursion limits on long rings."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        x1, y1 = points[start]
        x2, y2 = points[end]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        maxd, idx = -1.0, -1
        for i in range(start + 1, end):
            x0, y0 = points[i]
            d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm if norm else math.hypot(x0 - x1, y0 - y1)
            if d > maxd:
                maxd, idx = d, i
        if maxd > eps:
            keep[idx] = True
            stack.append((start, idx))
            stack.append((idx, end))
    return [p for p, k in zip(points, keep) if k]


def main():
    print("fetching", SRC_URL, file=sys.stderr)
    data = fetch()
    feats = data["features"]
    assert len(feats) == 71, f"expected 71 community-district areas, got {len(feats)}"

    out_features = []
    minlon = minlat = 1e9
    maxlon = maxlat = -1e9
    for f in feats:
        code = f["properties"]["boro_cd"]
        boro_num = code[0]
        cd_num = int(code[1:])
        boro_abbr, boro_full = BORO[boro_num]
        is_special = code in SPECIAL_NAMES
        if is_special:
            label = f"{boro_full} – {SPECIAL_NAMES[code]}"
            board_id = ""
        else:
            label = f"{boro_full} Community District {cd_num}"
            board_id = f"{boro_abbr}CB{cd_num}"

        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        simp_polys = []
        for poly in polys:
            simp_poly = []
            for ring in poly:
                s = dp_simplify(ring, SIMPLIFY_EPS)
                simp_poly.append([[round(x, 6), round(y, 6)] for x, y in s])
                for x, y in s:
                    minlon, maxlon = min(minlon, x), max(maxlon, x)
                    minlat, maxlat = min(minlat, y), max(maxlat, y)
            simp_polys.append(simp_poly)

        out_features.append({
            "type": "Feature",
            "properties": {
                "label": label, "boro": boro_abbr, "special": is_special, "board": board_id,
            },
            "geometry": {"type": "MultiPolygon", "coordinates": simp_polys},
        })

    fc = {"type": "FeatureCollection", "features": out_features}
    bounds = [[minlat, minlon], [maxlat, maxlon]]   # Leaflet order: [lat, lon]

    html = (TEMPLATE
            .replace("__DATA__", json.dumps(fc, separators=(",", ":")))
            .replace("__BOUNDS__", json.dumps(bounds))
            .replace("__BORO_COLOR__", json.dumps(BORO_COLOR))
            .replace("__LEAFLET_VERSION__", LEAFLET_VERSION)
            .replace("__LEAFLET_JS_SRI__", LEAFLET_JS_SRI)
            .replace("__LEAFLET_CSS_SRI__", LEAFLET_CSS_SRI))
    with open(OUT, "w") as f:
        f.write(html)
    print(f"wrote {OUT} ({len(html)/1024:.0f} KB, {len(out_features)} areas)", file=sys.stderr)


TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><link rel="icon" href="data:,">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>/* The dashboard used to live at "/". Its links (?board=, ?year=, ...) now go to /dashboard/. */
(function(){var s=location.search;if(/[?&](board|xboard|year|q|committee|sort|fu|c_[a-z0-9]+)=/.test(s))location.replace("/dashboard/"+s+location.hash);})();</script>
<title>NYC Community Board Budget Requests</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@__LEAFLET_VERSION__/dist/leaflet.css"
  integrity="__LEAFLET_CSS_SRI__" crossorigin=""/>
<style>
:root{--bd:#e2e8f0;--mut:#64748b;--ink:#0f172a;}
*{box-sizing:border-box}
html,body{height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  margin:0;color:var(--ink);background:#f8fafc;display:flex;flex-direction:column}
header{padding:16px 24px 12px;background:#fff;border-bottom:1px solid var(--bd);flex:0 0 auto}
h1{margin:0 0 4px;font-size:19px}
.sub{color:var(--mut);margin:0;font-size:13px;max-width:900px}
main{position:relative;flex:1 1 auto;min-height:0}
#map{width:100%;height:100%;background:#eaf2fb}
.legend{position:absolute;left:16px;bottom:16px;background:rgba(255,255,255,.92);border:1px solid var(--bd);
  border-radius:8px;padding:8px 10px;font-size:11.5px;color:var(--ink);box-shadow:0 1px 3px rgba(15,23,42,.1);z-index:1000}
.legend .row{display:flex;align-items:center;gap:6px;margin:2px 0}
.legend .sw{width:11px;height:11px;border-radius:3px;display:inline-block;flex:0 0 auto}
.leaflet-tooltip.cd-tip{font-size:12.5px;padding:4px 8px}
.district-special{cursor:default!important}
</style>
</head>
<body>
<header>
<h1>NYC Community Board Budget Requests</h1>
<p class="sub">Pan and zoom the map, then click a community district to see its budget requests. Or see <a href="/summary/">how the City answered them, by agency and board</a>.</p>
</header>
<main>
<div id="map"></div>
<div class="legend">
<div class="row"><span class="sw" style="background:__M_COLOR__"></span>Manhattan</div>
<div class="row"><span class="sw" style="background:__BX_COLOR__"></span>Bronx</div>
<div class="row"><span class="sw" style="background:__BK_COLOR__"></span>Brooklyn</div>
<div class="row"><span class="sw" style="background:__Q_COLOR__"></span>Queens</div>
<div class="row"><span class="sw" style="background:__SI_COLOR__"></span>Staten Island</div>
<div class="row"><span class="sw" style="background:#94a3b8"></span>Park / airport / no board</div>
</div>
</main>
<script src="https://unpkg.com/leaflet@__LEAFLET_VERSION__/dist/leaflet.js"
  integrity="__LEAFLET_JS_SRI__" crossorigin=""></script>
<script>
(function(){
var BORO_COLOR = __BORO_COLOR__;
var DISTRICTS = __DATA__;
var BOUNDS = __BOUNDS__;

var map = L.map("map", {scrollWheelZoom: true});
// Open one zoom level closer than the level that fits the whole city.
var CITY = L.latLngBounds(BOUNDS);
map.setView(CITY.getCenter(), map.getBoundsZoom(CITY, false, L.point(24, 24)) + 1);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  opacity: 0.5,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

function styleFor(feature){
  var p = feature.properties;
  if(p.special){
    return {color: "#64748b", weight: 1, fillColor: "#94a3b8", fillOpacity: 0.35, className: "district-special"};
  }
  return {color: "#fff", weight: 1.5, fillColor: BORO_COLOR[p.boro] || "#94a3b8", fillOpacity: 0.45};
}

var layer = L.geoJSON(DISTRICTS, {
  style: styleFor,
  onEachFeature: function(feature, lyr){
    var p = feature.properties;
    lyr.bindTooltip(p.board ? p.label + " → view requests" : p.label,
      {sticky: true, className: "cd-tip"});
    lyr.on("mouseover", function(){
      if(!p.special) lyr.setStyle({fillOpacity: 0.7, weight: 2.5});
    });
    lyr.on("mouseout", function(){ layer.resetStyle(lyr); });
    if(p.board){
      lyr.on("click", function(){
        window.location.href = "/dashboard/?board=" + encodeURIComponent(p.board);
      });
    }
  }
}).addTo(map);
})();
</script>
</body></html>
"""

for _b, _c in BORO_COLOR.items():
    TEMPLATE = TEMPLATE.replace(f"__{_b}_COLOR__", _c)

if __name__ == "__main__":
    main()
