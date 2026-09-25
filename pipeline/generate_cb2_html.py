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
for _c in FOLLOWUP_COLS + ["Tracking Code", "Label ID", "History Years", "Prior Response",
                           "Location Districts", "Location Match"]:   # older CSVs lack some of these
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
                           + (f'<span class="fu-dest">{html.escape(clean_text(r["Follow-up Agency"]))}</span>'
                              if str(r["Follow-up Agency"]).strip() else "")
                           + '<button type="button" class="fu-btn">Draft letter</button></div></td>')
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
                        ("data-fc", "Follow-up Contact"), ("data-fu", "Follow-up URL"),
                        ("data-fa", "Follow-up Agency"), ("data-id", "Label ID"), ("data-hy", "History Years"),
                        ("data-pr", "Prior Response"), ("data-cd", "Location Districts"),
                        ("data-cw", "Location Match")] if str(r[c]).strip())
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
.fu-dest{font-size:11px;color:var(--mut);line-height:1.25}
.fu-dest::before{content:"\u2192 "}
.fu-btn{border:1px solid #cbd5e1;background:#fff;border-radius:6px;padding:2px 8px;font-size:11px;cursor:pointer;color:#0f172a}
.fu-btn:hover{background:#eef2ff;border-color:#a5b4fc}
.fu-ov{position:fixed;inset:0;background:rgba(15,23,42,.45);display:flex;align-items:flex-start;justify-content:center;
  z-index:60;padding:32px 16px;overflow:auto}
.fu-ov[hidden],.fu-ov [hidden]{display:none!important}
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
.fu-cards{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.fu-card{display:flex;flex-direction:column;align-items:flex-start;text-align:left;gap:1px;border:1px solid transparent;border-radius:8px;padding:5px 9px;font:inherit;font-size:11px;cursor:pointer;min-width:0}
.fu-card b{font-size:15px}
.fu-card.on{border-color:currentColor;box-shadow:0 0 0 1px currentColor inset}
.fu-card.fu-sentcount{background:#f0fdf4;color:#166534;cursor:default}
.fu-digest{align-self:center;margin-left:auto;border:1px solid #2563eb;background:#2563eb;color:#fff;border-radius:8px;padding:8px 12px;font:inherit;font-size:13px;font-weight:600;cursor:pointer}
.fu-digest:disabled{background:#94a3b8;border-color:#94a3b8;cursor:default}
.fu-sent{font-size:11px;color:#166534;font-weight:600}
.fu-sent::before{content:"\u2713 "}
.fu-sentnote{color:#166534}
.fu-warn{font-size:12px;color:#92400e;margin-top:4px}
.fu-add{margin-top:6px;font-size:12.5px}
.fu-add summary{cursor:pointer;color:#1d4ed8}
.fu-add .fu-row{margin:6px 0 2px}
.fu-link{border:0;background:none;color:#b42318;cursor:pointer;padding:0;font:inherit;font-size:12px;text-decoration:underline}
.fu-act.fu-sentbtn{background:#f0fdf4;color:#166534;border-color:#86efac}
#fuSel{max-width:230px}
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
  /* On a phone the follow-up comes right after the title, above the long texts. */
  tr:not(.hide){display:flex;flex-direction:column}
  td{order:3} td:nth-child(-n+5){order:1} td.fu-td{order:2;border-bottom:1px solid #f1f5f9} td:nth-last-child(2){border-bottom:0}
  #fuSel{flex:1 1 100%;max-width:none}
  .fu-digest{margin-left:0;flex:1 1 100%}
  .fu-card{flex:1 1 30%}
}
</style></head><body>
"""
HEAD = HEAD.replace("__FY__", FY)

SCRIPT = r"""
<script>
(function(){
  window.cbInitialSearch=location.search;
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
    if(window.cbRowFilter && !window.cbRowFilter(tr)) return false;
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
    try{ document.dispatchEvent(new CustomEvent('cb:applied')); }catch(e){}
  }
  // For the follow-up controls: read and set a column's checkbox filter, and count a
  // column's values over the rows every other filter keeps.
  window.cbTable={
    col:function(label){ for(var i=0;i<ths.length;i++) if(ths[i].dataset.label===label) return i; return -1; },
    getSet:function(label){ var f=filters[this.col(label)]; return f&&f.type==='set'?Object.keys(f.allowed):null; },
    setSet:function(label,vals){ var ci=this.col(label); if(ci<0) return;
      if(vals){ var al={}; vals.forEach(function(v){al[v]=1;}); filters[ci]={type:'set',allowed:al}; } else delete filters[ci];
      apply(); },
    countBy:function(label,extra){ var ci=this.col(label), saved=filters[ci], rf=window.cbRowFilter, out={};
      delete filters[ci]; window.cbRowFilter=null;
      rows.forEach(function(tr){ if(rowOk(tr)){ var v=cell(tr,ci); out[v]=(out[v]||0)+1; if(extra&&extra(tr)) out.__extra=(out.__extra||0)+1; } });
      if(saved) filters[ci]=saved; window.cbRowFilter=rf; return out; },
    visible:function(){ return rows.filter(function(tr){ return !tr.classList.contains('hide'); }); },
    apply:function(){ apply(); }
  };
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
    var ex=window.cbCsvExtras;
    var cols=ths.map(function(t){return t.dataset.label;}).concat(['Committees']).concat(ex?ex.cols:[]);
    var lines=[cols.map(csvCell).join(',')];
    [].forEach.call(tbody.children,function(tr){ if(tr.classList.contains('hide')) return;   // current sort order
      var c=[]; for(var i=0;i<ths.length;i++) c.push(csvCell(cell(tr,i)));
      c.push(csvCell((tr.dataset.committees||'').split('|').join('; ')));
      if(ex) ex.values(tr).forEach(function(v){ c.push(csvCell(v)); });
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
    if(window.cbUrlExtras) window.cbUrlExtras(p);
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
<div id="fuRecipSec" class="fu-sec"><div class="fu-h">Recipients</div><div id="fuRecips"></div></div>
<div id="fuModeSec" class="fu-sec fu-row"><label><input type="radio" name="fuMode" value="each" checked> A separate letter for each recipient</label>
<label><input type="radio" name="fuMode" value="joint"> One letter to all</label></div>
<div class="fu-sec fu-row"><input id="fuName" class="fu-in" placeholder="Your name" autocomplete="name">
<input id="fuRole" class="fu-in" placeholder="Your title (for example, Chair)"></div>
<div id="fuLetters"></div>
<p class="fu-note">Each draft quotes the request and the city's responses. Review and edit it before sending.
Your name, your saved contacts and the letters you mark as sent stay in this browser.
Contacts come from official city websites (<span id="fuAsOf"></span>); check them before relying on them.</p>
</div></div>"""

FU_SCRIPT = r"""
<script>
(function(){
  var dlg=document.getElementById('fuModal'), T=window.cbTable; if(!dlg||!T) return;
  var C=window.contacts||{}; ['council','boardCouncil','bp','agency'].forEach(function(k){ if(!C[k]) C[k]={}; });
  var FY=window.pageYear, boardFull=window.boardFull||{}, boardName=window.boardName||{};
  var ths=[].slice.call(document.querySelectorAll('table thead th')), col={};
  ths.forEach(function(t,i){ col[t.dataset.label]=i; });
  var BORO={M:'Manhattan',BX:'Bronx',BK:'Brooklyn',Q:'Queens',SI:'Staten Island'};
  var ACTIONS=['Contact agency','Contact elected officials','Contact agency and elected officials','Track with agency',
               'Use 311 or another channel','No follow-up needed'];
  var SLUG={'Contact agency':'a','Contact elected officials':'e','Contact agency and elected officials':'ae',
            'Track with agency':'t','Use 311 or another channel':'c','No follow-up needed':'n'};
  var MONTH=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var fuName=document.getElementById('fuName'), fuRole=document.getElementById('fuRole');
  var cur=null, list=[], mode='each', lastFocus=null, digest=null, edits={};

  // ---- saved in this browser ----
  function load(k,d){ try{ var v=JSON.parse(localStorage.getItem(k)||'null'); return v==null?d:v; }catch(e){ return d; } }
  function save(k,v){ try{ localStorage.setItem(k,JSON.stringify(v)); }catch(e){} }
  var sender=load('cbFollowupSender',{}), sent=load('cbFollowupSent',{}), mine=load('cbFollowupContacts',{});
  fuName.value=sender.name||''; fuRole.value=sender.role||'';
  function rowKey(tr){ return FY+'|'+(tr.dataset.id||tr.dataset.tc||tr.dataset.search.slice(0,60)); }

  // ---- text ----
  function val(tr,label){ var i=col[label]; if(i==null) return ''; var td=tr.children[i], v=td.getAttribute('data-v');
    return (v!==null?v:td.textContent).replace(/\s+/g,' ').trim(); }
  function clip(s,max){ s=(s||'').replace(/\s+/g,' ').trim(); if(s.length<=max) return s;
    var c=s.slice(0,max), d=c.lastIndexOf('. '); return d>max*0.5?c.slice(0,d+1):c.replace(/\s+\S*$/,'')+'…'; }
  // A response's sentences, without breaking at "U.S." or "St." or inside a URL.
  var ABBR=/^(?:\(?[A-Z]\.|(?:[A-Za-z]\.){2,}|(?:St|Ave|Dept|No|Nos|Mr|Ms|Mrs|Dr|Inc|Co|Corp|Jr|Sr|vs|approx|Blvd|Rd|Pl|Pkwy|Bldg|Fl|Rm|Ste|Div)\.)$/;
  function sentences(s){ s=(s||'').replace(/\s+/g,' ').trim(); var out=[], start=0, re=/[.!?]+(?=\s|$)/g, m;
    while((m=re.exec(s))){ var end=m.index+m[0].length, w=(/\S+$/.exec(s.slice(start,end))||[''])[0];
      if(end<s.length&&ABBR.test(w)) continue; out.push(s.slice(start,end).trim()); start=end; }
    if(s.slice(start).trim()) out.push(s.slice(start).trim()); return out; }
  function lead(s,n,max){ return clip(sentences(s).slice(0,n).join(' '),max); }
  // A quoted text ends a sentence in the letter, so it needs end punctuation.
  function stop(s){ s=(s||'').replace(/[\s,;:]+$/,''); return !s||/[.!?…]$/.test(s)?s:s+'.'; }
  // The response as a letter quotes it. When the follow-up turns on a contact, a process or
  // another agency that the response names after its first two sentences, the quote adds
  // that sentence.
  var KEY=/\b(contact|reach out|call|e-?mail|apply|application|programs?|submit|forms?|311|portal|www\.|https?:|refer|jurisdiction|responsib|handled by|purview)/i;
  function quote(s,r,max){ var p=sentences(s), q=clip(p.slice(0,2).join(' '),max), k=-1;
    if(/^(channel|redirect|discuss|clarify)$/.test(r.purpose)&&!KEY.test(q))
      for(var j=2;j<p.length;j++) if(KEY.test(p[j])){ k=j; break; }
    return k<0?q:q+(k===2?' ':' … ')+clip(p[k],280); }
  function andList(a){ return a.length<2?a.join(''):a.slice(0,-1).join(', ')+' and '+a[a.length-1]; }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
  function reach(o){ return !!(o&&(o.email||o.form)); }
  function boroOf(b){ var m=/^(BX|BK|SI|M|Q)CB\d+$/.exec(b||''); return m?BORO[m[1]]:''; }
  function agencyPhrase(a){ if(a==='Other'||!a) return 'a city agency';
    return /^(the |Con ?Edison|Consolidated Edison|Amtrak|National Grid|Verizon|Spectrum|PSEG|Optimum|Metro-North|LIRR|FDNY Foundation)/i.test(a)?a:'the '+a; }
  function Cap(s){ return s.charAt(0).toUpperCase()+s.slice(1); }
  // The honorific for a salutation ("Commissioner Diya Vij"), from a formal title such as
  // "Commissioner of the NYC Department of Cultural Affairs". Other titles use the name alone.
  function honor(t){ t=t||''; var m=/^(Deputy|Assistant) Commissioner/i.exec(t);
    if(m) return m[0]; if(/Commissioner/i.test(t)) return 'Commissioner';
    if(/^Chancellor/i.test(t)) return 'Chancellor'; if(/^Chair/i.test(t)) return 'Chair';
    if(/^President/i.test(t)) return 'President'; return ''; }
  function isBP(o){ return o.role==='head'||/^Borough President$/i.test(o.office||''); }
  function bpName(o){ return isBP(o)?'Borough President'+(o.person?' '+o.person:''):(o.person||'colleagues at the Borough President’s office'); }
  function today(){ var d=new Date(); return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2); }
  function niceDate(s){ var p=(s||'').split('-'); return p.length===3?MONTH[+p[1]-1]+' '+(+p[2])+', '+p[0]:s; }

  // ---- one request ----
  function request(tr){
    var pill=tr.querySelector('.fu-pill');
    return {tr:tr, key:rowKey(tr), board:tr.dataset.board||'', full:boardFull[tr.dataset.board]||tr.dataset.board||'the community board',
      boro:boroOf(tr.dataset.board), pri:val(tr,'Priority'), type:val(tr,'Type'), agency:val(tr,'Agency'),
      title:val(tr,'Title'), expl:val(tr,'Explanation'), ar:val(tr,'Agency Response'), omb:val(tr,'OMB Executive Response'),
      action:val(tr,'Follow-up'), why:pill?pill.title:'', purpose:tr.dataset.fp||'', named:tr.dataset.fc||'',
      url:tr.dataset.fu||'', tc:tr.dataset.tc||'', dest:tr.dataset.fa||'',
      cds:(tr.dataset.cd||'').split('|').filter(Boolean).map(Number), where:tr.dataset.cw||'',
      hist:(tr.dataset.hy||'').split('|').filter(function(y){ return y&&+y<=+FY; }), prior:tr.dataset.pr||''};
  }
  function says311(r){ return /\b311\b/.test(r.ar+' '+r.omb+' '+r.why+' '+r.named); }
  // "Use 311 or another channel" needs no letter when the response gives a link or 311;
  // a named process ("Submit a space request") is a question for the agency.
  function linkOnly(r){ return r.action==='Use 311 or another channel'&&(!!r.url||says311(r)); }
  // "every year since FY2024" when the years run without a gap to this one.
  function histSentence(r){ var h=r.hist; if(h.length<2) return '';
    var every=+h[h.length-1]===+FY&&h.every(function(y,i){ return !i||+y===+h[i-1]+1; });
    return every?'We have made this request every year since FY'+h[0]+'.':'We have made this request in '+h.length+' budget years, starting in FY'+h[0]+'.'; }

  function recipients(r){
    var out=[], a=r.action;
    var wantA=/^(Contact agency|Track with agency)/.test(a)||(a==='Use 311 or another channel'&&!linkOnly(r));
    var wantE=/elected officials$/.test(a);
    var rank=function(o){ if(o.mine) return -1; if(!reach(o)) return 9; if(o.boards&&o.boards.indexOf(r.board)>-1) return 0;
      return {borough:1, liaison:2, head:3}[o.role]||8; };
    function offices(ag){
      var own=(mine[ag]||[]).map(function(m,i){ return {office:'your contact', person:m.name, email:m.email, form:'', phone:'', mine:true, idx:i}; });
      var offs=own.concat((C.agency[ag]||[]).filter(function(o){ return (!o.borough||o.borough===r.boro)&&(reach(o)||o.phone)&&
        (!o.boards||!o.boards.length||o.boards.indexOf(r.board)>-1); }));
      offs.sort(function(x,y){ return rank(x)-rank(y); }); return offs; }
    // A response that sends the board to another agency makes that agency the recipient;
    // the agency that responded stays on the list, unselected.
    [r.dest, r.agency].forEach(function(ag,k){ if(!ag||ag==='Other'||(k===1&&ag===r.dest)) return;
      // A press office is the recipient only when it is the body's one published channel.
      var offs=offices(ag), main=(k===0)||!r.dest, pick=offs.filter(function(o){ return rank(o)<4; })[0]||
        offs.filter(function(o){ return reach(o)&&o.role==='press'; })[0];
      offs.forEach(function(o){ var nm=o.mine?(o.person||o.email)+', '+ag:ag+', '+o.office+(o.person?(/\)$/.test(o.office)?', '+o.person:' ('+o.person+')'):'');
        out.push({kind:'agency', ag:ag, orig:!!r.dest&&ag!==r.dest, o:o, id:'ag|'+nm+'|'+(o.email||o.form||''), name:nm,
          label:nm+(o.mine?' (your contact)':''), on:wantA&&main&&o===pick}); });
      if(!offs.length&&main) out.push({kind:'agency', ag:ag, orig:false, o:{office:'', person:'', email:'', form:'', phone:''},
        id:'ag|'+ag, name:ag, label:ag+' (no contact on file)', on:wantA}); });
    // Council Members: the member for the request's site when the site is known,
    // otherwise those whose districts cover at least 10% of the board's land.
    var ov=(C.boardCouncil[r.board]||[]).slice(), seen={};
    r.cds.forEach(function(d){ if(!ov.some(function(p){ return p[0]===d; })) ov.push([d,0]); });
    ov.forEach(function(p){ var m=C.council[String(p[0])]; if(!m||seen[p[0]]) return; seen[p[0]]=1;
      var here=r.cds.indexOf(p[0])>-1;
      out.push({kind:'council', o:m, id:'cm|'+p[0], name:m.salutation+', District '+p[0], label:m.salutation+', District '+p[0]+(here?' (the request’s site)':
        (p[1]?' (covers '+Math.round(p[1]*100)+'% of the board’s area)':'')), on:wantE&&(r.cds.length?here:p[1]>=0.1)}); });
    // Borough President: the budget office for money, otherwise the Borough President.
    var bps=C.bp[r.boro]||[], budget=bps.filter(function(b){ return !isBP(b)&&/budget|capital/i.test(b.office||'')&&reach(b); })[0];
    var bpLead=(r.purpose==='funding'&&budget)||bps.filter(isBP)[0]||bps[0];
    bps.forEach(function(b){ out.push({kind:'bp', o:b, id:'bp|'+r.boro+'|'+b.office,
      name:isBP(b)?'Borough President'+(b.person?' '+b.person:''):r.boro+' Borough President’s office, '+b.office+(b.person?' ('+b.person+')':''), label:isBP(b)?'Borough President'+(b.person?' '+b.person:''):
      r.boro+' Borough President’s office, '+b.office+(b.person?' ('+b.person+')':''), on:wantE&&b===bpLead}); });
    return out;
  }
  function salute(x){
    if(x.kind==='council') return x.o.salutation;
    if(x.kind==='bp') return bpName(x.o);
    if(x.o.person){ var t=x.o.mine?'':honor(x.o.title||x.o.office); return (t?t+' ':'')+x.o.person; }
    return 'colleagues at '+agencyPhrase(x.ag);
  }
  function channelText(r,Y){ return r.url?Y+' points the board to '+r.url+'. Please tell us if the board should take any other step.'
    :says311(r)?Y+' points the board to 311. Please tell us if the board should take any other step.'
    :'Please tell us how the board should submit this request through the process '+(Y==='Your response'?'your':'the')+' response describes, or send us the form.'; }
  // The ask to an agency. The response is quoted just above it, so the ask does not
  // restate it. short=true gives one sentence for a list of requests.
  function agencyAsk(r,Y,orig,short){
    var S={clarify:'Please tell us what information would help.', study:'Please tell us where the agency’s review stands.',
      discuss:'Please tell us whom we should contact.', reconsider:'Please tell us what would allow the agency to reconsider it.',
      funding:'Please share the estimated cost and the funding the agency would need.', advocacy:'Please tell us which office would need to act.',
      status:'Please share its current status and timeline.', channel:'Please tell us how the board should submit it.',
      no_response:'Please tell us the agency’s position on it.'};
    var own=Y==='Your response', your=own?'your':'the agency’s', yours=own?'your agency':'the agency';
    if(r.purpose==='redirect'&&r.dest) return orig
      ?(short?'We are bringing it to '+agencyPhrase(r.dest)+'. Please tell us whom there we should contact.'
        :'We are bringing this request to '+agencyPhrase(r.dest)+'. Please tell us whom there we should contact, or whether your agency can take on any part of it.')
      :(short?'Please tell us whether your agency can consider it.'
        :'Please tell us whether '+(own?'your agency':agencyPhrase(r.dest))+' can take up this request in the next budget, and whom we should contact about it.');
    if(short) return S[r.purpose]||'Please tell us its current status.';
    switch(r.purpose){
      case 'clarify': return 'We would like to give '+yours+' the information it needs. Please tell us what would help, or suggest a time for board members to meet with the right staff.';
      case 'study': return 'Please tell us where '+your+' review stands and when you expect to finish it. We can provide any information that would help.';
      case 'discuss': return 'We would like to discuss this request with the right staff. Please tell us whom to contact and when they are available.';
      case 'reconsider': return 'This request remains a priority for our district. Please explain '+your+' reasons in more detail, and tell us what would allow '+yours+' to reconsider it in the next budget.';
      case 'funding': return 'Please share the estimated cost of this request and the funding '+yours+' would need to move it forward.';
      case 'advocacy': return 'Please tell us which office or level of government would need to act on this request, and what the board can do to help.';
      case 'status': return 'Please tell us where this request stands, when you expect the work to be done, and whom we should contact for updates.';
      case 'channel': return channelText(r,Y);
      case 'no_response': return 'We could not find a published response to this request in the Statement of Community District Needs or in the City’s Register of Community Board Budget Requests. Please tell us the agency’s position on it.';
      default: return 'Please tell us where this request stands and whether any work remains.';
    }
  }
  // Who a letter to elected officials asks: "you", or the Borough President when the
  // letter goes to the Borough President's staff.
  function youFor(els){ return els.length===1&&els[0].kind==='bp'&&!isBP(els[0].o)?'the Borough President':'you'; }
  // Elected officials can advocate for a request in the City's budget. For a capital
  // project they can also allocate Reso A funds, which the letter offers as a second ask.
  function electedAsk(r,els,joint){
    var who=andList(els.map(function(x){ return x.kind!=='bp'?x.o.salutation:isBP(x.o)?bpName(x.o):'the Borough President'; })), you=youFor(els);
    var ask=function(verb){ return joint?'We ask '+who+' to '+verb+'.':'We ask that '+you+' '+verb+'.'; };
    var yours=joint?'':you==='you'?'your ':'the Borough President’s ';
    if(r.purpose==='advocacy') return 'The response indicates that this request needs a decision beyond the agency. '+
      ask('help advance it, including through any legislation or policy change it requires');
    if(r.purpose==='funding'||/elected officials$/.test(r.action))
      return r.type==='Capital'?ask('advocate for funding this project in the City’s capital budget')+' We would also welcome '+yours+'consideration of Reso A capital funds for it.'
        :ask('advocate for funding this request in the City’s next budget');
    return (joint?'We ask '+who+' to help us':'We would appreciate '+(you==='you'?'your':'the Borough President’s')+' help')+
      ' getting a response from '+agencyPhrase(r.dest||r.agency)+' and moving this request forward.';
  }
  // OMB's Executive Budget response, as the letter reports it. OMB mostly answers in stock
  // phrases, summarized here in a short clause; each kind of clause goes only in letters it
  // bears on. A response that restates the agency, repeats what the agency said or sends the
  // board back to the agency is left out. Other text is quoted.
  var OMB_SAYS=[
    [/brought to the attention of your elected officials/i,'elected','recommended that the board bring this request to its elected officials'],
    [/recommends funding this budget request, but at this time the availability of funds is uncertain/i,'money','said the agency recommends funding it but that funds are uncertain'],
    [/availability of funds is uncertain|funding for this request cannot be determined/i,'money','said the availability of funds is uncertain'],
    [/available funds are insufficient/i,'money','said available funds are insufficient'],
    [/cannot be funded in FY ?(\d{4})/i,'money','said it cannot be funded in FY$1'],
    [/not recommended for funding/i,'money','did not recommend it for funding'],
    [/has not submitted a proposal to increase funding/i,'money','said the agency has not proposed more funding for it'],
    [/restoring and\/or increasing funding is needed/i,'money','said more funding is needed for it'],
    [/depends on sufficient federal\/state funds|approved if the city receives sufficient federal and\/or state funds/i,'money','said approval depends on federal or state funds'],
    [/citywide personnel\/program\/equipment funds are maintained/i,'money','said citywide funds for this work stay at their current level'],
    [/will accommodate part of this request/i,'status','said the agency will accommodate part of it within existing resources'],
    [/will try to accommodate this (issue|request)/i,'status','said the agency will try to accommodate it within existing resources'],
    [/will accommodate this request within existing resources/i,'status','said the agency will accommodate it within existing resources'],
    [/partially funded/i,'status','said it is partially funded'],
    [/funded in a prior fiscal year and the scope is now underway/i,'status','said it was funded in a prior year and the work is underway'],
    [/funded in a prior fiscal year and the construction contract has been let/i,'status','said it was funded in a prior year and the construction contract has been let'],
    [/funded in a prior fiscal year and the (preliminary |final )?design contract has been let/i,'status','said it was funded in a prior year and the design contract has been let'],
    [/has already been funded/i,'status','said it has already been funded'],
    [/included in the ten-year plan/i,'status','said the project is in the Ten-Year Plan'],
    [/project is ongoing/i,'status','said the project is ongoing'],
    [/funding and\/or headcount was recently added/i,'status','said funding or staff was recently added'],
    [/includes a city-wide allocation for this work/i,'status','said the Executive Budget includes a citywide allocation for this work'],
    [/has already been completed/i,'status','said it has been completed'],
    [/not eligible for capital funding/i,'info','said it is not eligible for capital funding'],
    [/not a budget request/i,'info','said this is not a budget request'],
    [/does not seem to be applicable to the responsible agency/i,'info','said the request does not seem to apply to the agency'],
    [/sidewalks are the responsibility of the adjacent property owner/i,'info','said sidewalks are the responsibility of the adjacent property owner'],
    [/more information is needed from the community board|requires additional information from the community board/i,'info','said the agency needs more information from the board'],
    [/includes more than one proposal/i,'info','noted that the request includes more than one proposal'],
    [/further (study|investigation)|requires further study|contact the (relevant |responsible )?(agency|borough commissioner|transit authority)|for more information|reach out to the agency/i,'skip','']
  ];
  function ombNote(r,toElected){
    var o=(r.omb||'').replace(/\s+/g,' ').trim(), norm=function(s){ return s.toLowerCase().replace(/[^a-z0-9]+/g,' ').trim(); };
    if(!o||/^OMB (supports the agency.s position|agrees with the agency)/i.test(o)||/^Agency (supports|does not support|will|has|is|cannot)/i.test(o)) return '';
    for(var i=0;i<OMB_SAYS.length;i++){
      var re=OMB_SAYS[i][0], kind=OMB_SAYS[i][1], m=re.exec(o); if(!m) continue;
      if(kind==='skip'||re.test(r.ar)) return '';
      var fits=kind==='info'||(kind==='elected'&&toElected)||(kind==='money'&&(toElected||/^(funding|advocacy|reconsider)$/.test(r.purpose)))||
        (kind==='status'&&/^(status|none)$/.test(r.purpose));
      return fits?'In the Executive Budget, OMB '+OMB_SAYS[i][2].replace('$1',m[1]||'')+'.':'';
    }
    if(norm(r.ar).indexOf(norm(o).slice(0,60))>-1) return '';
    return 'In the Executive Budget, OMB responded, “'+stop(lead(o,2,300))+'”';
  }
  function signature(full){ return ['Sincerely,', fuName.value.trim()||'[Your name]', fuRole.value.trim()||'[Your title]', full].join('\n'); }
  function kindWord(r){ var w=(r.type?r.type.toLowerCase()+' ':'')+'request'; return (/^[aeiou]/.test(w)?'an ':'a ')+w; }
  // A "CS" request has no rank, so the letter names only its tracking code.
  function ids(r){ return [/^\d+$/.test(r.pri)?'priority '+r.pri:'', r.tc?'tracking code '+r.tc:''].filter(Boolean).join(', '); }
  function titleOf(r){ return (r.title||'').replace(/[\s.,;:]+$/,''); }
  function letterBody(r,xs){
    var ag=xs.filter(function(x){return x.kind==='agency';}), el=xs.filter(function(x){return x.kind!=='agency';});
    // A letter to the agency that responded calls it "your agency".
    var joint=ag.length>0&&el.length>0, own=!joint&&ag.length>0&&ag.every(function(x){ return x.ag===r.agency; });
    // Before FY2026 a request's title is DCP's category for it, not the board's own title.
    var to=own?'your agency':agencyPhrase(r.agency);
    var p1=r.full+'’s FY'+FY+' budget requests included '+(+FY<2026?kindWord(r)+' to '+to+' in the category “'+titleOf(r)+'”':
      '“'+titleOf(r)+',” '+kindWord(r)+' to '+to)+(ids(r)?' ('+ids(r)+')':'')+'.';
    if(r.expl) p1+=' We wrote, “'+stop(clip(r.expl,320))+'”';
    var h=histSentence(r); if(h) p1+=' '+h;
    var parts=['Dear '+andList(xs.map(salute))+',', p1];
    if(r.purpose!=='no_response'){
      var ar=stop(quote(r.ar,r,360)), who=own?'Your agency':el.length&&!joint?'The agency':Cap(agencyPhrase(r.agency));
      var p2=ar?who+' responded, “'+ar+'”':'We could not find a published response from '+agencyPhrase(r.agency)+'.';
      var o=ombNote(r,el.length>0); if(o) p2+=' '+o;
      parts.push(p2); }
    if(ag.length) parts.push(agencyAsk(r, joint?'The response from '+agencyPhrase(r.agency):'Your response', ag.every(function(x){return x.orig;}), false));
    if(el.length) parts.push(electedAsk(r,el,joint));
    parts.push('Thank you for your help.');
    return parts.join('\n\n');
  }
  function subject(r){ return 'FY'+FY+' '+(r.type?r.type.toLowerCase()+' ':'')+'budget request, '+clip(r.title,70)+' ('+(boardName[r.board]||r.board)+(r.tc?', '+r.tc:'')+')'; }

  // ---- a list of requests for one official (the digest) ----
  function digestBody(g){
    var x=g.x, rs=g.reqs, lines=[], elected=x.kind!=='agency', n=rs.length, many=n>1, it=many?'them':'it';
    lines.push('Dear '+salute(x)+',');
    var intro=g.full+'’s FY'+FY+' budget requests included ';
    if(elected){
      var you=youFor([x]), yours=you==='you'?'your':'the Borough President’s';
      var money=rs.every(function(r){ return r.purpose==='funding'||(/elected officials$/.test(r.action)&&r.purpose!=='advocacy'); });
      var caps=rs.filter(function(r){ return r.type==='Capital'; }).length;
      lines.push(intro+(many?'the '+n+' requests below.':'the request below.')+' '+(money
        ?'The City’s responses indicate that '+(many?'each needs':'it needs')+' funding to move forward. We ask that '+you+' advocate for funding '+it+' in the City’s next budget.'+
          (caps?' We would also welcome '+yours+' consideration of Reso A capital funds for '+(caps===n?it:'the capital projects')+'.':'')
        :'We ask for '+yours+' help moving '+it+' forward, through advocacy with the agencies and in the City’s budget.'));
    } else {
      var redirected=rs.every(function(r){ return r.dest===x.ag&&r.agency!==x.ag; });
      lines.push(intro+(many?'the '+n+' requests':'the request')+(redirected?' below, which '+(many?'other agencies':'another agency')+' directed to your agency.':' to your agency listed below.')+
        ' We are following up on '+(many?'each of them':'it')+'.');
    }
    rs.forEach(function(r,i){
      var own=!elected&&r.agency===x.ag;
      var head=(i+1)+'. “'+titleOf(r)+'” ('+[own?'':r.agency, r.type?r.type.toLowerCase():'', ids(r)].filter(Boolean).join(', ')+').';
      var resp=stop(quote(r.ar,r,260)), h=histSentence(r);
      var item=head+(h?' '+h:'')+(resp?' '+(own?'Your agency':'The agency')+' responded, “'+resp+'”':' No response was published.');
      if(!elected) item+=' '+agencyAsk(r,'Your response',x.orig,true);
      lines.push(item);
    });
    lines.push('Thank you for your help.');
    return lines.join('\n\n');
  }

  // ---- letters on screen ----
  function contactBits(o){
    var b=[]; if(o.email) b.push('<a href="mailto:'+esc(o.email)+'">'+esc(o.email)+'</a>');
    if(o.form) b.push('<a href="'+esc(o.form)+'" target="_blank" rel="noopener">contact form</a>');
    if(o.phone) b.push(esc(o.phone)); var u=o.url||o.src; if(u) b.push('<a href="'+esc(u)+'" target="_blank" rel="noopener">source</a>');
    if(o.mine) b.push('<button type="button" class="fu-link" data-forget="'+esc(o.idx)+'">remove</button>');
    return b.join(' · ');
  }
  function mailHref(to,subj,body){ return 'mailto:'+to.join(',')+'?subject='+encodeURIComponent(subj)+'&body='+encodeURIComponent(body.replace(/\n/g,'\r\n')); }
  function markSent(rows,to){ var d=today(); rows.forEach(function(r){ sent[r.key]={d:d, to:to}; paintSent(r.tr); }); save('cbFollowupSent',sent); renderCards(); }
  function unmark(rows){ rows.forEach(function(r){ delete sent[r.key]; paintSent(r.tr); }); save('cbFollowupSent',sent); renderCards(); }
  // One letter card. key keeps a user's edits across redraws; sig is the signature in the text.
  function letterCard(key,toLabel,xs,subj,body,rows,full){
    var emails=xs.map(function(x){return x.o.email;}).filter(Boolean), forms=xs.filter(function(x){return !x.o.email&&x.o.form;});
    var w=document.createElement('div'); w.className='fu-letter';
    var isSent=rows.length&&rows.every(function(r){ return sent[r.key]; });
    w.innerHTML='<div class="fu-to"><b>To</b> '+esc(toLabel)+'</div><input class="fu-subj fu-in" aria-label="Subject">'+
      '<textarea class="fu-body" rows="14" aria-label="Letter"></textarea><div class="fu-acts">'+
      '<button type="button" class="fu-act fu-copy">Copy letter</button>'+(emails.length?'<a class="fu-act fu-mail" href="#">Open in email</a>':'')+
      forms.map(function(x){ return '<a class="fu-act" href="'+esc(x.o.form)+'" target="_blank" rel="noopener">Open '+esc((x.ag||'').replace(/^Department of /,'')||'contact')+' form</a>'; }).join('')+
      '<button type="button" class="fu-act fu-sentbtn">'+(isSent?'Sent ✓ (undo)':(rows.length>1?'Mark these '+rows.length+' requests sent':'Mark as sent'))+'</button>'+
      '<span class="fu-copied" hidden>Copied</span></div><div class="fu-warn" hidden></div>';
    var subjEl=w.querySelector('.fu-subj'), bodyEl=w.querySelector('.fu-body');
    var sig=signature(full), text=edits[key]!=null?edits[key]:body+'\n\n'+sig;
    subjEl.value=edits[key+'|s']!=null?edits[key+'|s']:subj; bodyEl.value=text; w.dataset.sig=sig; w.dataset.full=full;
    bodyEl.addEventListener('input',function(){ edits[key]=bodyEl.value; warn(); });
    subjEl.addEventListener('input',function(){ edits[key+'|s']=subjEl.value; warn(); });
    function warn(){ var n=mailHref(emails,subjEl.value,bodyEl.value).length, el=w.querySelector('.fu-warn');
      el.hidden=!(emails.length&&n>1900); el.textContent='This letter is long for an email link. If your email program cuts it off, use Copy letter.'; }
    warn();
    w.querySelector('.fu-copy').addEventListener('click',function(){
      var t=bodyEl.value, done=function(){ var c=w.querySelector('.fu-copied'); c.hidden=false; setTimeout(function(){c.hidden=true;},1500); };
      if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done,function(){ bodyEl.select(); document.execCommand('copy'); done(); });
      else { bodyEl.select(); document.execCommand('copy'); done(); } });
    var m=w.querySelector('.fu-mail');
    if(m) m.addEventListener('click',function(e){ e.preventDefault(); location.href=mailHref(emails,subjEl.value,bodyEl.value); });
    w.querySelector('.fu-sentbtn').addEventListener('click',function(){
      var all=rows.every(function(r){ return sent[r.key]; });
      if(all) unmark(rows); else markSent(rows, xs.map(function(x){ return x.name; }));
      var now=rows.every(function(r){ return sent[r.key]; });
      this.textContent=now?'Sent ✓ (undo)':(rows.length>1?'Mark these '+rows.length+' requests sent':'Mark as sent'); });
    return w;
  }
  // A new name or title updates each letter's signature in place, keeping any edits.
  function updateSignatures(){
    save('cbFollowupSender',{name:fuName.value, role:fuRole.value});
    [].forEach.call(document.querySelectorAll('#fuLetters .fu-letter'),function(w){
      var b=w.querySelector('.fu-body'), old=w.dataset.sig, neu=signature(w.dataset.full);
      if(old&&b.value.slice(-old.length)===old){ b.value=b.value.slice(0,-old.length)+neu; w.dataset.sig=neu;
        Object.keys(edits).forEach(function(k){ if(edits[k]&&edits[k].slice(-old.length)===old) edits[k]=edits[k].slice(0,-old.length)+neu; }); }
    });
  }
  function renderRecips(){
    var box=document.getElementById('fuRecips'); box.innerHTML='';
    var heads={agency:'Agency',council:'Council Members',bp:'Borough President'}, last='', agencies=[];
    list.forEach(function(x,i){
      if(x.kind!==last){ var h=document.createElement('div'); h.className='fu-sub'; h.textContent=heads[x.kind]; box.appendChild(h); last=x.kind; }
      if(x.kind==='agency'&&agencies.indexOf(x.ag)<0) agencies.push(x.ag);
      var l=document.createElement('label'); l.className='fu-rcp';
      l.innerHTML='<input type="checkbox" data-i="'+i+'"'+(x.on?' checked':'')+'><span><b>'+esc(x.label)+'</b><br><small>'+(contactBits(x.o)||'no email or form on file')+'</small></span>';
      box.appendChild(l);
      [].forEach.call(l.querySelectorAll('[data-forget]'),function(b){ b.addEventListener('click',function(e){ e.preventDefault();
        mine[x.ag].splice(+b.dataset.forget,1); if(!mine[x.ag].length) delete mine[x.ag]; save('cbFollowupContacts',mine); list=recipients(cur); renderRecips(); renderLetters(); }); });
    });
    var ag=cur.dest||cur.agency;
    if(ag&&ag!=='Other'){
      var f=document.createElement('div'); f.className='fu-add';
      f.innerHTML='<details><summary>Add your own contact for '+esc(ag)+'</summary><div class="fu-row">'+
        '<input class="fu-in" placeholder="Name" data-f="name"><input class="fu-in" placeholder="Email" type="email" data-f="email">'+
        '<button type="button" class="fu-act fu-copy">Save</button></div><small>Saved in this browser and offered first for '+esc(ag)+' requests.</small></details>';
      f.querySelector('button').addEventListener('click',function(){
        var n=f.querySelector('[data-f=name]').value.trim(), e=f.querySelector('[data-f=email]').value.trim();
        if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) return;
        (mine[ag]=mine[ag]||[]).push({name:n, email:e}); save('cbFollowupContacts',mine);
        list=recipients(cur); renderRecips(); renderLetters(); });
      box.appendChild(f);
    }
  }
  function renderLetters(){
    var box=document.getElementById('fuLetters'); box.innerHTML='';
    var sel=list.filter(function(x){return x.on;});
    if(!sel.length){ box.innerHTML='<p class="fu-empty">Select at least one recipient to draft a letter.</p>'; return; }
    var groups=mode==='joint'?[sel]:sel.map(function(x){return [x];});
    groups.forEach(function(g){
      var key='one|'+g.map(function(x){return x.label;}).join(';');
      box.appendChild(letterCard(key, g.map(function(x){return x.name;}).join('; '), g, subject(cur), letterBody(cur,g), [cur], cur.full));
    });
  }
  function show(){ dlg.hidden=false; document.body.classList.add('fu-lock'); dlg.querySelector('.fu-x').focus(); }
  function open(tr){
    cur=request(tr); list=recipients(cur); lastFocus=document.activeElement; edits={}; digest=null;
    document.getElementById('fuRecipSec').hidden=false; document.getElementById('fuModeSec').hidden=false;
    document.getElementById('fuTitle').textContent=cur.title||'Follow up';
    var meta='<span class="pill fu-pill fu-'+(SLUG[cur.action]||'n')+'">'+esc(cur.action||'No label')+'</span> '+esc(cur.why);
    meta+='<div class="fu-small">'+esc(cur.full)+' · FY'+esc(FY)+' '+esc(cur.type)+(cur.pri?' priority '+esc(cur.pri):'')+(cur.tc?' · tracking code '+esc(cur.tc):'')+' · '+esc(cur.agency)+'</div>';
    if(cur.hist.length>=2) meta+='<div class="fu-small">Requested in '+cur.hist.length+' budget years: '+esc(cur.hist.map(function(y){return 'FY'+y;}).join(', '))+'.'+
      (cur.prior?' The FY'+esc(cur.prior.slice(0,4))+' response was “'+esc(stop(cur.prior.slice(6)))+'”':'')+'</div>';
    if(cur.cds.length) meta+='<div class="fu-small">The request’s site ('+esc(cur.where)+') is in Council District '+esc(cur.cds.join(' and '))+'.</div>';
    if(cur.dest) meta+='<div class="fu-small">The response points to '+esc(agencyPhrase(cur.dest))+(C.agency[cur.dest]?'.':'. No contact for it is on file, so add one below or add its address yourself.')+'</div>';
    else if(cur.named) meta+='<div class="fu-small">The response names this contact: '+esc(cur.named)+'</div>';
    if(cur.action==='Use 311 or another channel'){
      if(cur.url) meta+='<div class="fu-small"><a href="'+esc(cur.url)+'" target="_blank" rel="noopener">Open the link the response gives</a></div>';
      else if(says311(cur)) meta+='<div class="fu-small"><a href="https://portal.311.nyc.gov/" target="_blank" rel="noopener">Open 311</a></div>';
      else meta+='<div class="fu-small">The response names another process. The letter below asks the agency how to use it.</div>'; }
    else if(cur.url) meta+='<div class="fu-small">The response links to <a href="'+esc(cur.url)+'" target="_blank" rel="noopener">'+esc(clip(cur.url,80))+'</a></div>';
    if(cur.action==='No follow-up needed') meta+='<div class="fu-small">No follow-up is needed. Select a recipient to draft a letter anyway.</div>';
    var st=sent[cur.key]; if(st) meta+='<div class="fu-small fu-sentnote">Marked sent '+esc(niceDate(st.d))+(st.to&&st.to.length?' to '+esc(st.to.join('; ')):'')+'.</div>';
    document.getElementById('fuMeta').innerHTML=meta;
    document.getElementById('fuAsOf').textContent=C.asOf?'council contacts as of '+C.asOf:'as published';
    renderRecips(); renderLetters(); show();
  }
  function openDigest(){
    var rows=T.visible().filter(function(tr){ var a=val(tr,'Follow-up'); return a&&a!=='No follow-up needed'; });
    var groups={}, order=[];
    rows.forEach(function(tr){ var r=request(tr);
      recipients(r).filter(function(x){ return x.on; }).forEach(function(x){
        var k=r.board+'|'+x.id; if(!groups[k]){ groups[k]={board:r.board, full:r.full, x:x, reqs:[]}; order.push(k); }
        groups[k].reqs.push(r); }); });
    var kindRank={agency:0, council:1, bp:2};
    order.sort(function(a,b){ var A=groups[a], B=groups[b];
      return A.board.localeCompare(B.board)||kindRank[A.x.kind]-kindRank[B.x.kind]||A.x.name.localeCompare(B.x.name); });
    edits={}; cur=null; lastFocus=document.activeElement;
    digest=order.map(function(k){ return groups[k]; });
    document.getElementById('fuRecipSec').hidden=true; document.getElementById('fuModeSec').hidden=true;
    var boards={}; digest.forEach(function(g){ boards[g.board]=1; });
    document.getElementById('fuTitle').textContent='Letters for the '+rows.length+' requests shown';
    document.getElementById('fuMeta').innerHTML='<div class="fu-small">One letter per official, listing every request shown that the official can help with. '+
      'Recipients follow each request’s follow-up, as in its own Draft letter panel. Requests marked “No follow-up needed” and those that only need 311 or a link are left out.'+
      (Object.keys(boards).length>1?' The requests come from '+Object.keys(boards).length+' boards, so each board gets its own letters.':'')+'</div>';
    document.getElementById('fuAsOf').textContent=C.asOf?'council contacts as of '+C.asOf:'as published';
    var box=document.getElementById('fuLetters'); box.innerHTML='';
    if(!digest.length) box.innerHTML='<p class="fu-empty">None of the requests shown has a recipient to write to.</p>';
    var many=Object.keys(boards).length>1, lastBoard='';
    digest.forEach(function(g,i){
      if(many&&g.board!==lastBoard){ var h=document.createElement('div'); h.className='fu-sub'; h.textContent=g.full; box.appendChild(h); lastBoard=g.board; }
      var subj='FY'+FY+' budget requests from '+(boardName[g.board]||g.board)+': '+g.reqs.length+' request'+(g.reqs.length>1?'s':'')+' for follow-up';
      box.appendChild(letterCard('dig|'+i, g.x.name+' · '+g.reqs.length+' request'+(g.reqs.length>1?'s':''), [g.x], subj, digestBody(g), g.reqs, g.full));
    });
    show();
  }
  function close(){ dlg.hidden=true; document.body.classList.remove('fu-lock'); if(lastFocus&&lastFocus.focus) lastFocus.focus(); }

  // ---- the table: sent marks, counts, the Follow-up menu ----
  function paintSent(tr){ var cell=tr.querySelector('.fu-cell'); if(!cell) return; var b=cell.querySelector('.fu-sent'), s=sent[rowKey(tr)];
    if(s){ if(!b){ b=document.createElement('span'); b.className='fu-sent'; cell.insertBefore(b,cell.querySelector('.fu-btn')); } b.textContent='Sent '+niceDate(s.d).replace(/, \d{4}$/,''); }
    else if(b) b.remove(); }
  function unsent(tr){ return !sent[rowKey(tr)]; }
  var fuSel=document.getElementById('fuSel'), cards=document.getElementById('fuCards');
  function renderCards(){
    if(!cards) return;
    var c=T.countBy('Follow-up', function(tr){ return !!sent[rowKey(tr)]; }), shown=T.visible().filter(function(tr){ var a=val(tr,'Follow-up'); return a&&a!=='No follow-up needed'; }).length;
    var cur0=T.getSet('Follow-up'), one=cur0&&cur0.length===1?cur0[0]:'';
    cards.innerHTML=ACTIONS.map(function(a){ return '<button type="button" class="fu-card fu-'+SLUG[a]+(one===a?' on':'')+'" data-a="'+esc(a)+'"><span>'+esc(a)+'</span><b>'+(c[a]||0)+'</b></button>'; }).join('')+
      '<span class="fu-card fu-sentcount"><span>Marked sent</span><b>'+(c.__extra||0)+'</b></span>'+
      '<button type="button" class="fu-digest"'+(shown?'':' disabled')+'>Draft one letter per official ('+shown+' requests)</button>';
    [].forEach.call(cards.querySelectorAll('.fu-card[data-a]'),function(b){ b.addEventListener('click',function(){
      window.cbRowFilter=null; var a=b.dataset.a; T.setSet('Follow-up', one===a?null:[a]); }); });
    cards.querySelector('.fu-digest').addEventListener('click',openDigest);
  }
  function syncSel(){ if(!fuSel) return; var s=T.getSet('Follow-up'), v='';
    if(window.cbRowFilter===unsent) v='__unsent';
    else if(s&&s.length===1) v=s[0];
    else if(s&&s.length===5&&s.indexOf('No follow-up needed')<0) v='__needs';
    else if(s) v='__custom';
    fuSel.value=v; }
  if(fuSel) fuSel.addEventListener('change',function(){ var v=fuSel.value; window.cbRowFilter=null;
    if(!v) T.setSet('Follow-up',null);
    else if(v==='__needs') T.setSet('Follow-up',ACTIONS.slice(0,5));
    else if(v==='__unsent'){ window.cbRowFilter=unsent; T.setSet('Follow-up',ACTIONS.slice(0,5)); }
    else if(v!=='__custom') T.setSet('Follow-up',[v]); });
  window.cbUrlExtras=function(p){ if(window.cbRowFilter===unsent) p.set('fu','unsent'); };
  window.cbCsvExtras={cols:['Tracking Code','Follow-up Agency','Follow-up Why','Requested In','Letter Sent','Letter Sent To'],
    values:function(tr){ var s=sent[rowKey(tr)], pill=tr.querySelector('.fu-pill');
      return [tr.dataset.tc||'', tr.dataset.fa||'', pill?pill.title:'', (tr.dataset.hy||'').split('|').filter(Boolean).map(function(y){return 'FY'+y;}).join(', '), s?s.d:'', s&&s.to?s.to.join('; '):'']; }};
  document.addEventListener('cb:applied',function(){ renderCards(); syncSel(); });

  [fuName,fuRole].forEach(function(el){ el.addEventListener('input',updateSignatures); });
  document.addEventListener('click',function(e){ var b=e.target.closest&&e.target.closest('.fu-btn'); if(b) open(b.closest('tr')); });
  document.getElementById('fuRecips').addEventListener('change',function(e){ var i=e.target.getAttribute('data-i'); if(i===null) return; list[+i].on=e.target.checked; renderLetters(); });
  [].forEach.call(document.querySelectorAll('input[name=fuMode]'),function(r){ r.addEventListener('change',function(){ mode=r.value; renderLetters(); }); });
  dlg.querySelector('.fu-x').addEventListener('click',close);
  dlg.addEventListener('click',function(e){ if(e.target===dlg) close(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'&&!dlg.hidden) close(); });

  [].forEach.call(document.querySelectorAll('tbody tr'),paintSent);
  if(new URLSearchParams(window.cbInitialSearch||'').get('fu')==='unsent'){ window.cbRowFilter=unsent; T.apply(); }
  else { renderCards(); syncSel(); }
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
parts.append('<div id="fuCards" class="fu-cards" aria-label="Follow-up counts"></div>')
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
parts.append('<select id="fuSel" class="commsel" title="Filter by follow-up. Letters sent are marked in this browser only." '
             'aria-label="Filter by follow-up"><option value="">All follow-ups</option>'
             '<option value="__needs">Needs follow-up</option><option value="__unsent">Needs follow-up, not yet sent</option>'
             + "".join(f'<option value="{html.escape(a)}">{html.escape(a)}</option>' for a in FU_SLUG)
             + '<option value="__custom" hidden>Custom filter</option></select>')
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
