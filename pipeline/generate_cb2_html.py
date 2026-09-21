#!/usr/bin/env python3
"""Render the FY2027 two-stage detailed spreadsheet as a single self-contained
HTML file. Each request shows the agency's full response (Statement PDF) and
OMB's Executive response (open-data Register). Click a column name to sort;
click its funnel button to filter."""
import html
import json
import re
import sys
import pandas as pd

CSV = sys.argv[1] if len(sys.argv) > 1 else \
    "CB FY2027 Requests (multi-board, detailed, 2-stage).csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "CB2 FY2027 Requests and Agency Responses.html"

REG_URL = "https://data.cityofnewyork.us/City-Government/Register-of-Community-Board-Budget-Requests/vn4m-mk4t"
REPO_DIR = "https://github.com/NYCPlanning/labs-cd-needs-statements/tree/master/QN%20DNS%20FY%202027"

BORO_FULL = {"M": "Manhattan", "BX": "Bronx", "BK": "Brooklyn", "Q": "Queens", "SI": "Staten Island"}
DCP2 = {"M": "MN", "BX": "BX", "BK": "BK", "Q": "QN", "SI": "SI"}


def board_meta(b):                       # "QCB2" -> ("Queens CB2", statement-PDF url)
    m = re.match(r"([A-Z]+)CB(\d+)", str(b))
    abbr, num = m.group(1), m.group(2)
    code = DCP2[abbr] + num.zfill(2)
    pdf = ("https://raw.githubusercontent.com/NYCPlanning/labs-cd-needs-statements/master/"
           f"{DCP2[abbr]}%20DNS%20FY%202027/FY2027_Statement_{code}.pdf")
    return f"{BORO_FULL[abbr]} CB{num}", pdf


df = pd.read_csv(CSV, dtype=str).fillna("")
boards = sorted(df["Board"].unique())
board_opts = [(b, board_meta(b)[0]) for b in boards]
board_pdf = {b: board_meta(b)[1] for b in boards}
DEFAULT_BOARD = "QCB2" if "QCB2" in boards else ""
board_name = dict(board_opts)


def board_full_name(b):
    m = re.match(r"([A-Z]+)CB(\d+)", b)
    return f"{BORO_FULL[m.group(1)]} Community Board {m.group(2)}"


board_full = {b: board_full_name(b) for b in boards}
BORO_ORDER = {"M": 0, "BX": 1, "BK": 2, "Q": 3, "SI": 4}


def _bk(b):
    m = re.match(r"([A-Z]+)CB(\d+)", b)
    return (BORO_ORDER.get(m.group(1), 9), int(m.group(2)))


_chk, _cur = [], None
for _b in sorted(boards, key=_bk):
    _ab = re.match(r"([A-Z]+)CB", _b).group(1)
    if _ab != _cur:
        _cur = _ab
        _chk.append(f'<div class="cm-grp">{html.escape(BORO_FULL[_ab])}</div>')
    _ck = " checked" if _b == DEFAULT_BOARD else ""
    _chk.append(f'<label class="cm-opt" data-name="{html.escape(board_name[_b])}">'
                f'<input type="checkbox" value="{html.escape(_b)}"{_ck}> {html.escape(board_name[_b])}</label>')
board_checklist = "".join(_chk)

DISPLAY = ["Priority", "Type", "Board", "Agency", "Title", "Explanation",
           "Agency Response", "OMB Executive Response", "Agency Stance (MZ added)"]
WIDE = {"Title", "Explanation", "Agency Response", "OMB Executive Response"}
PCT = {"Priority": 6, "Type": 6, "Board": 5, "Agency": 9, "Title": 13,
       "Explanation": 15, "Agency Response": 19.5, "OMB Executive Response": 19,
       "Agency Stance (MZ added)": 7.5}
LABEL = {"Agency Stance (MZ added)": "Agency Stance"}
TOOLTIP = {
    "Priority": "The board's priority/order for this request, as listed in its FY2027 Statement of Community District Needs (PDF).",
    "Type": "Capital or Expense — taken from the Capital/Expense sections of the Statement PDF.",
    "Board": "Borough + community board (e.g. QCB2 = Queens Community Board 2).",
    "Agency": "The city agency responsible for the request (from the Statement PDF).",
    "Title": "The community board's short title for the request (from the Statement PDF).",
    "Explanation": "The board's description and justification of the request (from the Statement PDF).",
    "Agency Response": "The agency's full written response, from the FY2027 Statement of Community District Needs (PDF), published Nov 2025.",
    "OMB Executive Response": "OMB's Executive Budget response, from NYC Open Data's Register of Community Board Budget Requests, matched to each request by its text (99.8% of requests matched).",
    "Agency Stance (MZ added)": "Added by MZ: Support / Oppose / Neutral-Unclear, derived from the agency response — whether the agency supports the request (regardless of whether it can fund it).",
}

sc = df["Agency Stance (MZ added)"].value_counts()
n_exp = (df["Type"] == "Expense").sum()
n_cap = (df["Type"] == "Capital").sum()
n_omb = (df["OMB Executive Response"].str.strip() != "").sum()
committees_list = sorted({c for cs in df["Committees"] for c in str(cs).split("|") if c})


def stance_slug(v):
    return {"Support": "support", "Oppose": "oppose",
            "Neutral/Unclear": "neutral"}.get(v, "neutral")


body = []
for idx, (_, r) in enumerate(df.iterrows()):
    z = "odd" if idx % 2 else "even"
    blob = html.escape(" ".join(str(r[c]) for c in DISPLAY).lower(), quote=True)
    tds = []
    for c in DISPLAY:
        val = html.escape(str(r[c]))
        if c == "Agency Stance (MZ added)":
            tds.append(f'<td><span class="pill i-{stance_slug(r[c])}">{val}</span></td>')
        elif c == "Type":
            tds.append(f'<td><span class="pill {"ce-e" if r[c] == "Expense" else "ce-c"}">{val}</span></td>')
        elif c == "Board":
            tds.append(f'<td class="board">{val}</td>')
        elif c == "Agency":
            tds.append(f'<td class="agency">{val}</td>')
        elif c in WIDE:
            extra = " mtitle" if c == "Title" else ""
            tds.append(f'<td class="wide{extra}">{val}</td>')
        else:
            tds.append(f'<td class="nowrap">{val}</td>')
    body.append(f'<tr class="{z}" data-search="{blob}" '
                f'data-board="{html.escape(str(r["Board"]), quote=True)}" '
                f'data-committees="{html.escape(str(r["Committees"]), quote=True)}">' + "".join(tds) + "</tr>")

FUNNEL = ("<svg viewBox='0 0 16 16' width='11' height='11' aria-hidden='true'>"
          "<path fill='currentColor' d='M1 3h14l-5.5 6.5V14l-3 1.5V9.5z'/></svg>")


def th(idx, label, cls, tip):
    lab = html.escape(label)
    return (f'<th class="{cls}" data-ci="{idx}" data-label="{lab}" title="{html.escape(tip)}"><div class="th-in">'
            f'<span class="th-lbl">{lab}<span class="th-arrow"></span></span>'
            f'<button class="th-funnel" title="Sort &amp; filter" aria-label="Sort and filter">{FUNNEL}</button>'
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
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CB2 FY2027 Budget Requests &amp; Agency Responses</title>
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
.legend{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:10px;color:var(--mut)}
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
.count{color:var(--mut);font-size:12px;white-space:nowrap;margin-left:auto}
.wrap{padding:0 12px 40px}
table{border-collapse:separate;border-spacing:0;width:100%;table-layout:fixed;background:#fff;margin-top:8px}
thead th{position:sticky;top:var(--ch,0px);background:#1e293b;color:#fff;text-align:left;padding:8px 6px;
  font-size:10.5px;font-weight:600;white-space:normal;vertical-align:bottom;user-select:none;z-index:2}
.th-in{display:flex;align-items:flex-end;gap:3px;justify-content:space-between}
.th-lbl{cursor:pointer;flex:1 1 auto;min-width:0}
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
.agency{white-space:normal;font-size:12px}
.board{white-space:nowrap;font-weight:600}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;white-space:nowrap}
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
  .boardbtn{width:100%;text-align:left}
  #commSel{flex:1 1 48%;max-width:none}
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
}
</style></head><body>
"""

SCRIPT = """
<script>
(function(){
  var table=document.querySelector('table');
  var tbody=table.querySelector('tbody');
  var ths=[].slice.call(table.querySelectorAll('thead th'));
  var rows=[].slice.call(tbody.children);
  var numeric={}; ths.forEach(function(t,i){if((t.dataset.label||'').toLowerCase()==='priority') numeric[i]=true;});
  var countEl=document.getElementById('count');
  (function(){var L=ths.map(function(t){return t.dataset.label||'';});
    rows.forEach(function(tr){for(var i=0;i<tr.children.length&&i<L.length;i++) tr.children[i].setAttribute('data-th',L[i]);});})();
  var q=document.getElementById('q');
  var filters={}, sortCol=-1, sortDir=1, term='', commFilter='';
  var boardPick=new Set(), boardPdf=window.boardPdf||{}, repoDir=window.repoDir||'', boardName=window.boardName||{}, boardFull=window.boardFull||{};
  function cell(tr,ci){return tr.children[ci].textContent.trim();}
  var typeCol=-1,stanceCol=-1;
  ths.forEach(function(t,i){var l=(t.dataset.label||'').toLowerCase(); if(l==='type')typeCol=i; if(l.indexOf('stance')>-1)stanceCol=i;});
  function setCard(k,v){var e=document.querySelector('[data-card="'+k+'"]'); if(e)e.textContent=v;}
  function rowOk(tr){
    if(boardPick.size && !boardPick.has(tr.dataset.board)) return false;
    if(commFilter && ((tr.dataset.committees||'').split('|').indexOf(commFilter)===-1)) return false;
    if(term && (tr.dataset.search||'').indexOf(term)===-1) return false;
    for(var ci in filters){var f=filters[ci], v=cell(tr,+ci);
      if(f.type==='set'){ if(!f.allowed[v]) return false; }
      else if(f.type==='text'){ if(v.toLowerCase().indexOf(f.q)===-1) return false; }}
    return true;
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
      var fn=t.querySelector('.th-funnel'); if(fn) fn.classList.toggle('active',!!filters[i]);
      var ar=t.querySelector('.th-arrow'); if(ar) ar.textContent=(sortCol===i)?(sortDir===1?' \\u25b2':' \\u25bc'):'';
    });
    writeURL();
  }
  function doSort(ci,dir){
    sortCol=ci; sortDir=dir; var num=numeric[ci];
    var ms=document.getElementById('msort'); if(ms) ms.value=ci+'.'+(dir===1?'asc':'desc');
    rows.slice().sort(function(a,b){
      var x=cell(a,ci), y=cell(b,ci);
      if(num){x=parseFloat(x); y=parseFloat(y); x=isNaN(x)?-Infinity:x; y=isNaN(y)?-Infinity:y; return (x-y)*dir;}
      return x.localeCompare(y,undefined,{numeric:true})*dir;
    }).forEach(function(r){tbody.appendChild(r);});
    apply();
  }
  function distinct(ci){var seen={},out=[]; rows.forEach(function(tr){var v=cell(tr,ci); if(!(v in seen)){seen[v]=1; out.push(v);}}); return out;}
  var menu=document.createElement('div'); menu.className='colmenu'; menu.style.display='none';
  document.body.appendChild(menu);
  menu.addEventListener('click',function(e){e.stopPropagation();});
  document.addEventListener('click',function(){menu.style.display='none'; var bp=document.getElementById('boardPanel'); if(bp)bp.style.display='none';});
  function mkBtn(txt,cls,fn){var b=document.createElement('button'); b.className=cls; b.textContent=txt; b.onclick=fn; return b;}
  function openMenu(ci,thEl){
    menu.innerHTML='';
    var title=document.createElement('div'); title.className='cm-title'; title.textContent='Filter: '+(thEl.dataset.label||''); menu.appendChild(title);
    var vals=distinct(ci).sort(function(a,b){return a.localeCompare(b,undefined,{numeric:true});});
    if(vals.length<=30){
      var cur=(filters[ci]&&filters[ci].type==='set')?filters[ci].allowed:null;
      var working={}; vals.forEach(function(v){working[v]=cur?!!cur[v]:true;});
      function commit(){
        var on=vals.filter(function(v){return working[v];});
        if(on.length===vals.length) delete filters[ci];
        else {var al={}; on.forEach(function(v){al[v]=1;}); filters[ci]={type:'set',allowed:al};}
        apply();
      }
      var list=document.createElement('div'); list.className='cm-list';
      if(vals.length>8){
        var fs=document.createElement('input'); fs.className='cm-search'; fs.placeholder='filter values\\u2026';
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
      var inp=document.createElement('input'); inp.className='cm-search'; inp.placeholder='contains\\u2026';
      inp.value=(filters[ci]&&filters[ci].type==='text')?filters[ci].q:'';
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
  q.addEventListener('input',function(){term=q.value.trim().toLowerCase(); apply();});
  var commSel=document.getElementById('commSel');
  if(commSel) commSel.addEventListener('change',function(){commFilter=commSel.value; apply();});
  var msort=document.getElementById('msort');
  if(msort) msort.addEventListener('change',function(){if(!msort.value)return; var pr=msort.value.split('.'); doSort(+pr[0], pr[1]==='desc'?-1:1);});
  var bTotal=document.querySelectorAll('#boardList input').length;
  function boardLabel(){
    if(boardPick.size===0||boardPick.size===bTotal) return 'All boards';
    if(boardPick.size===1) return boardName[Array.from(boardPick)[0]]||'1 board';
    return boardPick.size+' boards';
  }
  function updBoard(){
    var bb=document.getElementById('boardBtn'); if(bb) bb.innerHTML=boardLabel()+' \\u25be';
    var lk=document.getElementById('stmtLink');
    if(lk) lk.href=(boardPick.size===1)?(boardPdf[Array.from(boardPick)[0]]||repoDir):repoDir;
    var h1b=document.getElementById('h1board');
    if(h1b) h1b.textContent=(boardPick.size===1)?(boardFull[Array.from(boardPick)[0]]||'Community Boards'):((boardPick.size===0||boardPick.size===bTotal)?'NYC Community Boards':(boardPick.size+' Community Boards'));
    apply();
  }
  [].forEach.call(document.querySelectorAll('#boardList input'),function(c){
    if(c.checked) boardPick.add(c.value);
    c.addEventListener('change',function(){ if(c.checked)boardPick.add(c.value); else boardPick.delete(c.value); updBoard(); });
  });
  [].forEach.call(document.querySelectorAll('#boardPanel .cm-mini'),function(b){
    b.addEventListener('click',function(){ var on=b.dataset.act==='all';
      [].forEach.call(document.querySelectorAll('#boardList input'),function(c){c.checked=on; if(on)boardPick.add(c.value); else boardPick.delete(c.value);});
      updBoard(); });
  });
  var bSearch=document.getElementById('boardSearch');
  if(bSearch) bSearch.addEventListener('input',function(){ var t=bSearch.value.toLowerCase();
    [].forEach.call(document.querySelectorAll('#boardList .cm-opt'),function(o){o.style.display=(o.dataset.name||'').toLowerCase().indexOf(t)>-1?'':'none';}); });
  var bBtn=document.getElementById('boardBtn');
  if(bBtn) bBtn.addEventListener('click',function(e){e.stopPropagation(); var pp=document.getElementById('boardPanel'); pp.style.display=pp.style.display==='none'?'block':'none';});
  var bPanel=document.getElementById('boardPanel'); if(bPanel) bPanel.addEventListener('click',function(e){e.stopPropagation();});
  function csvCell(s){s=(s==null?'':String(s)).replace(/\\s+/g,' ').trim(); return /[",]/.test(s)?('"'+s.replace(/"/g,'""')+'"'):s;}
  function downloadCSV(){
    var cols=ths.map(function(t){return t.dataset.label;}).concat(['Committees']);
    var lines=[cols.map(csvCell).join(',')];
    rows.forEach(function(tr){ if(tr.classList.contains('hide')) return;
      var c=[]; for(var i=0;i<ths.length;i++) c.push(csvCell(cell(tr,i)));
      c.push(csvCell((tr.dataset.committees||'').split('|').join('; ')));
      lines.push(c.join(',')); });
    var blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{type:'text/csv;charset=utf-8;'});
    var url=URL.createObjectURL(blob), a=document.createElement('a');
    a.href=url; a.download='CB2_FY2027_'+(commFilter?commFilter.replace(/[^a-z0-9]+/gi,'_'):'requests')+'.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function(){URL.revokeObjectURL(url);},1500);
  }
  var dlBtn=document.getElementById('dlBtn'); if(dlBtn) dlBtn.addEventListener('click',downloadCSV);
  function setStick(){var c=document.querySelector('.controls'); if(c) document.documentElement.style.setProperty('--ch', c.offsetHeight+'px');}
  setStick(); window.addEventListener('resize', setStick);
  var urlReady=false;
  function colKey(i){return 'c_'+(ths[i].dataset.label||'').toLowerCase().replace(/[^a-z0-9]+/g,'');}
  function writeURL(){
    if(!urlReady) return;
    var p=new URLSearchParams();
    if(boardPick.size===0||boardPick.size===bTotal) p.set('board','all');
    else p.set('board',Array.from(boardPick).join(','));
    if(term) p.set('q',term);
    if(commFilter) p.set('committee',commFilter);
    ths.forEach(function(t,i){var f=filters[i]; if(!f) return; var k=colKey(i);
      if(f.type==='set'){Object.keys(f.allowed).forEach(function(v){p.append(k,v);});}
      else if(f.type==='text'){p.set(k,f.q);}});
    if(sortCol>=0) p.set('sort',colKey(sortCol).slice(2)+(sortDir===1?'.asc':'.desc'));
    var qs=p.toString();
    try{history.replaceState(null,'',qs?('?'+qs):location.pathname);}catch(e){}
  }
  function readURL(){
    var p=new URLSearchParams(location.search);
    // compat: map v2-card-explorer params onto the column filters
    if(p.has('agency')&&!p.has('c_agency')) p.set('c_agency',p.get('agency'));
    if(p.has('type')&&!p.has('c_type')) p.set('c_type',p.get('type'));
    if(p.has('stance')&&!p.has('c_agencystance'))
      p.set('c_agencystance',p.get('stance')==='Neutral'?'Neutral/Unclear':p.get('stance'));
    if(p.has('sort')&&p.get('sort').indexOf('stance.')===0) p.set('sort','agency'+p.get('sort'));
    if(p.has('board')){ var bv=p.get('board');
      if(bv==='all'){ boardPick=new Set();
        [].forEach.call(document.querySelectorAll('#boardList input'),function(c){c.checked=true; boardPick.add(c.value);}); }
      else { boardPick=new Set(bv.split(',').filter(Boolean));
        [].forEach.call(document.querySelectorAll('#boardList input'),function(c){c.checked=boardPick.has(c.value);}); } }
    if(p.has('q')){ var v=p.get('q'); term=v.toLowerCase(); q.value=v; }
    if(p.has('committee')){ commFilter=p.get('committee'); if(commSel) commSel.value=commFilter; }
    var slug2ci={}; ths.forEach(function(t,i){slug2ci[colKey(i)]=i;});
    Object.keys(slug2ci).forEach(function(k){ if(!p.has(k)) return;
      var ci=slug2ci[k], vals=p.getAll(k);
      if(distinct(ci).length<=30){var al={}; vals.forEach(function(v){al[v]=1;}); filters[ci]={type:'set',allowed:al};}
      else {filters[ci]={type:'text',q:(vals[0]||'').toLowerCase()};}
    });
    if(p.has('sort')){var sp=p.get('sort'), dot=sp.lastIndexOf('.'),
      sl=(dot>0?sp.slice(0,dot):sp), dir=(dot>0&&sp.slice(dot+1)==='desc')?-1:1,
      sci=slug2ci['c_'+sl]; if(sci!=null) doSort(sci,dir);}
  }
  readURL(); urlReady=true;
  updBoard();
})();
</script>
</body></html>
"""

parts = [HEAD, '<header>']
parts.append('<h1><span id="h1board">Queens Community Board 2</span> &mdash; FY2027 Budget Requests &amp; Agency Responses</h1>')
parts.append('<p class="sub">The <b>Agency Response</b> '
             f'(<a id="stmtLink" href="{REPO_DIR}" target="_blank" rel="noopener">FY2027 Statement PDF</a>) '
             'and the <b>OMB Executive Response</b> '
             f'(from NYC Open Data <a href="{REG_URL}" target="_blank" rel="noopener">Register of Community '
             'Board Budget Requests</a>).</p>')
parts.append('<div class="cards">')
for k, key in [("Requests", "requests"), ("Expense", "expense"), ("Capital", "capital"),
               ("Support", "support"), ("Oppose", "oppose"), ("Neutral/Unclear", "neutral")]:
    parts.append(f'<div class="card"><div class="k">{k}</div><div class="v" data-card="{key}">0</div></div>')
parts.append('</div>')
parts.append('</header>')

parts.append('<div class="controls">')
parts.append('<input id="q" type="search" placeholder="Search all columns…">')
parts.append('<div class="bsel"><button id="boardBtn" class="commsel boardbtn" title="Filter by community board">Queens CB2 &#9662;</button>'
             '<div id="boardPanel" class="boardpanel" style="display:none">'
             '<input id="boardSearch" class="cm-search" placeholder="search boards…">'
             '<div class="cm-ctrl"><button type="button" class="cm-mini" data-act="all">All</button>'
             '<button type="button" class="cm-mini" data-act="none">None</button></div>'
             '<div class="cm-list" id="boardList">' + board_checklist + '</div></div></div>')
parts.append('<select id="commSel" class="commsel" '
             'title="Filter by committee (CB2 taxonomy). Queens CB2: as submitted via the '
             'committee form; all other boards: inferred from the responsible agency and '
             'request text.">'
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
parts.append('<span class="hint">Click a column name to sort; click its &#9662; funnel to filter</span>')
parts.append('<span id="count" class="count"></span>')
parts.append('</div>')

parts.append('<div class="wrap"><table>' + colgroup + '<thead><tr>' + header_cells + '</tr></thead><tbody>')
parts.extend(body)
parts.append('</tbody></table></div>')
parts.append('<script>window.boardPdf=' + json.dumps(board_pdf) + ';window.repoDir=' + json.dumps(REPO_DIR) + ';window.boardName=' + json.dumps(board_name) + ';window.boardFull=' + json.dumps(board_full) + ';</script>')
parts.append(SCRIPT)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))

print(f"Wrote {OUT}  ({len(df)} rows, {len(DISPLAY)} columns)")
