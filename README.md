# NYC Community Board Budget Requests Dashboard (FY2027)

A browsable dashboard of community board budget requests and the city's responses to
them, for **all 59 NYC community boards**. It joins two sources the city publishes
separately:

- the **full agency response** to each request, which only appears in each board's
  *Statement of Community District Needs* PDF, and
- **OMB's Executive response**, which only appears in the open-data *Register of
  Community Board Budget Requests*.

The result is a two-stage view of each request: what the board asked for, what the
agency said, and what OMB said afterward.

**Live:** https://cb2-budget-requests-fy2027.vercel.app

The dashboard is a single self-contained `index.html` (~7 MB, all data embedded
inline, no backend and no external JS), deployed as a Vercel static site. It opens
on Queens CB2 but every board is in the file and selectable.

## Repo layout

| Path | What it is |
| --- | --- |
| `index.html` | The built dashboard. Generated, but committed so the site deploys. |
| `pipeline/parse_statement_pdf.py` | One Statement PDF (as `pdftotext -layout` text) into structured rows. Each request is a two-column block: the board's explanation on the left, the agency's response on the right. |
| `pipeline/build_statement_sheet.py` | One board's two-stage sheet. Joins the PDF parse to the Register on explanation text, derives Capital/Expense from the tracking-code suffix, and assigns committees. |
| `pipeline/build_all_boards.py` | Driver. Fetches and parses all 59 Statement PDFs in parallel, runs the per-board build, concatenates into one all-boards CSV. |
| `pipeline/generate_cb2_html.py` | The all-boards CSV into `index.html`. Sorting, filtering, and CSV export are generated inline. |
| `pipeline/build_cb2_register.py` | Standalone: rebuilds a CB2-only sheet from the open-data Register alone, without the PDFs. |
| `pipeline/committee_labels.csv` | The committee for each request, keyed by request id. Produced by `label_committees/`. |
| `label_committees/` | The committee definitions, labeling scripts and validation. See its README. |
| `update.sh` | Runs the whole pipeline and redeploys. |

Statement PDFs come from DCP's public
[NYCPlanning/labs-cd-needs-statements](https://github.com/NYCPlanning/labs-cd-needs-statements)
repo; the Register comes from NYC Open Data dataset `vn4m-mk4t`.

## Rebuilding

Requires `python3` with `pandas`, `pdftotext` (poppler), and the `vercel` CLI.

```sh
./update.sh            # data scratch dir defaults to ~/Downloads
DATA=/some/dir ./update.sh
```

Code runs from `pipeline/`; the downloaded PDFs, the Register CSV, and the
intermediate per-board CSVs are written to the data directory and are gitignored.

When only the build logic or the committee labels change, skip the download and
the PDF parsing. Run this from the data directory. It takes about a minute.

```sh
python3 ~/cb2-budget-requests-fy2027/pipeline/build_all_boards.py --reuse-parsed
```

### One input is not in this repo

`build_all_boards.py` expects a committee-assignment form export:

    Submitting Budget Requests to Budget Committee (Responses) - Form Responses 1.csv

That is a CB2 internal Google Form containing the names of the board members who
filed each request, so it is deliberately not published here. It is used **only** to
give Queens CB2 exact committee assignments. Without it the build still works, and
CB2's committees come from `pipeline/committee_labels.csv` like every other board's.
Those labels match the form's primary committee for 58 of CB2's 65 requests.

## Generalizing to other years and boards

The **board** dimension is already general: `build_all_boards.py` iterates all five
boroughs (`PREFIX`, `MAXCB`) and `build_statement_sheet.py` takes `BORO` and `CB` as
arguments.

The **fiscal year** is still hardcoded. To move to another FY, these are the places
that need to change:

| File | Line | What is hardcoded |
| --- | --- | --- |
| `update.sh` | 16 | Register query: `publication='20270217' OR '20260512'` (the Executive and Preliminary publication dates) |
| `update.sh` | 12, 21 | Combined-CSV and built-HTML filenames |
| `pipeline/build_all_boards.py` | 19 | `REGISTER` filename |
| `pipeline/build_all_boards.py` | 26 | PDF URL path: `{pre} DNS FY 2027/FY2027_Statement_{code}.pdf` |
| `pipeline/build_all_boards.py` | 86 | Output CSV filename |
| `pipeline/build_statement_sheet.py` | 151 | Register row filter `d["fy"] == "2027"` |
| `pipeline/generate_cb2_html.py` | 13, 14, 17, 28 | Default in/out filenames, DCP repo directory, per-board PDF links |
| `pipeline/generate_cb2_html.py` | 73, 79, 146, 406, 462, 464 | Column help text, page title, CSV export filename, `<h1>`, Statement link label |

The other CB2-specific piece is the **committee taxonomy**. Every board's requests
are labeled with CB2's seven committees, defined in `label_committees/rubric.md`. A
new fiscal year needs new labels, and `label_committees/README.md` describes how to
produce them. Until then, unlabeled requests fall back to the agency and keyword rule
in `build_statement_sheet.py`, and the build log says how many did. A board with a
different committee structure would need its own rubric and its own labels.
