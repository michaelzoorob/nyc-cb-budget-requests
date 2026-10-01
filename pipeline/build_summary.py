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
/* The board menu works like the dashboard's: search, All and None, and a checkbox per board. */
.bsel{position:relative;display:flex;align-items:center;gap:5px}
.pick{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--bd);border-radius:8px;background:#fff;color:var(--ink);cursor:pointer;white-space:nowrap;max-width:260px;overflow:hidden;text-overflow:ellipsis}
.boardpanel{position:absolute;top:calc(100% + 4px);left:0;z-index:60;background:#fff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 10px 30px rgba(15,23,42,.18);padding:8px;width:240px;font-size:12px}
.cm-search{width:100%;padding:5px 7px;border:1px solid #cbd5e1;border-radius:6px;margin-bottom:6px;font-size:12px;font-family:inherit}
.cm-ctrl{display:flex;gap:6px;margin-bottom:4px}
.cm-mini{flex:1;border:1px solid #e2e8f0;background:#fff;border-radius:6px;padding:3px;cursor:pointer;font-size:11px;color:#475569}
.cm-mini:hover{background:#f1f5f9}
.cm-list{max-height:260px;overflow:auto;border:1px solid #eef2f7;border-radius:6px;padding:2px}
.cm-grp{font-weight:700;font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:.04em;padding:7px 4px 2px}
.cm-opt{display:flex;align-items:center;gap:7px;padding:3px 5px;cursor:pointer;border-radius:4px}
.cm-opt:hover{background:#f1f5f9}
.cm-opt span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
</head><body>
<header>
<div class="links"><a href="/">&larr; Map</a><span>&middot;</span><a id="dashLink" href="/dashboard/?board=all">Requests dashboard</a><span>&middot;</span><a id="planLink" href="/plan/">Next-cycle planner</a></div>
<h1>How the City answered community board budget requests</h1>
<p class="sub">Each year, NYC's 59 community boards send the City their budget requests, and the agency that would carry each one out answers it. Click an agency or a board to see its requests.</p>
<div class="bar-row"><label>Year <select id="year"></select></label>
<div class="bsel"><span>Board</span><button type="button" id="boardBtn" class="pick" aria-haspopup="true" aria-expanded="false" title="Filter by community board">All boards &#9662;</button>
<div id="boardPanel" class="boardpanel" hidden><input id="boardSearch" class="cm-search" type="search" placeholder="search boards…" aria-label="Search boards">
<div class="cm-ctrl"><button type="button" class="cm-mini" data-act="all">All</button><button type="button" class="cm-mini" data-act="none">None</button></div>
<div class="cm-list" id="boardList"></div></div></div></div>
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
// Every board that appears in any year, for the board menu (code -> name and borough), in
// the menu's order.
var BOARDS = {};
D.years.forEach(function(y){ (D.data[y] ? D.data[y].boards : []).forEach(function(b){ BOARDS[b[0]] = {name: b[1], boro: b[2]}; }); });
var boroIdx = function(code){ for(var i = 1; i < BORO.length; i++) if(BORO[i][0] === BOARDS[code].boro) return i; return 9; };
var CODES = Object.keys(BOARDS).sort(function(a, b){ return boroIdx(a) - boroIdx(b) || +a.replace(/\\D/g, "") - +b.replace(/\\D/g, ""); });
// As on the dashboard, the page opens on every board, ?board= narrows it, and a menu with
// no box checked also means every board.
var S = {year: D.latest, boro: "", boards: new Set(CODES), sort: {agencies: ["n", -1], boards: ["order", 1]}};
function allBoards(){ return !S.boards.size || S.boards.size === CODES.length; }
function picked(){ return allBoards() ? [] : CODES.filter(function(k){ return S.boards.has(k); }); }
function andList(xs){ return xs.length < 3 ? xs.join(" and ") : xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1]; }
function addCounts(into, c){ Object.keys(c).forEach(function(k){ into[k] = (into[k] || 0) + c[k]; }); return into; }

function readURL(){
  var p = new URLSearchParams(location.search);
  if(p.get("year") && D.data[p.get("year")]) S.year = p.get("year");
  if(BORO.some(function(b){ return b[0] === p.get("boro"); })) S.boro = p.get("boro") || "";
  var bd = (p.get("board") || "").toUpperCase().split(",").map(function(x){ return x.trim(); }).filter(function(x){ return BOARDS[x]; });
  if(bd.length) S.boards = new Set(bd);
}
function writeURL(){
  var p = new URLSearchParams();
  if(S.year !== D.latest) p.set("year", S.year);
  if(!allBoards()) p.set("board", picked().join(","));
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
  var Y = D.data[S.year], url = D.yearUrl[S.year], P = picked(), B = P.length > 0;
  var rows = B ? Y.boards.filter(function(b){ return S.boards.has(b[0]); }) : [];
  var c = B ? rows.reduce(function(o, b){ return addCounts(o, b[4]); }, {}) : Y.total;
  var n = B ? rows.reduce(function(t, b){ return t + b[3]; }, 0) : Y.n;
  var name = P.length > 3 ? P.length + " boards" : andList(P.map(function(k){ return BOARDS[k].name; }));
  var bq = B ? P.join(",") : "all";
  $("dashLink").href = url + "?board=" + bq;
  $("planLink").href = "/plan/" + (P.length === 1 ? "?board=" + encodeURIComponent(P[0]) : "");
  $("agencyHead").textContent = B ? "By agency, for " + name : "By agency";
  var agencies = Y.agencies;
  if(B){ var m = {};
    P.forEach(function(k){ (Y.byBoard[k] || []).forEach(function(a){ var x = m[a[0]] || (m[a[0]] = [a[0], 0, {}]); x[1] += a[1]; addCounts(x[2], a[2]); }); });
    agencies = Object.keys(m).map(function(k){ return m[k]; }); }
  $("legend").innerHTML = cats().filter(function(k){ return c[k[0]]; }).map(function(k){ return '<span><i style="background:' + k[2] + '"></i>' + esc(k[1]) + "</span>"; }).join("");
  var parts = cats().filter(function(k){ return c[k[0]]; }).map(function(k){ return esc(k[1].toLowerCase()) + " " + fmt(pct(c, k[0], n)); });
  $("totals").innerHTML = B && !n ? esc(name) + (P.length > 1 ? " have" : " has") + " no published requests for FY" + S.year + "."
    : "In FY" + S.year + ", agencies answered <b>" + n.toLocaleString() + "</b> requests" + (B ? " from " + esc(name) : "") + ": " + parts.join(", ") + "." + stack(c, n);
  table("agencies", agencies.map(function(a){ return {name: a[0], n: a[1], c: a[2]}; }),
    function(r){ return r.name; }, function(r){ return url + "?board=" + bq + "&c_agency=" + encodeURIComponent(r.name); });
  table("boards", Y.boards.filter(function(b){ return !S.boro || b[2] === S.boro; }).map(function(b, i){ return {code: b[0], name: b[1], order: i, n: b[3], c: b[4], sel: B && S.boards.has(b[0])}; }),
    function(r){ return r.name; }, function(r){ return url + "?board=" + encodeURIComponent(r.code); });
  $("boros").innerHTML = BORO.map(function(b){ return '<button type="button" class="f" data-b="' + b[0] + '" aria-pressed="' + (S.boro === b[0]) + '">' + b[1] + "</button>"; }).join("");
  [].forEach.call($("boros").querySelectorAll("button"), function(x){ x.addEventListener("click", function(){ S.boro = x.dataset.b; writeURL(); render(); }); });
  $("foot").innerHTML = Y.mode === "six"
    ? "For FY2026 and later, each answer is the standard reply the agency chose in DCP\\u2019s Statement of Community District Needs, such as \\u201cAgency supports but cannot accommodate.\\u201d \\u201cSupports but can\\u2019t accommodate\\u201d usually means the agency likes the request but has no money for it."
    : "Before FY2026 agencies did not choose from standard replies, so these answers come from the dashboard\\u2019s Agency Stance column, which reads the first sentence of each response. \\u201cNeutral or unclear\\u201d includes replies such as \\u201cfurther study is needed\\u201d and \\u201calready completed.\\u201d";
}
D.years.forEach(function(y){ if(D.data[y]){ var o = document.createElement("option"); o.value = y; o.textContent = "FY" + y; $("year").appendChild(o); } });
BORO.slice(1).forEach(function(bo){
  var codes = CODES.filter(function(k){ return BOARDS[k].boro === bo[0]; });
  if(codes.length) $("boardList").insertAdjacentHTML("beforeend", '<div class="cm-grp">' + esc(bo[1]) + "</div>" + codes.map(function(k){
    return '<label class="cm-opt" data-name="' + esc(BOARDS[k].name + " " + k) + '"><input type="checkbox" value="' + k + '"><span>' + esc(BOARDS[k].name) + "</span></label>"; }).join("")); });
var boxes = [].slice.call($("boardList").querySelectorAll("input"));
function updBoard(){
  boxes.forEach(function(x){ x.checked = S.boards.has(x.value); });
  var P = picked();
  $("boardBtn").innerHTML = esc(P.length === 0 ? "All boards" : P.length === 1 ? BOARDS[P[0]].name : P.length + " boards") + " &#9662;";
}
function boardsChanged(){ updBoard(); writeURL(); render(); }
boxes.forEach(function(x){ x.addEventListener("change", function(){ if(x.checked) S.boards.add(x.value); else S.boards.delete(x.value); boardsChanged(); }); });
[].forEach.call($("boardPanel").querySelectorAll(".cm-mini"), function(b){ b.addEventListener("click", function(){
  S.boards = b.dataset.act === "all" ? new Set(CODES) : new Set(); boardsChanged(); }); });
// Search hides the boards that don't match, and a borough heading with none left.
$("boardSearch").addEventListener("input", function(){ var t = this.value.toLowerCase(), grp = null, any = false;
  [].forEach.call($("boardList").children, function(el){
    if(el.classList.contains("cm-grp")){ if(grp) grp.hidden = !any; grp = el; any = false; return; }
    el.hidden = (el.dataset.name || "").toLowerCase().indexOf(t) < 0; any = any || !el.hidden; });
  if(grp) grp.hidden = !any; });
function menu(open){ $("boardPanel").hidden = !open; $("boardBtn").setAttribute("aria-expanded", open); if(open) $("boardSearch").focus(); }
$("boardBtn").addEventListener("click", function(e){ e.stopPropagation(); menu($("boardPanel").hidden); });
$("boardPanel").addEventListener("click", function(e){ e.stopPropagation(); });
document.addEventListener("click", function(){ menu(false); });
document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !$("boardPanel").hidden){ menu(false); $("boardBtn").focus(); } });
readURL(); $("year").value = S.year; updBoard();
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
