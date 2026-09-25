#!/usr/bin/env python3
"""Render one fiscal year's two-stage detailed spreadsheet as a single self-contained
HTML page. Each request shows the agency's response and OMB's Executive response.
Click a column name to sort; click its funnel button to filter.

    generate_cb2_html.py [--fy YEAR] [CSV] [OUT]

A Year menu links the pages for every year in shared.YEARS. The latest year is the
site root (/); earlier years live at /fy<YEAR>/. Filters carry across years, so a
board, committee, search or column filter set on one year's page stays set on the
next. The URL records all of it, which makes any view shareable."""
import html
import json
import os
import re
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared import FOLLOWUP_COLS, LATEST, PDF_YEARS, PUBLICATIONS, YEARS  # noqa: E402

argv = sys.argv[1:]
FY = LATEST
if "--fy" in argv:
    _i = argv.index("--fy")
    FY = argv[_i + 1]
    del argv[_i:_i + 2]
CSV = argv[0] if len(argv) > 0 else f"CB FY{FY} Requests (all boards, detailed, 2-stage).csv"
OUT = argv[1] if len(argv) > 1 else f"CB2 FY{FY} Requests and Agency Responses.html"
FROM_PDF = FY in PDF_YEARS
YEAR_URL = {y: ("/" if y == LATEST else f"/fy{y}/") for y in YEARS}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def pub_month(pub):                       # "20240116" -> "January 2024"
    return f"{MONTHS[int(pub[4:6]) - 1]} {pub[:4]}"


REG_URL = "https://data.cityofnewyork.us/City-Government/Register-of-Community-Board-Budget-Requests/vn4m-mk4t"
REPO_URL = "https://github.com/NYCPlanning/labs-cd-needs-statements"

BORO_FULL = {"M": "Manhattan", "BX": "Bronx", "BK": "Brooklyn", "Q": "Queens", "SI": "Staten Island"}
DCP2 = {"M": "MN", "BX": "BX", "BK": "BK", "Q": "QN", "SI": "SI"}
BORO_ORDER = {"M": 0, "BX": 1, "BK": 2, "Q": 3, "SI": 4}
MAXCB = {"M": 12, "BX": 12, "BK": 18, "Q": 14, "SI": 3}
# Every board, including ones absent from this year, so a board carried over from
# another year's page can still be named ("Brooklyn CB6 has no FY2020 requests").
ALL_BOARDS = [f"{b}CB{n}" for b in BORO_ORDER for n in range(1, MAXCB[b] + 1)]


def _split(b):
    m = re.match(r"([A-Z]+)CB(\d+)", str(b))
    return m.group(1), m.group(2)


def board_short(b):                       # "QCB2" -> "Queens CB2"
    a, n = _split(b)
    return f"{BORO_FULL[a]} CB{n}"


def board_full_name(b):                   # "QCB2" -> "Queens Community Board 2"
    a, n = _split(b)
    return f"{BORO_FULL[a]} Community Board {n}"


def board_pdf_url(b):                     # opens in GitHub's viewer instead of downloading
    a, n = _split(b)
    return f"{REPO_URL}/blob/master/{DCP2[a]}%20DNS%20FY%20{FY}/FY{FY}_Statement_{DCP2[a]}{n.zfill(2)}.pdf"


def _bk(b):
    a, n = _split(b)
    return (BORO_ORDER.get(a, 9), int(n))


df = pd.read_csv(CSV, dtype=str).fillna("")
for _c in FOLLOWUP_COLS + ["Tracking Code"]:          # CSVs built before follow-up labels existed
    if _c not in df:
        df[_c] = ""
boards = sorted(df["Board"].unique(), key=_bk)
DEFAULT_BOARD = "QCB2" if "QCB2" in boards else ""
board_name = {b: board_short(b) for b in ALL_BOARDS}
board_full = {b: board_full_name(b) for b in ALL_BOARDS}
board_pdf = {b: board_pdf_url(b) for b in boards}

_chk, _cur = [], None
for _b in boards:
    _ab = _split(_b)[0]
    if _ab != _cur:
        _cur = _ab
        _chk.append(f'<div class="cm-grp">{html.escape(BORO_FULL[_ab])}</div>')
    _ck = " checked" if _b == DEFAULT_BOARD else ""
    _chk.append(f'<label class="cm-opt" data-name="{html.escape(board_name[_b] + " " + _b)}">'
                f'<input type="checkbox" value="{html.escape(_b)}"{_ck}> {html.escape(board_name[_b])}</label>')
board_checklist = "".join(_chk)

DISPLAY = ["Priority", "Type", "Board", "Agency", "Title", "Explanation",
           "Agency Response", "OMB Executive Response", "Agency Stance (MZ added)", "Follow-up"]
WIDE = {"Title", "Explanation", "Agency Response", "OMB Executive Response"}
PCT = {"Priority": 6, "Type": 6, "Board": 5, "Agency": 8, "Title": 12,
       "Explanation": 13, "Agency Response": 16.5, "OMB Executive Response": 16.5,
       "Agency Stance (MZ added)": 7.5, "Follow-up": 9.5}
LABEL = {"Agency Stance (MZ added)": "Agency Stance"}
# Each column's filter kind is fixed, so a filter means the same thing on every year's
# page. (Choosing by the number of distinct values made Priority a checkbox list on
# FY2027 and a "contains" text box on earlier years.)
FILTER_KIND = {"Priority": "set", "Type": "set", "Board": "set", "Agency Stance": "set", "Follow-up": "set"}
FU_SLUG = {"Contact agency": "a", "Contact elected officials": "e", "Contact agency and elected officials": "ae",
           "Track with agency": "t", "Use 311 or another channel": "c", "No follow-up needed": "n"}

# Some years' Statement PDFs could not be used for a few boards, which then come
# from the Register. The page says which.
YEAR_NOTE = {
    "2025": (" The Register has no FY2025 requests from Brooklyn CB6, CB12 or CB16. Brooklyn CB16's "
             "Statement lists its requests, so they appear without responses. DCP published no FY2025 "
             "Statement for Brooklyn CB6 or CB12, so those boards are absent."),
    "2020": (" The Register has no FY2020 requests from Brooklyn CB6, and DCP published no FY2020 Statement "
             "for it, so the board is absent."),
    "2026": (" The FY2026 Bronx PDFs list each request without the agency's response, so the Bronx "
             "boards' responses come from the Register. The Register has no FY2026 requests from Bronx CB12, "
             "so its 11 requests appear without responses. DCP's FY2026 file for Manhattan CB7 holds CB6's "
             "requests, so Manhattan CB7 comes entirely from the Register."),
}
MIXED = " A few boards come from the Register instead. See the note above." if FROM_PDF and FY in YEAR_NOTE else ""

n_omb_all = (df["OMB Executive Response"].str.strip() != "").sum()
_num = df[df["Priority"].str.isdigit()].assign(_p=lambda x: x["Priority"].astype(int))


def _ranked_within(keys):
    """Share of groups whose priorities run exactly 1..n."""
    g = _num.groupby(keys)["_p"].apply(lambda s: sorted(s) == list(range(1, len(s) + 1)))
    return g.mean() if len(g) else 0


# FY2027 Statements rank a board's requests to each agency separately.
BY_AGENCY = _ranked_within(["Board", "Type", "Agency"]) > 0.9 and _ranked_within(["Board", "Type"]) < 0.5
if FROM_PDF:
    TOOLTIP = {
        "Priority": (f"The request's priority number in the board's FY{FY} Statement of Community District Needs (PDF)."
                     + (f" In FY{FY} a board ranks its requests to each agency separately. Priority 2 is the board's "
                        "second capital or expense request to that agency, so several requests share each number. "
                        "These priorities are not comparable with other years." if BY_AGENCY else "")),
        "Type": "Capital or Expense, from the Statement PDF's capital and expense sections.",
        "Board": "Borough + community board (e.g. QCB2 = Queens Community Board 2).",
        "Agency": "The city agency responsible for the request (from the Statement PDF).",
        "Title": ("The request's title in the Statement PDF. Where a board wrote no title of its own, "
                  "this is DCP's standard request category." + MIXED),
        "Explanation": "The board's description and justification of the request (from the Statement PDF).",
        "Agency Response": f"The agency's full written response, from the FY{FY} Statement of Community District Needs (PDF)." + MIXED,
        "OMB Executive Response": "OMB's Executive Budget response, from NYC Open Data's Register of Community Board Budget Requests, "
                                  f"matched to each request by its text ({100 * n_omb_all / max(1, len(df)):.1f}% of requests matched).",
    }
else:
    _ag, _omb = PUBLICATIONS[FY]
    TOOLTIP = {
        "Priority": "The board's priority for this request (from NYC Open Data's Register of Community Board Budget Requests).",
        "Type": "Capital or Expense, from the request's tracking code in the Register.",
        "Board": "Borough + community board (e.g. QCB2 = Queens Community Board 2).",
        "Agency": "The city agency responsible for the request (from the Register).",
        "Title": "DCP's standard category for the request (from the Register). Boards' own titles begin in FY2026.",
        "Explanation": "The board's description and justification of the request (from the Register).",
        "Agency Response": f"The agency's response, from the Register's {pub_month(_ag)} round of agency responses.",
        "OMB Executive Response": f"OMB's Executive Budget response, from the Register's {pub_month(_omb)} round.",
    }
TOOLTIP["Agency Stance (MZ added)"] = (
    "Added by MZ. Support, Oppose or Neutral/Unclear, read from the first sentence of the agency response. "
    "It records whether the agency supports the request, regardless of whether it can fund it."
    + ("" if FROM_PDF else
       " Before FY2026 agencies mostly answered with standard phrases that take no position, such as "
       "\"Further study by the agency of this request is needed\", so most requests read Neutral/Unclear."))

TOOLTIP["Follow-up"] = (
    "The next step for a board that still wants this request, read from the agency and OMB responses by a model "
    "following label_followup/rubric.md in the repository. Draft letter writes a follow-up letter to the agency, "
    "the district's Council Members or the Borough President.")

committees_list = sorted({c for cs in df["Committees"] for c in str(cs).split("|") if c})


def clean_text(v):
    """Display-only cleanup of artifacts in the source text. The Register's \\x1a stands
    for an apostrophe ("the City\\x1as vision"), U+FFFD marks a character lost upstream
    (usually a non-breaking space or a line break), PDF page breaks leave form feeds, and
    some Register text carries HTML entities ("it&#39;s"). The pipeline's CSVs keep the
    source text as published. Where the lost character is a known letter ("caf�",
    "Fa�ade"), it is restored."""
    t = html.unescape(str(v)).replace("\x1a", "'")
    t = re.sub(r"\b([Cc])af�", r"\1afé", re.sub(r"\b([Ff])a�ade", r"\1açade", t))
    return re.sub(r"[\x00-\x08\x0b-\x1f�]", " ", t)


def stance_slug(v):
    return {"Support": "support", "Oppose": "oppose",
            "Neutral/Unclear": "neutral"}.get(v, "neutral")


body = []
for idx, (_, r) in enumerate(df.iterrows()):
    z = "odd" if idx % 2 else "even"
    blob = html.escape(" ".join(clean_text(r[c]) for c in DISPLAY).lower(), quote=True)
    tds = []
    for c in DISPLAY:
        val = html.escape(clean_text(r[c]))
        if c == "Agency Stance (MZ added)":
            # <wbr>: a narrow column breaks "Neutral/Unclear" at the slash, not mid-word
            tds.append(f'<td><span class="pill i-{stance_slug(r[c])}">{val.replace("/", "/<wbr>")}</span></td>')
        elif c == "Type":
            tds.append(f'<td><span class="pill {"ce-e" if r[c] == "Expense" else "ce-c"}">{val}</span></td>')
        elif c == "Follow-up":
            # data-v is the cell's value for sorting, filters and the CSV; the button is not.
            if val:
                why = html.escape(clean_text(r["Follow-up Why"]), quote=True)
                tds.append(f'<td class="fu-td" data-v="{html.escape(clean_text(r[c]), quote=True)}"><div class="fu-cell">'
                           f'<span class="pill fu-pill fu-{FU_SLUG.get(r[c], "n")}" title="{why}">{val}</span>'
                           f'<button type="button" class="fu-btn">Draft letter</button></div></td>')
            else:
                tds.append('<td class="fu-td" data-v=""></td>')
        elif c == "Board":
            tds.append(f'<td class="board">{val}</td>')
        elif c == "Agency":
            tds.append(f'<td class="agency">{val}</td>')
        elif c in WIDE:
            extra = " mtitle" if c == "Title" else ""
            tds.append(f'<td class="wide{extra}">{val}</td>')
        else:
            tds.append(f'<td class="nowrap">{val}</td>')
    fu_attrs = "".join(f' {a}="{html.escape(clean_text(r[c]), quote=True)}"' for a, c in
                       [("data-tc", "Tracking Code"), ("data-fp", "Follow-up Purpose"),
                        ("data-fc", "Follow-up Contact"), ("data-fu", "Follow-up URL")] if str(r[c]).strip())
    body.append(f'<tr class="{z}" data-search="{blob}" '
                f'data-board="{html.escape(str(r["Board"]), quote=True)}" '
                f'data-committees="{html.escape(str(r["Committees"]), quote=True)}"{fu_attrs}>' + "".join(tds) + "</tr>")

FUNNEL = ("<svg viewBox='0 0 16 16' width='11' height='11' aria-hidden='true'>"
          "<path fill='currentColor' d='M1 3h14l-5.5 6.5V14l-3 1.5V9.5z'/></svg>")


def th(idx, label, cls, tip):
    lab = html.escape(label)
    return (f'<th class="{cls}" data-ci="{idx}" data-label="{lab}" title="{html.escape(tip)}"><div class="th-in">'
            f'<span class="th-lbl">{lab}<span class="th-arrow"></span></span>'
            f'<button class="th-funnel" title="Filter this column" aria-label="Filter this column">{FUNNEL}</button>'
            f'</div></th>')


def col_cls(c):
    if c in WIDE:
        return "wide"
    if c == "Agency":
        return "agency"
    return "nowrap"


header_cells = "".join(th(i, LABEL.get(c, c), col_cls(c), TOOLTIP.get(c, "")) for i, c in enumerate(DISPLAY))
colgroup = "<colgroup>" + "".join(f"<col style='width:{PCT[c]}%'>" for c in DISPLAY) + "</colgroup>"

HEAD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><link rel="icon" href="data:,">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FY__FY__ NYC Community Board Budget Requests &amp; Agency Responses</title>
<style>
:root{--bd:#e2e8f0;--mut:#64748b;--ink:#0f172a;}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  margin:0;color:var(--ink);background:#f8fafc;font-size:13px;line-height:1.45}
header{padding:20px 24px 12px;background:#fff;border-bottom:1px solid var(--bd)}
h1{margin:0 0 4px;font-size:19px}
.sub{color:var(--mut);margin:0 0 14px;font-size:13px;max-width:1100px}
.sub a{color:#2563eb;text-decoration:underline}
.cards{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:6px}
.card{background:#f1f5f9;border:1px solid var(--bd);border-radius:8px;padding:8px 12px;min-width:104px}
.card .k{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.03em}
.card .v{font-size:16px;font-weight:600}
.controls{position:sticky;top:0;z-index:20;background:#fff;border-bottom:1px solid var(--bd);
  padding:10px 24px;display:flex;flex-wrap:wrap;gap:12px;align-items:center}
input#q{flex:1;min-width:220px;padding:8px 10px;border:1px solid var(--bd);border-radius:8px;font-size:13px}
.commsel{padding:7px 9px;border:1px solid var(--bd);border-radius:8px;font-size:13px;background:#fff;color:var(--ink);cursor:pointer;max-width:240px}
.bsel{position:relative}
.boardbtn{cursor:pointer;white-space:nowrap}
.boardpanel{position:absolute;top:calc(100% + 4px);left:0;z-index:60;background:#fff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 10px 30px rgba(15,23,42,.18);padding:8px;width:240px}
.cm-grp{font-weight:700;font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:.04em;padding:7px 4px 2px}
.dlbtn{padding:8px 12px;border:1px solid #2563eb;background:#2563eb;color:#fff;border-radius:8px;font-size:13px;cursor:pointer;white-space:nowrap}
.dlbtn:hover{background:#1d4ed8}
.hint{color:var(--mut);font-size:12px}
.hint svg{vertical-align:-1px}
.count{color:var(--mut);font-size:12px;white-space:nowrap;margin-left:auto}
.notice{margin:10px 12px 0;padding:8px 12px;border:1px solid #fde68a;background:#fffbeb;color:#92400e;border-radius:8px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 12px 0}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 4px 3px 10px;border:1px solid #bae6fd;background:#f0f9ff;
  color:#0c4a6e;border-radius:999px;font-size:12px}
.chip button{border:0;background:#e0f2fe;color:#0c4a6e;border-radius:999px;width:18px;height:18px;cursor:pointer;line-height:1;padding:0}
.chip button:hover{background:#bae6fd}
.wrap{padding:0 12px 40px}
table{border-collapse:separate;border-spacing:0;width:100%;table-layout:fixed;background:#fff;margin-top:8px}
thead th{position:sticky;top:var(--ch,0px);background:#1e293b;color:#fff;text-align:left;padding:8px 6px;
  font-size:10.5px;font-weight:600;white-space:normal;vertical-align:bottom;user-select:none;z-index:2}
.th-in{display:flex;align-items:flex-end;gap:3px;justify-content:space-between}
.th-lbl{cursor:pointer;flex:1 1 auto;min-width:0;overflow-wrap:anywhere}
.th-lbl:hover{text-decoration:underline}
.th-arrow{font-size:9px}
.th-funnel{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;
  border:1px solid rgba(255,255,255,.25);background:rgba(255,255,255,.1);color:#cbd5e1;border-radius:4px;
  padding:0;width:16px;height:16px}
.th-funnel:hover{background:rgba(255,255,255,.25);color:#fff}
.th-funnel.active{background:#38bdf8;border-color:#38bdf8;color:#08263a}
td{padding:8px 10px;border-bottom:1px solid #eef2f7;vertical-align:top;overflow-wrap:anywhere}
tr.even td{background:#fff}
tr.odd td{background:#f8fafc}
.wide{white-space:pre-wrap}
.nowrap{white-space:normal}
td.agency{white-space:normal;font-size:12px}
.board{white-space:nowrap;font-weight:600}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;white-space:nowrap;
  max-width:100%;overflow-wrap:anywhere}
td .i-neutral{white-space:normal;overflow-wrap:normal}
.i-support{background:#dcfce7;color:#166534}
.i-oppose{background:#fee2e2;color:#b42318}
.i-neutral{background:#fef3c7;color:#92400e}
.ce-e{background:#ede9fe;color:#5b21b6}
.ce-c{background:#cffafe;color:#155e75}
tr.hide{display:none}
.colmenu{position:absolute;z-index:60;background:#fff;border:1px solid #cbd5e1;border-radius:10px;
  box-shadow:0 10px 30px rgba(15,23,42,.18);padding:8px;min-width:190px;max-width:260px;font-size:12px;color:var(--ink)}
.cm-title{font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.03em;color:#475569;padding:2px 4px 6px}
.cm-search{width:100%;box-sizing:border-box;padding:5px 7px;border:1px solid #cbd5e1;border-radius:6px;margin-bottom:6px;font-size:12px}
.cm-ctrl{display:flex;gap:6px;margin-bottom:4px}
.cm-mini{flex:1;border:1px solid #e2e8f0;background:#fff;border-radius:6px;padding:3px;cursor:pointer;font-size:11px;color:#475569}
.cm-mini:hover{background:#f1f5f9}
.cm-list{max-height:200px;overflow:auto;border:1px solid #eef2f7;border-radius:6px;padding:2px}
.cm-opt{display:flex;align-items:center;gap:7px;padding:3px 5px;cursor:pointer;border-radius:4px}
.cm-opt:hover{background:#f1f5f9}
.cm-opt span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cm-clear{width:100%;margin-top:6px;border:1px solid #fecaca;background:#fef2f2;color:#b42318;border-radius:6px;padding:5px;cursor:pointer;font-size:12px}
.cm-clear:hover{background:#fee2e2}
.msort{display:none}
.fu-cell{display:flex;flex-direction:column;align-items:flex-start;gap:5px}
td .fu-pill{white-space:normal;overflow-wrap:normal}
.fu-a{background:#dbeafe;color:#1e40af}
.fu-e{background:#ede9fe;color:#5b21b6}
.fu-ae{background:#e0e7ff;color:#3730a3}
.fu-t{background:#ccfbf1;color:#115e59}
.fu-c{background:#ffedd5;color:#9a3412}
.fu-n{background:#f1f5f9;color:#475569}
.fu-btn{border:1px solid #cbd5e1;background:#fff;border-radius:6px;padding:2px 8px;font-size:11px;cursor:pointer;color:#0f172a}
.fu-btn:hover{background:#eef2ff;border-color:#a5b4fc}
.fu-ov{position:fixed;inset:0;background:rgba(15,23,42,.45);display:flex;align-items:flex-start;justify-content:center;
  z-index:60;padding:32px 16px;overflow:auto}
.fu-ov[hidden]{display:none}
body.fu-lock{overflow:hidden}
.fu-box{background:#fff;border-radius:12px;max-width:780px;width:100%;padding:16px 20px 18px;box-shadow:0 12px 36px rgba(15,23,42,.25)}
.fu-head{display:flex;align-items:flex-start;gap:10px}
.fu-head h2{font-size:17px;margin:2px 0 8px;flex:1}
.fu-x{border:0;background:#f1f5f9;border-radius:8px;width:32px;height:32px;font-size:20px;cursor:pointer;line-height:1}
.fu-meta{font-size:13px;color:#334155;margin-bottom:6px}
.fu-small{font-size:12px;color:var(--mut);margin-top:4px}
.fu-sec{margin:12px 0}
.fu-h{font-weight:700;font-size:13px;margin-bottom:4px}
.fu-sub{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;color:var(--mut);margin:8px 0 2px}
.fu-rcp{display:flex;gap:8px;align-items:flex-start;padding:4px 0;font-size:13px;cursor:pointer}
.fu-rcp small{color:var(--mut)}
.fu-row{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:13px}
.fu-in{border:1px solid #cbd5e1;border-radius:6px;padding:6px 8px;font:inherit;font-size:13px;flex:1 1 200px;min-width:0}
.fu-letter{border:1px solid var(--bd);border-radius:10px;padding:10px;margin:10px 0;background:#f8fafc}
.fu-to{font-size:13px;margin-bottom:6px}
.fu-subj{width:100%;box-sizing:border-box;margin-bottom:6px}
.fu-body{width:100%;box-sizing:border-box;font:inherit;font-size:13px;line-height:1.45;border:1px solid #cbd5e1;border-radius:6px;padding:8px}
.fu-acts{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:6px}
.fu-act{border:1px solid #2563eb;background:#2563eb;color:#fff;border-radius:6px;padding:6px 10px;font-size:12.5px;cursor:pointer;text-decoration:none}
.fu-act.fu-copy{background:#fff;color:#1d4ed8}
.fu-copied{font-size:12px;color:#166534}
.fu-empty,.fu-note{font-size:12px;color:var(--mut)}
@media (max-width:820px){
  header{padding:14px 14px 10px}
  h1{font-size:16px;line-height:1.3}
  .sub{font-size:12px;margin-bottom:10px}
  .cards{gap:6px;margin-bottom:2px}
  .card{min-width:0;flex:1 1 27%;padding:6px 8px}
  .card .k{font-size:10px}
  .card .v{font-size:14px}
  .controls{position:static;padding:10px 12px;gap:8px}
  input#q{flex:1 1 100%;min-width:0}
  .bsel{flex:1 1 100%}
  .boardbtn{width:100%;max-width:none;text-align:left}
  #commSel{flex:1 1 48%;max-width:none}
  #yearSel{flex:1 1 48%;max-width:none}
  .msort{display:block;flex:1 1 48%;max-width:none}
  .dlbtn{flex:1 1 100%}
  .hint{display:none}
  .count{margin-left:0;flex:1 1 100%;order:9;text-align:right}
  .boardpanel{width:calc(100vw - 24px)}
  .wrap{padding:0 10px 48px}
  table,tbody,tr,td{display:block}
  colgroup,thead{display:none}
  table{table-layout:auto;width:100%;margin-top:4px;background:transparent}
  tr{background:#fff!important;border:1px solid var(--bd);border-radius:10px;
     margin:10px 0;padding:4px 12px;box-shadow:0 1px 2px rgba(15,23,42,.05)}
  tr.even td,tr.odd td{background:transparent!important}
  td{padding:7px 0;border-bottom:1px solid #f1f5f9;white-space:normal!important;overflow-wrap:anywhere}
  td:last-child{border-bottom:0}
  td::before{content:attr(data-th);display:block;font-weight:700;color:var(--mut);
     font-size:10px;text-transform:uppercase;letter-spacing:.03em;margin-bottom:3px}
  td.mtitle{font-size:14.5px;font-weight:600}
  .wide{white-space:pre-wrap!important}
  .fu-ov{padding:0}
  .fu-box{border-radius:0;min-height:100vh;padding:14px}
  .fu-cell{flex-direction:row;align-items:center;flex-wrap:wrap}
}
</style></head><body>
"""
HEAD = HEAD.replace("__FY__", FY)

SCRIPT = r"""
<script>
(function(){
  var FY=window.pageYear;
  var has=function(o,k){return o!=null && Object.prototype.hasOwnProperty.call(o,k);};
  var table=document.querySelector('table');
  var tbody=table.querySelector('tbody');
  var ths=[].slice.call(table.querySelectorAll('thead th'));
  var rows=[].slice.call(tbody.children);
  var KIND=window.filterKind||{};
  var numeric={}; ths.forEach(function(t,i){if((t.dataset.label||'').toLowerCase()==='priority') numeric[i]=true;});
  var countEl=document.getElementById('count');
  (function(){var L=ths.map(function(t){return t.dataset.label||'';});
    rows.forEach(function(tr){for(var i=0;i<tr.children.length&&i<L.length;i++) tr.children[i].setAttribute('data-th',L[i]);});})();
  var q=document.getElementById('q');
  var filters={}, sortCol=-1, sortDir=1, term='', rawTerm='', commFilter='';
  var boardPdf=window.boardPdf||{}, repoUrl=window.repoUrl||'', boardName=window.boardName||{}, boardFull=window.boardFull||{};
  var boxes=[].slice.call(document.querySelectorAll('#boardList input'));
  var present={}; boxes.forEach(function(c){present[c.value]=1;});
  var bTotal=boxes.length;
  // boardPick holds boards shown on this page. absentReq holds boards the URL asked
  // for that have no requests this year; they stay in the URL so switching back to a
  // year that has them restores them, and they empty the view with a notice.
  var boardPick=new Set(), absentReq=[];
  function cell(tr,ci){var td=tr.children[ci], v=td.getAttribute('data-v'); return (v!==null?v:td.textContent).trim();}
  function kindOf(ci){return KIND[ths[ci].dataset.label]==='set'?'set':'text';}
  var typeCol=-1,stanceCol=-1;
  ths.forEach(function(t,i){var l=(t.dataset.label||'').toLowerCase(); if(l==='type')typeCol=i; if(l.indexOf('stance')>-1)stanceCol=i;});
  function setCard(k,v){var e=document.querySelector('[data-card="'+k+'"]'); if(e)e.textContent=v;}
  function rowOk(tr){
    if(absentReq.length && boardPick.size===0) return false;
    if(boardPick.size && !boardPick.has(tr.dataset.board)) return false;
    if(commFilter && ((tr.dataset.committees||'').split('|').indexOf(commFilter)===-1)) return false;
    if(term && (tr.dataset.search||'').indexOf(term)===-1) return false;
    for(var ci in filters){var f=filters[ci], v=cell(tr,+ci);
      if(f.type==='set'){ if(!has(f.allowed,v)) return false; }
      else if(f.type==='text'){ if(v.toLowerCase().indexOf(f.q)===-1) return false; }}
    return true;
  }
  function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function renderNotice(){
    var n=document.getElementById('notice'); if(!n) return;
    if(!absentReq.length){n.style.display='none'; n.textContent=''; return;}
    var names=absentReq.map(function(b){return has(boardName,b)?boardName[b]:b;});
    n.textContent=(names.length===1?names[0]+' has':names.join(', ')+' have')+' no FY'+FY+' requests in NYC Open Data\'s Register or in DCP\'s Statement PDFs.';
    n.style.display='block';
  }
  function renderChips(){
    var box=document.getElementById('chips'); if(!box) return;
    box.innerHTML='';
    Object.keys(filters).forEach(function(ci){
      var f=filters[ci], lab=ths[ci].dataset.label||'', txt;
      if(f.type==='set'){var v=Object.keys(f.allowed);
        txt=v.length? v.slice(0,3).join(', ')+(v.length>3?' +'+(v.length-3)+' more':'') : 'none';}
      else txt='contains “'+f.q+'”';
      var s=document.createElement('span'); s.className='chip';
      s.innerHTML='<span><b>'+esc(lab)+':</b> '+esc(txt)+'</span>';
      var x=document.createElement('button'); x.type='button'; x.title='Clear this filter'; x.setAttribute('aria-label','Clear '+lab+' filter'); x.textContent='×';
      x.onclick=function(){delete filters[ci]; apply();};
      s.appendChild(x); box.appendChild(s);
    });
  }
  function apply(){
    var n=0,exp=0,cap=0,sup=0,opp=0,neu=0;
    rows.forEach(function(tr){var ok=rowOk(tr); tr.classList.toggle('hide',!ok);
      if(ok){n++; var ty=cell(tr,typeCol),st=cell(tr,stanceCol);
        if(ty==='Expense')exp++; else if(ty==='Capital')cap++;
        if(st==='Support')sup++; else if(st==='Oppose')opp++; else neu++;}});
    countEl.textContent=n+' / '+rows.length+' rows';
    setCard('requests',n);setCard('expense',exp);setCard('capital',cap);
    setCard('support',sup);setCard('oppose',opp);setCard('neutral',neu);
    ths.forEach(function(t,i){
      var fn=t.querySelector('.th-funnel'); if(fn) fn.classList.toggle('active',has(filters,i));
      var ar=t.querySelector('.th-arrow'); if(ar) ar.textContent=(sortCol===i)?(sortDir===1?' ▲':' ▼'):'';
    });
    renderNotice(); renderChips(); setStick();
    writeURL();
  }
  function doSort(ci,dir){
    sortCol=ci; sortDir=dir; var num=numeric[ci];
    var ms=document.getElementById('msort'); if(ms) ms.value=ci+'.'+(dir===1?'asc':'desc');
    rows.slice().sort(function(a,b){
      var x=cell(a,ci), y=cell(b,ci);
      if(num){var xn=parseFloat(x), yn=parseFloat(y), xa=isNaN(xn), ya=isNaN(yn);
        if(xa||ya) return (xa&&ya)? x.localeCompare(y) : (xa?1:-1);   // "CS" and blanks sort last either way
        return (xn-yn)*dir;}
      return x.localeCompare(y,undefined,{numeric:true})*dir;
    }).forEach(function(r){tbody.appendChild(r);});
    apply();
  }
  function distinct(ci){var seen={},out=[]; rows.forEach(function(tr){var v=cell(tr,ci); if(!has(seen,v)){seen[v]=1; out.push(v);}}); return out;}
  var menu=document.createElement('div'); menu.className='colmenu'; menu.style.display='none';
  document.body.appendChild(menu);
  menu.addEventListener('click',function(e){e.stopPropagation();});
  document.addEventListener('click',function(){menu.style.display='none'; var bp=document.getElementById('boardPanel'); if(bp)bp.style.display='none';});
  function mkBtn(txt,cls,fn){var b=document.createElement('button'); b.type='button'; b.className=cls; b.textContent=txt; b.onclick=fn; return b;}
  function openMenu(ci,thEl){
    menu.innerHTML='';
    var title=document.createElement('div'); title.className='cm-title'; title.textContent='Filter: '+(thEl.dataset.label||''); menu.appendChild(title);
    if(kindOf(ci)==='set'){
      var vals=distinct(ci).sort(function(a,b){return a.localeCompare(b,undefined,{numeric:true});});
      var cur=(has(filters,ci)&&filters[ci].type==='set')?filters[ci].allowed:null;
      var working={}; vals.forEach(function(v){working[v]=cur?has(cur,v):true;});
      function commit(){
        var on=vals.filter(function(v){return working[v];});
        if(on.length===vals.length) delete filters[ci];
        else {var al={}; on.forEach(function(v){al[v]=1;}); filters[ci]={type:'set',allowed:al};}
        apply();
      }
      var list=document.createElement('div'); list.className='cm-list';
      if(vals.length>8){
        var fs=document.createElement('input'); fs.className='cm-search'; fs.placeholder='filter values…';
        fs.oninput=function(){var t=fs.value.toLowerCase();
          [].forEach.call(list.children,function(o){o.style.display=o.dataset.v.toLowerCase().indexOf(t)>-1?'':'none';});};
        menu.appendChild(fs);
      }
      var ctrl=document.createElement('div'); ctrl.className='cm-ctrl';
      ctrl.appendChild(mkBtn('All','cm-mini',function(){vals.forEach(function(v){working[v]=true;});
        [].forEach.call(list.querySelectorAll('input'),function(c){c.checked=true;}); commit();}));
      ctrl.appendChild(mkBtn('None','cm-mini',function(){vals.forEach(function(v){working[v]=false;});
        [].forEach.call(list.querySelectorAll('input'),function(c){c.checked=false;}); commit();}));
      menu.appendChild(ctrl);
      vals.forEach(function(v){
        var row=document.createElement('label'); row.className='cm-opt'; row.dataset.v=v;
        var cb=document.createElement('input'); cb.type='checkbox'; cb.checked=working[v];
        cb.onchange=function(){working[v]=cb.checked; commit();};
        var sp=document.createElement('span'); sp.textContent=(v===''?'(blank)':v);
        row.appendChild(cb); row.appendChild(sp); list.appendChild(row);
      });
      menu.appendChild(list);
    } else {
      var inp=document.createElement('input'); inp.className='cm-search'; inp.placeholder='contains…';
      inp.value=(has(filters,ci)&&filters[ci].type==='text')?filters[ci].q:'';
      inp.oninput=function(){var t=inp.value.trim().toLowerCase(); if(t)filters[ci]={type:'text',q:t}; else delete filters[ci]; apply();};
      menu.appendChild(inp); setTimeout(function(){inp.focus();},0);
    }
    menu.appendChild(mkBtn('Clear column filter','cm-clear',function(){delete filters[ci]; apply(); menu.style.display='none';}));
    var r=thEl.getBoundingClientRect();
    menu.style.display='block';
    var maxL=window.scrollX+document.documentElement.clientWidth-menu.offsetWidth-8;
    menu.style.left=Math.max(8,Math.min(r.left+window.scrollX,maxL))+'px';
    menu.style.top=(r.bottom+window.scrollY+2)+'px';
  }
  function toggleSort(ci){ doSort(ci,(sortCol===ci&&sortDir===1)?-1:1); }
  ths.forEach(function(thEl,ci){
    var lbl=thEl.querySelector('.th-lbl'), fun=thEl.querySelector('.th-funnel');
    if(lbl) lbl.addEventListener('click',function(e){e.stopPropagation(); menu.style.display='none'; toggleSort(ci);});
    if(fun) fun.addEventListener('click',function(e){e.stopPropagation();
      if(menu.style.display==='block'&&menu.dataset.ci==ci){menu.style.display='none'; return;}
      menu.dataset.ci=ci; openMenu(ci,thEl);});
  });
  q.addEventListener('input',function(){rawTerm=q.value.trim(); term=rawTerm.toLowerCase(); apply();});
  var commSel=document.getElementById('commSel');
  if(commSel) commSel.addEventListener('change',function(){commFilter=commSel.value; apply();});
  var ySel=document.getElementById('yearSel');
  if(ySel){
    ySel.addEventListener('change',function(){var u=has(window.yearUrl,ySel.value)?window.yearUrl[ySel.value]:null; if(u) location.href=u+location.search;});
    // Coming Back from another year's page restores this page, including a stale menu value.
    window.addEventListener('pageshow',function(){ySel.value=FY;});
  }
  var msort=document.getElementById('msort');
  if(msort) msort.addEventListener('change',function(){if(!msort.value)return; var pr=msort.value.split('.'); doSort(+pr[0], pr[1]==='desc'?-1:1);});
  function boardLabel(){
    if(absentReq.length && boardPick.size===0) return absentReq.length===1?(has(boardName,absentReq[0])?boardName[absentReq[0]]:absentReq[0]):absentReq.length+' boards';
    if(boardPick.size===0||boardPick.size===bTotal) return 'All boards';
    if(boardPick.size===1) return boardName[Array.from(boardPick)[0]]||'1 board';
    return boardPick.size+' boards';
  }
  function updBoard(){
    var bb=document.getElementById('boardBtn'); if(bb) bb.innerHTML=esc(boardLabel())+' ▾';
    var only=(boardPick.size===1)?Array.from(boardPick)[0]:((boardPick.size===0&&absentReq.length===1)?absentReq[0]:null);
    var lk=document.getElementById('stmtLink');
    if(lk){ var one=(boardPick.size===1)?Array.from(boardPick)[0]:null;
      lk.href=(one&&has(boardPdf,one))?boardPdf[one]:repoUrl;
      lk.textContent='FY'+FY+(one?' Statement PDF':' Statement PDFs'); }
    var h1b=document.getElementById('h1board');
    if(h1b) h1b.textContent=only?(has(boardFull,only)?boardFull[only]:'Community Board'):((boardPick.size===0||boardPick.size===bTotal)?'NYC Community Boards':(boardPick.size+' Community Boards'));
    apply();
  }
  boxes.forEach(function(c){
    c.addEventListener('change',function(){ absentReq=[]; if(c.checked)boardPick.add(c.value); else boardPick.delete(c.value); updBoard(); });
  });
  [].forEach.call(document.querySelectorAll('#boardPanel .cm-mini'),function(b){
    b.addEventListener('click',function(){ var on=b.dataset.act==='all'; absentReq=[];
      boxes.forEach(function(c){c.checked=on; if(on)boardPick.add(c.value); else boardPick.delete(c.value);});
      updBoard(); });
  });
  var bSearch=document.getElementById('boardSearch');
  if(bSearch) bSearch.addEventListener('input',function(){ var t=bSearch.value.toLowerCase();
    [].forEach.call(document.querySelectorAll('#boardList .cm-opt'),function(o){o.style.display=(o.dataset.name||'').toLowerCase().indexOf(t)>-1?'':'none';}); });
  var bBtn=document.getElementById('boardBtn');
  if(bBtn) bBtn.addEventListener('click',function(e){e.stopPropagation(); var pp=document.getElementById('boardPanel'); pp.style.display=pp.style.display==='none'?'block':'none';});
  var bPanel=document.getElementById('boardPanel'); if(bPanel) bPanel.addEventListener('click',function(e){e.stopPropagation();});
  function csvCell(s){s=(s==null?'':String(s)).replace(/\s+/g,' ').trim();
    if(/^[=+\-@]/.test(s)) s="'"+s;                      // keep spreadsheets from reading text as a formula
    return /[",]/.test(s)?('"'+s.replace(/"/g,'""')+'"'):s;}
  function downloadCSV(){
    var cols=ths.map(function(t){return t.dataset.label;}).concat(['Committees']);
    var lines=[cols.map(csvCell).join(',')];
    [].forEach.call(tbody.children,function(tr){ if(tr.classList.contains('hide')) return;   // current sort order
      var c=[]; for(var i=0;i<ths.length;i++) c.push(csvCell(cell(tr,i)));
      c.push(csvCell((tr.dataset.committees||'').split('|').join('; ')));
      lines.push(c.join(',')); });
    var blob=new Blob(['﻿'+lines.join('\r\n')],{type:'text/csv;charset=utf-8;'});
    var url=URL.createObjectURL(blob), a=document.createElement('a');
    var who=(boardPick.size===1)?Array.from(boardPick)[0]:'NYC_community_boards';
    a.href=url; a.download=who+'_FY'+FY+'_'+(commFilter?commFilter.replace(/[^a-z0-9]+/gi,'_'):'requests')+'.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function(){URL.revokeObjectURL(url);},1500);
  }
  var dlBtn=document.getElementById('dlBtn'); if(dlBtn) dlBtn.addEventListener('click',downloadCSV);
  function setStick(){var c=document.querySelector('.controls'); if(c) document.documentElement.style.setProperty('--ch', c.offsetHeight+'px');}
  window.addEventListener('resize', setStick);
  if(window.ResizeObserver){var ctl=document.querySelector('.controls'); if(ctl) new ResizeObserver(setStick).observe(ctl);}
  var urlReady=false;
  function colKey(i){return 'c_'+(ths[i].dataset.label||'').toLowerCase().replace(/[^a-z0-9]+/g,'');}
  function writeURL(){
    if(!urlReady) return;
    var p=new URLSearchParams();
    if(absentReq.length) p.set('board',Array.from(boardPick).concat(absentReq).join(','));
    else if(boardPick.size===0||boardPick.size===bTotal) p.set('board','all');
    else if(boardPick.size>bTotal/2){          // "all but a few" survives a switch to a year with other boards
      p.set('board','all');
      p.set('xboard',boxes.filter(function(c){return !boardPick.has(c.value);}).map(function(c){return c.value;}).join(','));
    } else p.set('board',Array.from(boardPick).join(','));
    if(rawTerm) p.set('q',rawTerm);
    if(commFilter) p.set('committee',commFilter);
    ths.forEach(function(t,i){if(!has(filters,i)) return; var f=filters[i], k=colKey(i);
      if(f.type==='set'){var v=Object.keys(f.allowed); if(!v.length) p.append(k,'__none__'); v.forEach(function(x){p.append(k,x);});}
      else if(f.type==='text'){p.set(k,f.q);}});
    if(sortCol>=0) p.set('sort',colKey(sortCol).slice(2)+(sortDir===1?'.asc':'.desc'));
    var qs=p.toString();
    try{history.replaceState(null,'',(qs?('?'+qs):location.pathname)+location.hash);}catch(e){}
  }
  function readURL(){
    var p=new URLSearchParams(location.search);
    // compat: map v2-card-explorer params onto the column filters
    if(p.has('agency')&&!p.has('c_agency')) p.set('c_agency',p.get('agency'));
    if(p.has('type')&&!p.has('c_type')) p.set('c_type',p.get('type'));
    if(p.has('stance')&&!p.has('c_agencystance'))
      p.set('c_agencystance',p.get('stance')==='Neutral'?'Neutral/Unclear':p.get('stance'));
    if(p.has('sort')&&p.get('sort').indexOf('stance.')===0) p.set('sort','agency'+p.get('sort'));
    if(p.has('board')){
      var bv=p.get('board').toUpperCase(), req=bv.split(',').map(function(s){return s.trim();}).filter(Boolean);
      boardPick=new Set(); absentReq=[];
      if(bv==='ALL'){
        var ex={}; (p.get('xboard')||'').toUpperCase().split(',').forEach(function(s){if(s)ex[s.trim()]=1;});
        boxes.forEach(function(c){if(!has(ex,c.value)) boardPick.add(c.value);});
      } else req.forEach(function(b){ if(has(present,b)) boardPick.add(b); else if(has(boardName,b)) absentReq.push(b); });
      boxes.forEach(function(c){c.checked=boardPick.has(c.value);});
    }
    if(p.has('q')){ rawTerm=p.get('q').trim(); term=rawTerm.toLowerCase(); q.value=rawTerm; }
    if(p.has('committee')&&commSel){ var want=p.get('committee').toLowerCase();
      [].forEach.call(commSel.options,function(o){ if(o.value&&o.value.toLowerCase()===want){commFilter=o.value; commSel.value=o.value;} }); }
    var slug2ci={}; ths.forEach(function(t,i){slug2ci[colKey(i)]=i;});
    Object.keys(slug2ci).forEach(function(k){ if(!p.has(k)) return;
      var ci=slug2ci[k], vals=p.getAll(k);
      if(kindOf(ci)==='set'){var al={}; vals.forEach(function(v){if(v!=='__none__') al[v]=1;}); filters[ci]={type:'set',allowed:al};}
      else if(vals[0]) {filters[ci]={type:'text',q:vals[0].toLowerCase()};}
    });
    if(p.has('sort')){var sp=p.get('sort'), dot=sp.lastIndexOf('.'),
      sl=(dot>0?sp.slice(0,dot):sp), dir=(dot>0&&sp.slice(dot+1)==='desc')?-1:1,
      sci=slug2ci['c_'+sl]; if(sci!=null) doSort(sci,dir);}
  }
  boxes.forEach(function(c){ if(c.checked) boardPick.add(c.value); });
  readURL(); urlReady=true;
  updBoard();
})();
</script>
</body></html>
"""

# ?year=2026&board=QCB2 style links: jump to that year's page before the table loads.
YEAR_REDIRECT = ("<script>(function(){var p=new URLSearchParams(location.search),y=p.get('year');"
                 "if(!y)return;var U=" + json.dumps(YEAR_URL) + ";p.delete('year');var qs=p.toString();"
                 "if(y!=='" + FY + "'&&Object.prototype.hasOwnProperty.call(U,y))location.replace(U[y]+(qs?'?'+qs:'')+location.hash);"
                 "else history.replaceState(null,'',location.pathname+(qs?'?'+qs:'')+location.hash);})();</script>")
STMT = f'<a id="stmtLink" href="{REPO_URL}" target="_blank" rel="noopener">FY{FY} Statement PDFs</a>'
REG = f'<a href="{REG_URL}" target="_blank" rel="noopener">Register of Community Board Budget Requests</a>'
if FROM_PDF:
    SOURCE = (f"The <b>Agency Response</b> comes from each board's {STMT}, and the <b>OMB Executive Response</b> "
              f"from NYC Open Data's {REG}.")
else:
    SOURCE = (f"The <b>Agency Response</b> and the <b>OMB Executive Response</b> both come from NYC Open Data's {REG}. "
              f"Titles are DCP's standard request categories, since boards' own titles begin in FY2026. "
              f"Agencies then mostly answered with standard phrases that take no position, so most stances read "
              f"Neutral/Unclear. For reference, see the {STMT}.")
CONTACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts")


def load_contacts():
    """The follow-up letters' recipients: each board's Council Members (by share of the
    board's land area), its Borough President, and each agency's offices. See
    pipeline/contacts/README.md for sources."""
    def rd(name):
        p = os.path.join(CONTACTS_DIR, name)
        return pd.read_csv(p, dtype=str).fillna("").to_dict("records") if os.path.exists(p) else []
    office = lambda r: {"borough": r.get("borough", ""), "office": r.get("office", ""), "person": r.get("person", ""),
                        "title": r.get("title", ""), "email": r.get("email", ""), "form": r.get("form_url", ""),
                        "phone": r.get("phone", ""), "src": r.get("source_url", ""), "role": r.get("role", ""),
                        "boards": [b for b in r.get("boards", "").split("|") if b]}
    out = {"council": {}, "boardCouncil": {}, "bp": {}, "agency": {}, "asOf": ""}
    for r in rd("council_members.csv"):
        out["council"][r["council_district"]] = {"name": r["name"], "salutation": r["salutation"],
                                                 "email": r["email"], "url": r["url"]}
        out["asOf"] = max(out["asOf"], r.get("as_of", ""))
    for r in rd("board_council_districts.csv"):
        out["boardCouncil"].setdefault(r["board"], []).append([int(r["council_district"]), float(r["share"])])
    for r in rd("borough_presidents.csv"):
        out["bp"].setdefault(r["borough"], []).append(office(r))
    for r in rd("agency_contacts.csv"):
        out["agency"].setdefault(r["agency"], []).append(office(r))
    return out


FU_MODAL = """<div id="fuModal" class="fu-ov" hidden>
<div class="fu-box" role="dialog" aria-modal="true" aria-labelledby="fuTitle">
<div class="fu-head"><h2 id="fuTitle"></h2><button type="button" class="fu-x" aria-label="Close">&times;</button></div>
<div id="fuMeta" class="fu-meta"></div>
<div class="fu-sec"><div class="fu-h">Recipients</div><div id="fuRecips"></div></div>
<div class="fu-sec fu-row"><label><input type="radio" name="fuMode" value="each" checked> A separate letter for each recipient</label>
<label><input type="radio" name="fuMode" value="joint"> One letter to all</label></div>
<div class="fu-sec fu-row"><input id="fuName" class="fu-in" placeholder="Your name" autocomplete="name">
<input id="fuRole" class="fu-in" placeholder="Your title (for example, Chair)"></div>
<div id="fuLetters"></div>
<p class="fu-note">Each draft quotes the request and the city's responses. Review and edit it before sending.
Changing recipients redrafts the letters, so edit last. Contacts come from official city websites
(<span id="fuAsOf"></span>); check them before relying on them.</p>
</div></div>"""

FU_SCRIPT = r"""
<script>
(function(){
  var dlg=document.getElementById('fuModal'); if(!dlg) return;
  var C=window.contacts||{}; ['council','boardCouncil','bp','agency'].forEach(function(k){ if(!C[k]) C[k]={}; });
  var FY=window.pageYear, boardFull=window.boardFull||{}, boardName=window.boardName||{};
  var ths=[].slice.call(document.querySelectorAll('table thead th')), col={};
  ths.forEach(function(t,i){ col[t.dataset.label]=i; });
  var BORO={M:'Manhattan',BX:'Bronx',BK:'Brooklyn',Q:'Queens',SI:'Staten Island'};
  var SKEY='cbFollowupSender', cur=null, list=[], mode='each', lastFocus=null;
  function boroOf(b){ var m=/^(BX|BK|SI|M|Q)CB\d+$/.exec(b||''); return m?BORO[m[1]]:''; }
  function val(tr,label){ var i=col[label]; if(i==null) return ''; var td=tr.children[i], v=td.getAttribute('data-v');
    return (v!==null?v:td.textContent).replace(/\s+/g,' ').trim(); }
  function clip(s,max){ s=(s||'').replace(/\s+/g,' ').trim(); if(s.length<=max) return s;
    var c=s.slice(0,max), d=c.lastIndexOf('. '); return d>max*0.5?c.slice(0,d+1):c.replace(/\s+\S*$/,'')+'…'; }
  function lead(s,n,max){ s=(s||'').replace(/\s+/g,' ').trim(); if(!s) return '';
    var parts=s.match(/[^.!?]+(?:[.!?]+|$)/g)||[s]; return clip(parts.slice(0,n).join('').trim(),max); }
  function andList(a){ return a.length<2?a.join(''):a.slice(0,-1).join(', ')+' and '+a[a.length-1]; }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
  function reach(o){ return !!(o&&(o.email||o.form)); }
  function agencyPhrase(a){ return a==='Other'||!a?'a city agency':'the '+a; }
  function loadSender(){ try{ return JSON.parse(localStorage.getItem(SKEY)||'{}')||{}; }catch(e){ return {}; } }
  function saveSender(){ try{ localStorage.setItem(SKEY,JSON.stringify({name:fuName.value,role:fuRole.value})); }catch(e){} }

  function request(tr){
    var pill=tr.querySelector('.fu-pill');
    return {board:tr.dataset.board||'', full:boardFull[tr.dataset.board]||tr.dataset.board||'the community board',
      boro:boroOf(tr.dataset.board), pri:val(tr,'Priority'), type:val(tr,'Type'), agency:val(tr,'Agency'),
      title:val(tr,'Title'), expl:val(tr,'Explanation'), ar:val(tr,'Agency Response'), omb:val(tr,'OMB Executive Response'),
      action:val(tr,'Follow-up'), why:pill?pill.title:'', purpose:tr.dataset.fp||'', named:tr.dataset.fc||'',
      url:tr.dataset.fu||'', tc:tr.dataset.tc||''};
  }
  function recipients(r){
    var out=[], a=r.action;
    var wantA=/^(Contact agency|Track with agency)/.test(a), wantE=/elected officials$/.test(a);
    // An agency's offices for this board: its own contact when the agency assigns staff by
    // board, the borough office, then a citywide liaison, then the head. Press offices and
    // contacts for a single facility or school district are listed but never pre-selected.
    var offs=(C.agency[r.agency]||[]).filter(function(o){ return (!o.borough||o.borough===r.boro)&&(reach(o)||o.phone)&&
      (!o.boards||!o.boards.length||o.boards.indexOf(r.board)>-1); });
    var rank=function(o){ if(!reach(o)) return 9; if(o.boards&&o.boards.indexOf(r.board)>-1) return 0;
      return {borough:1, liaison:2, head:3}[o.role]||8; };
    offs.sort(function(a,b){ return rank(a)-rank(b); });
    var pick=offs.filter(function(o){ return rank(o)<4; })[0];
    offs.forEach(function(o){
      out.push({kind:'agency', o:o, label:r.agency+', '+o.office+(o.person?' ('+o.person+')':''), on:wantA&&o===pick}); });
    (C.boardCouncil[r.board]||[]).forEach(function(p){ var m=C.council[String(p[0])]; if(!m) return;
      out.push({kind:'council', o:m, label:m.salutation+', District '+p[0]+' (covers '+Math.round(p[1]*100)+'% of the board’s area)',
                on:wantE&&p[1]>=0.1}); });
    var bps=C.bp[r.boro]||[], lead=bps.filter(isBP)[0]||bps[0];
    bps.forEach(function(b){
      out.push({kind:'bp', o:b, label:isBP(b)?'Borough President'+(b.person?' '+b.person:''):r.boro+' Borough President\u2019s office, '+b.office+(b.person?' ('+b.person+')':''),
                on:wantE&&b===lead}); });
    return out;
  }
  function isBP(o){ return o.role==='head'||/^Borough President$/i.test(o.office||''); }
  function bpName(o){ return isBP(o)?'Borough President'+(o.person?' '+o.person:''):(o.person||'colleagues at the Borough President\u2019s office'); }
  function salute(x,r){
    if(x.kind==='council') return x.o.salutation;
    if(x.kind==='bp') return bpName(x.o);
    if(x.o.person){ var t=x.o.title||(/(Commissioner|Chancellor|Director|Chair|President)$/.test(x.o.office||'')?x.o.office:'');
      return (t?t+' ':'')+x.o.person; }
    return 'colleagues at '+agencyPhrase(r.agency);
  }
  function agencyAsk(r,direct){
    var Y=direct?'Your response':'The response from '+agencyPhrase(r.agency);
    switch(r.purpose){
      case 'clarify': return Y+' says the agency needs more information about this request. We would like to provide it. Please tell us what information would help, or suggest a time for board members to discuss the request with the right staff.';
      case 'study': return Y+' says the agency needs to study this request further. Please tell us where that review stands and when you expect to finish it. We can provide any information that would help.';
      case 'discuss': return Y+' asks the board to contact the agency about this request. We would like to discuss it with the right staff. Please tell us whom to contact and when they are available.';
      case 'reconsider': return 'We understand the agency does not support this request at this time. The need remains a priority for our district. Please explain the agency’s reasons in more detail and tell us what would allow it to reconsider the request in the next budget cycle.';
      case 'funding': return Y+' indicates that funding is the obstacle to this request. Please share the estimated cost and the funding the agency would need to proceed.';
      case 'advocacy': return Y+' indicates that this request needs a decision beyond the agency. Please tell us which office or level of government would need to act, and what the board can do to help.';
      case 'status': return 'Thank you for the agency’s response. Please tell us the current status of this request, the expected timeline and whom we should contact for updates.';
      case 'channel': return Y+' directs the board to '+(r.url||'311')+'. We will use that process. Please tell us if the board should take any other step.';
      case 'no_response': return 'We could not find a published response to this request in the Statement of Community District Needs or in the City’s Register of Community Board Budget Requests. Please tell us the agency’s position on the request.';
      default: return 'Please tell us the current status of this request and whether any work remains.';
    }
  }
  function electedAsk(r,els,joint){
    var who=andList(els.map(function(x){ return x.kind==='bp'?bpName(x.o):x.o.salutation; }));
    if(r.purpose==='advocacy'){
      var adv=(joint?'We ask '+who+' to consider':'We ask that you consider')+' supporting this request with '+agencyPhrase(r.agency)+', including any legislation or policy change it requires.';
      return joint?adv:'The response from '+agencyPhrase(r.agency)+' indicates that this request needs a decision beyond the agency. '+adv;
    }
    if(r.purpose==='funding'||/elected officials$/.test(r.action)){
      var money=r.type==='Capital'?'allocating capital funds (Reso A) to this project':'providing discretionary funding for this need';
      var ask=(joint?'We ask '+who+' to consider ':'We ask that you consider ')+money+' and advocating for it with '+agencyPhrase(r.agency)+' and OMB in the next budget.';
      return joint?ask:'The response from '+agencyPhrase(r.agency)+' indicates that funding is the obstacle to this request. '+ask;
    }
    return (joint?'We ask '+who+' to help us':'We would appreciate your office’s help')+' in getting a response from '+agencyPhrase(r.agency)+' and moving this request forward.';
  }
  function subject(r){ return 'FY'+FY+' '+(r.type?r.type.toLowerCase()+' ':'')+'budget request, '+clip(r.title,70)+' ('+(boardName[r.board]||r.board)+(r.tc?', '+r.tc:'')+')'; }
  function letter(r,xs){
    var ag=xs.filter(function(x){return x.kind==='agency';}), el=xs.filter(function(x){return x.kind!=='agency';});
    var joint=ag.length>0&&el.length>0;
    var ids=[r.pri?'priority '+r.pri:'', r.tc?'tracking code '+r.tc:''].filter(Boolean).join(', ');
    var kindWord=(r.type?r.type.toLowerCase()+' ':'')+'request', art=/^[aeiou]/.test(kindWord)?'an ':'a ';
    var p1='In its FY'+FY+' budget requests, '+r.full+' submitted '+art+kindWord+' to '+agencyPhrase(r.agency)+' titled “'+r.title+'”'+(ids?' ('+ids+')':'')+'.';
    if(r.expl) p1+=' The request reads, “'+clip(r.expl,320)+'”';
    var ar=lead(r.ar,2,360), echo=!r.omb||/^OMB supports the agency.s position/i.test(r.omb);
    var p2=ar?(r.agency&&r.agency!=='Other'?'The '+r.agency:'The agency')+' responded, “'+ar+'”':'We could not find a published response from '+agencyPhrase(r.agency)+'.';
    if(!echo) p2+=' In the Executive Budget, OMB responded, “'+lead(r.omb,2,300)+'”';
    var asks=[]; if(ag.length) asks.push(agencyAsk(r,!joint)); if(el.length) asks.push(electedAsk(r,el,joint));
    var s={name:fuName.value.trim(), role:fuRole.value.trim()};
    var lines=['Dear '+andList(xs.map(function(x){return salute(x,r);}))+',','',p1,'',p2,''];
    asks.forEach(function(a){ lines.push(a,''); });
    lines.push('Thank you for your attention to this request.','','Sincerely,',s.name||'[Your name]',s.role||'[Your title]',r.full);
    return lines.join('\n');
  }
  function contactBits(o){
    var b=[]; if(o.email) b.push('<a href="mailto:'+esc(o.email)+'">'+esc(o.email)+'</a>');
    if(o.form) b.push('<a href="'+esc(o.form)+'" target="_blank" rel="noopener">contact form</a>');
    if(o.phone) b.push(esc(o.phone)); var u=o.url||o.src; if(u) b.push('<a href="'+esc(u)+'" target="_blank" rel="noopener">source</a>');
    return b.join(' · ');
  }
  function renderRecips(){
    var box=document.getElementById('fuRecips'); box.innerHTML='';
    if(!list.length){ box.innerHTML='<p class="fu-empty">No contacts are on file for this request.</p>'; return; }
    var heads={agency:'Agency',council:'Council Members',bp:'Borough President'}, last='';
    list.forEach(function(x,i){
      if(x.kind!==last){ var h=document.createElement('div'); h.className='fu-sub'; h.textContent=heads[x.kind]; box.appendChild(h); last=x.kind; }
      var l=document.createElement('label'); l.className='fu-rcp';
      l.innerHTML='<input type="checkbox" data-i="'+i+'"'+(x.on?' checked':'')+'><span><b>'+esc(x.label)+'</b><br><small>'+(contactBits(x.o)||'no email or form on file')+'</small></span>';
      box.appendChild(l);
    });
  }
  function renderLetters(){
    var box=document.getElementById('fuLetters'); box.innerHTML='';
    var sel=list.filter(function(x){return x.on;});
    if(!sel.length){ box.innerHTML='<p class="fu-empty">Select at least one recipient to draft a letter.</p>'; return; }
    var groups=mode==='joint'?[sel]:sel.map(function(x){return [x];});
    groups.forEach(function(g){
      var emails=g.map(function(x){return x.o.email;}).filter(Boolean), forms=g.filter(function(x){return !x.o.email&&x.o.form;});
      var w=document.createElement('div'); w.className='fu-letter';
      w.innerHTML='<div class="fu-to"><b>To</b> '+esc(g.map(function(x){return x.label.split(' (')[0];}).join('; '))+'</div>'+
        '<input class="fu-subj fu-in" aria-label="Subject">'+'<textarea class="fu-body" rows="14" aria-label="Letter"></textarea>'+
        '<div class="fu-acts"><button type="button" class="fu-act fu-copy">Copy letter</button>'+
        (emails.length?'<a class="fu-act fu-mail" href="#">Open in email</a>':'')+
        forms.map(function(x){return '<a class="fu-act" href="'+esc(x.o.form)+'" target="_blank" rel="noopener">Open '+esc(x.label.split(',')[0])+' contact form</a>';}).join('')+
        '<span class="fu-copied" hidden>Copied</span></div>';
      box.appendChild(w);
      var subj=w.querySelector('.fu-subj'), body=w.querySelector('.fu-body');
      subj.value=subject(cur); body.value=letter(cur,g);
      w.querySelector('.fu-copy').addEventListener('click',function(){
        var t=body.value, done=function(){ var c=w.querySelector('.fu-copied'); c.hidden=false; setTimeout(function(){c.hidden=true;},1500); };
        if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done,function(){ body.select(); document.execCommand('copy'); done(); });
        else { body.select(); document.execCommand('copy'); done(); }
      });
      var m=w.querySelector('.fu-mail');
      if(m) m.addEventListener('click',function(e){ e.preventDefault();
        location.href='mailto:'+emails.join(',')+'?subject='+encodeURIComponent(subj.value)+'&body='+encodeURIComponent(body.value.replace(/\n/g,'\r\n')); });
    });
  }
  function open(tr){
    cur=request(tr); list=recipients(cur); lastFocus=document.activeElement;
    document.getElementById('fuTitle').textContent=cur.title||'Follow up';
    var meta='<span class="pill fu-pill fu-'+({'Contact agency':'a','Contact elected officials':'e','Contact agency and elected officials':'ae','Track with agency':'t','Use 311 or another channel':'c','No follow-up needed':'n'}[cur.action]||'n')+'">'+esc(cur.action||'No label')+'</span> '+esc(cur.why);
    meta+='<div class="fu-small">'+esc(cur.full)+' · FY'+esc(FY)+' '+esc(cur.type)+(cur.pri?' priority '+esc(cur.pri):'')+(cur.tc?' · tracking code '+esc(cur.tc):'')+' · '+esc(cur.agency)+'</div>';
    if(cur.named) meta+='<div class="fu-small">The response names this contact: '+esc(cur.named)+'</div>';
    if(cur.url) meta+='<div class="fu-small">The response links to <a href="'+esc(cur.url)+'" target="_blank" rel="noopener">'+esc(clip(cur.url,80))+'</a></div>';
    if(cur.action==='Use 311 or another channel') meta+='<div class="fu-small"><a href="'+esc(cur.url||'https://portal.311.nyc.gov/')+'" target="_blank" rel="noopener">'+(cur.url?'Open the channel the response names':'Open 311')+'</a></div>';
    if(cur.action==='No follow-up needed') meta+='<div class="fu-small">No follow-up is needed. Select a recipient to draft a letter anyway.</div>';
    document.getElementById('fuMeta').innerHTML=meta;
    document.getElementById('fuAsOf').textContent=C.asOf?'council contacts as of '+C.asOf:'as published';
    renderRecips(); renderLetters(); dlg.hidden=false; document.body.classList.add('fu-lock');
    dlg.querySelector('.fu-x').focus();
  }
  function close(){ dlg.hidden=true; document.body.classList.remove('fu-lock'); if(lastFocus&&lastFocus.focus) lastFocus.focus(); }
  var fuName=document.getElementById('fuName'), fuRole=document.getElementById('fuRole'), s0=loadSender();
  fuName.value=s0.name||''; fuRole.value=s0.role||'';
  [fuName,fuRole].forEach(function(el){ el.addEventListener('change',function(){ saveSender(); if(cur) renderLetters(); }); });
  document.addEventListener('click',function(e){ var b=e.target.closest&&e.target.closest('.fu-btn'); if(b){ open(b.closest('tr')); } });
  document.getElementById('fuRecips').addEventListener('change',function(e){ var i=e.target.getAttribute('data-i'); if(i===null) return; list[+i].on=e.target.checked; renderLetters(); });
  [].forEach.call(document.querySelectorAll('input[name=fuMode]'),function(r){ r.addEventListener('change',function(){ mode=r.value; renderLetters(); }); });
  dlg.querySelector('.fu-x').addEventListener('click',close);
  dlg.addEventListener('click',function(e){ if(e.target===dlg) close(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'&&!dlg.hidden) close(); });
})();
</script>
"""

parts = [HEAD, YEAR_REDIRECT, '<header>']
parts.append(f'<h1><span id="h1board">Queens Community Board 2</span> &mdash; FY{FY} Budget Requests &amp; Agency Responses</h1>')
parts.append(f'<p class="sub">{SOURCE}{YEAR_NOTE.get(FY, "")}</p>')
parts.append('<div class="cards">')
for k, key in [("Requests", "requests"), ("Expense", "expense"), ("Capital", "capital"),
               ("Support", "support"), ("Oppose", "oppose"), ("Neutral/Unclear", "neutral")]:
    parts.append(f'<div class="card"><div class="k">{k}</div><div class="v" data-card="{key}">0</div></div>')
parts.append('</div>')
parts.append('</header>')

parts.append('<div class="controls">')
parts.append('<select id="yearSel" class="commsel" title="Fiscal year" aria-label="Fiscal year" autocomplete="off">'
             + "".join(f'<option value="{y}"{" selected" if y == FY else ""}>FY{y}</option>' for y in YEARS)
             + '</select>')
parts.append('<input id="q" type="search" placeholder="Search all columns…">')
parts.append('<div class="bsel"><button id="boardBtn" class="commsel boardbtn" title="Filter by community board">Queens CB2 &#9662;</button>'
             '<div id="boardPanel" class="boardpanel" style="display:none">'
             '<input id="boardSearch" class="cm-search" placeholder="search boards…">'
             '<div class="cm-ctrl"><button type="button" class="cm-mini" data-act="all">All</button>'
             '<button type="button" class="cm-mini" data-act="none">None</button></div>'
             '<div class="cm-list" id="boardList">' + board_checklist + '</div></div></div>')
parts.append('<select id="commSel" class="commsel" '
             'title="Filter by committee (CB2 taxonomy). Queens CB2 FY2027: as submitted via '
             'CB2\'s committee form. Everything else: assigned by a model following CB2\'s '
             'committee definitions.">'
             '<option value="">All committees</option>'
             + "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in committees_list)
             + '</select>')
_msort_opts = "".join(
    f'<option value="{i}.asc">{html.escape(LABEL.get(c, c))} ↑</option>'
    f'<option value="{i}.desc">{html.escape(LABEL.get(c, c))} ↓</option>'
    for i, c in enumerate(DISPLAY))
parts.append('<select id="msort" class="commsel msort" title="Sort rows" aria-label="Sort rows">'
             '<option value="">Sort by…</option>' + _msort_opts + '</select>')
parts.append('<button id="dlBtn" class="dlbtn" title="Download the current filtered view as CSV">&#8595; Download CSV</button>')
parts.append(f'<span class="hint">Click a column name to sort; click its {FUNNEL} to filter</span>')
parts.append('<span id="count" class="count"></span>')
parts.append('</div>')
parts.append('<div id="notice" class="notice" style="display:none" role="status"></div>')
parts.append('<div id="chips" class="chips" aria-label="Active column filters"></div>')

parts.append('<div class="wrap"><table>' + colgroup + '<thead><tr>' + header_cells + '</tr></thead><tbody>')
parts.extend(body)
parts.append('</tbody></table></div>')
parts.append('<script>window.pageYear=' + json.dumps(FY) + ';window.boardPdf=' + json.dumps(board_pdf)
             + ';window.repoUrl=' + json.dumps(REPO_URL) + ';window.boardName=' + json.dumps(board_name)
             + ';window.boardFull=' + json.dumps(board_full) + ';window.yearUrl=' + json.dumps(YEAR_URL)
             + ';window.filterKind=' + json.dumps(FILTER_KIND) + ';window.contacts=' + json.dumps(load_contacts())
             + ';</script>')
parts.append(SCRIPT)
parts.append(FU_MODAL)
parts.append(FU_SCRIPT)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))

print(f"Wrote {OUT}  ({len(df)} rows, {len(DISPLAY)} columns)")
