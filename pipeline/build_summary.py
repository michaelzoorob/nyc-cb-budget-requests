#!/usr/bin/env python3
"""Build summary/index.html: how agencies answered community board budget requests,
by agency and by board, for every fiscal year.

    build_summary.py [DATA_DIR] [OUT]

DATA_DIR holds the per-year "CB FY<YEAR> Requests (all boards, detailed, 2-stage).csv"
files (default ~/Downloads). OUT defaults to summary/index.html in the repo.

FY2026 and later responses open with one of DCP's six standard answers ("Agency supports
but cannot accommodate" and so on), which the page splits out. Earlier years have no such
answers, so the page uses the dashboard's Agency Stance column (support, oppose, neutral or
unclear). Like the dashboard pages, the page is one self-contained HTML file.
"""
import json
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shared import YEARS, LATEST  # noqa: E402

DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Downloads")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "summary", "index.html")
YEAR_URL = {y: ("/dashboard/" if y == LATEST else f"/fy{y}/") for y in YEARS}

# DCP's six answers, in the order the page stacks them (the first sentence of a response).
SIX = [("can", r"^agency supports and can accommodate"), ("cannot", r"^agency supports but cannot accommodate"),
       ("completed", r"^this request has already been completed"),
       ("alternative", r"^agency does not support but can address"),
       ("unclear", r"^the agency does not understand"), ("oppose", r"^agency does not support")]
STANCE = {"Support": "support", "Oppose": "oppose", "Neutral/Unclear": "neutral"}
BORO = {"M": "Manhattan", "BX": "Bronx", "BK": "Brooklyn", "Q": "Queens", "SI": "Staten Island"}


def answer(text):
    t = " ".join(str(text).split()).lower()
    if not t:
        return "none"
    for key, rx in SIX:
        if re.match(rx, t):
            return key
    return "other"


def board_parts(code):
    m = re.match(r"^(BX|BK|SI|M|Q)CB(\d+)$", code)
    return (m.group(1), int(m.group(2))) if m else ("", 0)


def year_data(fy):
    path = os.path.join(DATA, f"CB FY{fy} Requests (all boards, detailed, 2-stage).csv")
    d = pd.read_csv(path, dtype=str).fillna("")
    six = fy >= "2026"
    d["k"] = d["Agency Response"].map(answer) if six else d["Agency Stance (MZ added)"].map(lambda s: STANCE.get(s, "neutral"))

    def counts(g):
        return {k: int(v) for k, v in g["k"].value_counts().items()}
    agencies = sorted(([a, len(g), counts(g)] for a, g in d.groupby("Agency") if a), key=lambda r: -r[1])
    boards = []
    for b, g in d.groupby("Board"):
        boro, num = board_parts(b)
        boards.append([b, f"{BORO.get(boro, boro)} CB{num}" if boro else b, boro, num, len(g), counts(g)])
    boards.sort(key=lambda r: (list(BORO).index(r[2]) if r[2] in BORO else 9, r[3]))
    by_board = {b: sorted(([a, len(ga), counts(ga)] for a, ga in g.groupby("Agency") if a), key=lambda r: -r[1])
                for b, g in d.groupby("Board")}
    return {"mode": "six" if six else "three", "n": len(d), "total": counts(d), "agencies": agencies,
            "boards": [r[:3] + r[4:] for r in boards], "byBoard": by_board}


DATA_JS = {"years": YEARS, "latest": LATEST, "yearUrl": YEAR_URL,
           "data": {fy: year_data(fy) for fy in YEARS
                    if os.path.exists(os.path.join(DATA, f"CB FY{fy} Requests (all boards, detailed, 2-stage).csv"))}}

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><link rel="icon" href="data:,">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How the City answered community board budget requests</title>
<style>
:root{--bd:#e2e8f0;--mut:#64748b;--ink:#0f172a;--acc:#2563eb}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;margin:0;color:var(--ink);background:#f8fafc}
header{padding:16px 24px 8px;background:#fff;border-bottom:1px solid var(--bd)}
main{padding:16px 24px 32px;max-width:1200px}
h1{margin:0 0 4px;font-size:19px}
h2{font-size:15px;margin:22px 0 8px}
.sub{color:var(--mut);margin:0 0 10px;font-size:13px;max-width:900px}
.links a{font-size:12px;color:var(--acc);text-decoration:none}
.links a:hover{text-decoration:underline}
.links span{color:#94a3b8;font-size:12px;margin:0 4px}
.bar-row{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;font-size:13px}
select,button.f{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--bd);border-radius:8px;background:#fff;color:var(--ink)}
button.f{cursor:pointer}
button.f[aria-pressed="true"]{background:#1e3a8a;color:#fff;border-color:#1e3a8a}
.totals{font-size:13px;line-height:1.5;margin:4px 0 6px;max-width:900px}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--mut);margin:6px 0 4px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.wrap{overflow-x:auto;background:#fff;border:1px solid var(--bd);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:7px 10px;border-bottom:1px solid var(--bd);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal;min-width:180px}
th{background:#f1f5f9;font-weight:600;cursor:pointer;user-select:none;position:sticky;top:0}
th[aria-sort="ascending"]::after{content:" \\25B2";font-size:9px}
th[aria-sort="descending"]::after{content:" \\25BC";font-size:9px}
td a{color:var(--ink);text-decoration:none;border-bottom:1px dotted #94a3b8}
td a:hover{color:var(--acc);border-bottom-color:var(--acc)}
td.bar{width:34%;min-width:160px}
tr.sel td{background:#eff6ff}
.empty{color:var(--mut);padding:10px}
.stack{display:flex;height:12px;border-radius:3px;overflow:hidden;background:#f1f5f9}
.stack span{display:block;height:100%}
.n{color:var(--mut)}
footer{color:var(--mut);font-size:12px;padding:0 24px 32px;max-width:900px;line-height:1.5}
</style>
</head><body>
<header>
<div class="links"><a href="/">&larr; Map</a><span>&middot;</span><a id="dashLink" href="/dashboard/?board=all">Requests dashboard</a><span>&middot;</span><a id="planLink" href="/plan/">Next-cycle planner</a></div>
<h1>How the City answered community board budget requests</h1>
<p class="sub">Each year, NYC's 59 community boards send the City their budget requests, and the agency that would carry each one out answers it. Click an agency or a board to see its requests.</p>
<div class="bar-row"><label>Year <select id="year"></select></label><label>Board <select id="board"><option value="">All boards</option></select></label></div>
</header>
<main>
<div class="totals" id="totals"></div>
<div class="legend" id="legend"></div>
<h2 id="agencyHead">By agency</h2>
<div class="wrap"><table id="agencies"></table></div>
<h2>By board</h2>
<div class="bar-row" id="boros"></div>
<div class="wrap" style="margin-top:8px"><table id="boards"></table></div>
</main>
<footer id="foot"></footer>
<script>
var D = __DATA__;
var CAT = {
  six: [["can","Supports and can accommodate","#15803d"],["cannot","Supports but can\\u2019t accommodate","#86efac"],
        ["completed","Already completed","#60a5fa"],["alternative","Doesn\\u2019t support but can meet the need another way","#a78bfa"],
        ["unclear","Doesn\\u2019t understand the request","#fbbf24"],["oppose","Doesn\\u2019t support","#ef4444"],
        ["none","No response","#cbd5e1"],["other","Other","#94a3b8"]],
  three: [["support","Supports","#16a34a"],["neutral","Neutral or unclear","#cbd5e1"],["oppose","Opposes","#ef4444"]]};
var COLS = {six: ["can","cannot","oppose"], three: ["support","oppose","neutral"]};
var BORO = [["","All boroughs"],["M","Manhattan"],["BX","Bronx"],["BK","Brooklyn"],["Q","Queens"],["SI","Staten Island"]];
var $ = function(id){ return document.getElementById(id); };
var esc = function(s){ return String(s).replace(/[&<>"']/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); };
var pct = function(c, k, n){ return n ? 100 * (c[k] || 0) / n : 0; };
var fmt = function(x){ return Math.round(x) + "%"; };
var S = {year: D.latest, boro: "", board: "", sort: {agencies: ["n", -1], boards: ["order", 1]}};
// Every board that appears in any year, for the board menu (code -> name and borough).
var BOARDS = {};
D.years.forEach(function(y){ (D.data[y] ? D.data[y].boards : []).forEach(function(b){ BOARDS[b[0]] = {name: b[1], boro: b[2]}; }); });

function readURL(){
  var p = new URLSearchParams(location.search);
  if(p.get("year") && D.data[p.get("year")]) S.year = p.get("year");
  if(BORO.some(function(b){ return b[0] === p.get("boro"); })) S.boro = p.get("boro") || "";
  var bd = (p.get("board") || "").toUpperCase(); if(BOARDS[bd]) S.board = bd;
}
function writeURL(){
  var p = new URLSearchParams();
  if(S.year !== D.latest) p.set("year", S.year);
  if(S.board) p.set("board", S.board);
  if(S.boro) p.set("boro", S.boro);
  var q = p.toString();
  try { history.replaceState(null, "", location.pathname + (q ? "?" + q : "")); } catch(e){}
}
function cats(){ return CAT[D.data[S.year].mode]; }
function stack(c, n){
  return '<div class="stack" role="img" aria-label="' + esc(cats().filter(function(k){ return c[k[0]]; }).map(function(k){ return k[1] + " " + fmt(pct(c, k[0], n)); }).join(", ")) + '">' +
    cats().map(function(k){ var w = pct(c, k[0], n); return w ? '<span style="width:' + w + '%;background:' + k[2] + '" title="' + esc(k[1] + ": " + (c[k[0]] || 0) + " (" + fmt(w) + ")") + '"></span>' : ""; }).join("") + "</div>";
}
function table(id, rows, nameOf, linkOf){
  var mode = D.data[S.year].mode, cols = COLS[mode], label = {};
  cats().forEach(function(k){ label[k[0]] = k[1]; });
  var sort = S.sort[id], key = sort[0], dir = sort[1];
  rows = rows.slice().sort(function(a, b){
    var va = key === "name" ? a.name : key === "n" ? a.n : key === "order" ? a.order : pct(a.c, key, a.n),
        vb = key === "name" ? b.name : key === "n" ? b.n : key === "order" ? b.order : pct(b.c, key, b.n);
    return (va < vb ? -1 : va > vb ? 1 : 0) * dir || b.n - a.n; });
  var th = function(k, text){ var s = key === k || (k === "name" && key === "order") ? (dir > 0 ? "ascending" : "descending") : "none";
    return '<th scope="col" data-k="' + k + '" aria-sort="' + s + '">' + text + "</th>"; };
  $(id).innerHTML = "<thead><tr>" + th(id === "boards" ? "order" : "name", id === "boards" ? "Board" : "Agency") + th("n", "Requests") +
    '<th scope="col" class="bar" aria-sort="none">Answers</th>' + cols.map(function(k){ return th(k, esc(label[k])); }).join("") + "</tr></thead><tbody>" +
    (rows.length ? "" : '<tr><td class="empty" colspan="' + (3 + cols.length) + '">No requests.</td></tr>') +
    rows.map(function(r){ return '<tr' + (r.sel ? ' class="sel"' : '') + '><td><a href="' + esc(linkOf(r)) + '">' + esc(nameOf(r)) + "</a></td><td>" + r.n + '</td><td class="bar">' + stack(r.c, r.n) + "</td>" +
      cols.map(function(k){ return "<td>" + fmt(pct(r.c, k, r.n)) + ' <span class="n">(' + (r.c[k] || 0) + ")</span></td>"; }).join("") + "</tr>"; }).join("") + "</tbody>";
  [].forEach.call($(id).querySelectorAll("th[data-k]"), function(h){ h.addEventListener("click", function(){
    var k = h.dataset.k; S.sort[id] = [k, S.sort[id][0] === k ? -S.sort[id][1] : (k === "name" || k === "order" ? 1 : -1)]; render(); }); });
}
function render(){
  var Y = D.data[S.year], url = D.yearUrl[S.year], B = S.board, row = B ? Y.boards.filter(function(b){ return b[0] === B; })[0] : null;
  var c = B ? (row ? row[4] : {}) : Y.total, n = B ? (row ? row[3] : 0) : Y.n, name = B ? BOARDS[B].name : "";
  $("dashLink").href = url + "?board=" + (B || "all");
  $("planLink").href = "/plan/" + (B ? "?board=" + encodeURIComponent(B) : "");
  $("agencyHead").textContent = B ? "By agency, for " + name : "By agency";
  $("legend").innerHTML = cats().filter(function(k){ return c[k[0]]; }).map(function(k){ return '<span><i style="background:' + k[2] + '"></i>' + esc(k[1]) + "</span>"; }).join("");
  var parts = cats().filter(function(k){ return c[k[0]]; }).map(function(k){ return esc(k[1].toLowerCase()) + " " + fmt(pct(c, k[0], n)); });
  $("totals").innerHTML = B && !n ? esc(name) + " has no published requests for FY" + S.year + "."
    : "In FY" + S.year + ", agencies answered <b>" + n.toLocaleString() + "</b> requests" + (B ? " from " + esc(name) : "") + ": " + parts.join(", ") + "." + stack(c, n);
  table("agencies", (B ? (Y.byBoard[B] || []) : Y.agencies).map(function(a){ return {name: a[0], n: a[1], c: a[2]}; }),
    function(r){ return r.name; }, function(r){ return url + "?board=" + (B || "all") + "&c_agency=" + encodeURIComponent(r.name); });
  table("boards", Y.boards.filter(function(b){ return !S.boro || b[2] === S.boro; }).map(function(b, i){ return {code: b[0], name: b[1], order: i, n: b[3], c: b[4], sel: b[0] === B}; }),
    function(r){ return r.name; }, function(r){ return url + "?board=" + encodeURIComponent(r.code); });
  $("boros").innerHTML = BORO.map(function(b){ return '<button type="button" class="f" data-b="' + b[0] + '" aria-pressed="' + (S.boro === b[0]) + '">' + b[1] + "</button>"; }).join("");
  [].forEach.call($("boros").querySelectorAll("button"), function(x){ x.addEventListener("click", function(){ S.boro = x.dataset.b; writeURL(); render(); }); });
  $("foot").innerHTML = Y.mode === "six"
    ? "For FY2026 and later, each answer is the standard reply the agency chose in DCP\\u2019s Statement of Community District Needs, such as \\u201cAgency supports but cannot accommodate.\\u201d \\u201cSupports but can\\u2019t accommodate\\u201d usually means the agency likes the request but has no money for it."
    : "Before FY2026 agencies did not choose from standard replies, so these answers come from the dashboard\\u2019s Agency Stance column, which reads the first sentence of each response. \\u201cNeutral or unclear\\u201d includes replies such as \\u201cfurther study is needed\\u201d and \\u201calready completed.\\u201d";
}
D.years.forEach(function(y){ if(D.data[y]){ var o = document.createElement("option"); o.value = y; o.textContent = "FY" + y; $("year").appendChild(o); } });
BORO.slice(1).forEach(function(bo){
  var g = document.createElement("optgroup"); g.label = bo[1];
  Object.keys(BOARDS).filter(function(k){ return BOARDS[k].boro === bo[0]; })
    .sort(function(a, b){ return +a.replace(/\\D/g, "") - +b.replace(/\\D/g, ""); })
    .forEach(function(k){ var o = document.createElement("option"); o.value = k; o.textContent = BOARDS[k].name; g.appendChild(o); });
  $("board").appendChild(g); });
readURL(); $("year").value = S.year; $("board").value = S.board;
$("board").addEventListener("change", function(){ S.board = $("board").value; writeURL(); render(); });
$("year").addEventListener("change", function(){ S.year = $("year").value; writeURL(); render(); });
render();
</script>
</body></html>
"""

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(PAGE.replace("__DATA__", json.dumps(DATA_JS, separators=(",", ":"))))
y = DATA_JS["data"][LATEST]
print(f"wrote {os.path.normpath(OUT)} ({os.path.getsize(OUT) // 1024} KB, {len(DATA_JS['data'])} years; "
      f"FY{LATEST}: {len(y['agencies'])} agencies, {len(y['boards'])} boards)", file=sys.stderr)
