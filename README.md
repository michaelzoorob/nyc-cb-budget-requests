# NYC Community Board Budget Requests Dashboard

A browsable dashboard of community board budget requests and the city's responses to
them, for **all 59 NYC community boards** and **fiscal years 2020 through 2027**. Each
request shows what the board asked for, how the responsible agency responded, and
OMB's Executive Budget response.

**Live:** https://cb2-budget-requests-fy2027.vercel.app

The site root shows the latest year. Earlier years are at `/fy2026/`, `/fy2025/` and so
on. The Year menu switches between them and keeps the board, committee, search and
column filters. A link such as `?year=2024&board=QCB2` also works.

Each year is one self-contained HTML page of 7 to 9 MB, with the data embedded inline
and no backend or external JS. The pages are deployed as a Vercel static site.

## Where each year's data comes from

| Fiscal years | Board requests and agency responses | OMB Executive response |
| --- | --- | --- |
| FY2026–FY2027 | Each board's *Statement of Community District Needs* PDF, which carries the agency's full written response | NYC Open Data *Register of Community Board Budget Requests* (`vn4m-mk4t`), matched to each request by its text |
| FY2020–FY2025 | The Register's January round of agency responses | The Register's April or May round |

Statement PDFs come from DCP's public
[NYCPlanning/labs-cd-needs-statements](https://github.com/NYCPlanning/labs-cd-needs-statements)
repository. The PDFs before FY2026 either list requests without responses
(FY2017–FY2023) or repeat the Register's text in a table (FY2024–FY2025), so the
Register is the source for those years. Two consequences follow. Agency responses
before FY2026 are usually one or two sentences, because that is what agencies wrote.
Titles before FY2026 are DCP's standard request categories, because boards' own titles
first appear in the FY2026 PDFs.

The FY2026 Bronx PDFs print each request in a four-column table without the agency's
response. The Bronx boards therefore take their responses from the Register and their own
request titles from that table (`pipeline/parse_request_table.py`). Bronx CB12 is missing
from the FY2026 Register, so its 11 requests come from its PDF alone and show no
responses. DCP's FY2026 file for Manhattan CB7 holds CB6's requests, so Manhattan CB7
comes entirely from the Register. The build catches a mismatched file like that one by
checking that a PDF's requests match the board's own Register entries.

Three boards are missing from the Register in some years. The Register has no FY2025
requests from Brooklyn CB6, CB12 or CB16, and none from Brooklyn CB6 in FY2020. Brooklyn
CB16's FY2025 Statement lists its requests in a five-column table, so they appear without
responses. DCP published no Statement in the other cases, so those boards are absent from
those years.

Priority numbers mean different things in different years. In FY2027 a board ranks its
requests to each agency separately, so several requests share each number. In earlier
years a board ranks its whole capital list and its whole expense list.

The Register has no agency round for FY2019 and no data before it, so earlier years are
not included.

## Repo layout

| Path | What it is |
| --- | --- |
| `index.html`, `fy<YEAR>/index.html` | The built pages, with the latest year at the root. Generated, but committed. |
| `pipeline/shared.py` | The fiscal years, each year's Register publications, agency names, request ids, the stance rule and the committee fallback. Every builder imports it. |
| `pipeline/build_all_boards.py` | Builds one year (`--fy YEAR`). For a PDF year it fetches and parses all 59 Statement PDFs in parallel, builds each board, and falls back to the Register for a board whose PDF lacks per-request responses or holds another board's requests. Other years come from the Register, plus the Statement's request table for a board the Register lacks. |
| `pipeline/parse_statement_pdf.py` | One Statement PDF (as `pdftotext -layout` text) into structured rows. |
| `pipeline/build_statement_sheet.py` | One board's two-stage sheet for a PDF year. Joins the PDF parse to the Register on explanation text. |
| `pipeline/build_register_year.py` | A year's sheet from the Register alone, and the per-board fallback for PDF years. |
| `pipeline/parse_request_table.py` | The request tables in PDFs without per-request responses: four columns for the FY2026 Bronx boards, five for Brooklyn CB16 in FY2025. |
| `pipeline/generate_cb2_html.py` | One year's CSV into one page, including the Year menu. |
| `pipeline/build_cb2_register.py` | Standalone. Builds a CB2-only sheet from the Register alone. |
| `pipeline/committee_labels.csv` | The committee for each request, keyed by request id. |
| `pipeline/followup_labels.csv` | The follow-up action for each pair of agency and OMB responses. |
| `pipeline/build_contacts.py`, `pipeline/contacts/` | The follow-up letters' recipients, with Council Members by district, Borough Presidents and agency offices. See its README. |
| `label_followup/` | The follow-up rubric, labeling scripts and validation. See its README. |
| `label_committees/` | The committee definitions, labeling scripts and validation. See its README. |
| `update.sh` | Rebuilds every year and redeploys. |

## Rebuilding

Requires `python3` with `pandas`, `pdftotext` (poppler) and the `vercel` CLI.

```sh
./update.sh              # full rebuild; the data directory defaults to ~/Downloads
REUSE=1 ./update.sh      # reuse parsed PDFs and Registers (labels or post-parse code changed)
DATA=/some/dir ./update.sh
```

Code runs from `pipeline/`. Downloaded Registers and intermediate CSVs go to the data
directory, and Statement PDFs with their text go to its `statement_text/` folder. Use
`REUSE=1` only when the PDF parser is unchanged, since it skips re-parsing. To rebuild
one year, run these from the data directory.

```sh
python3 ~/cb2-budget-requests-fy2027/pipeline/build_all_boards.py --fy 2025
python3 ~/cb2-budget-requests-fy2027/pipeline/generate_cb2_html.py --fy 2025 \
    "CB FY2025 Requests (all boards, detailed, 2-stage).csv" ~/cb2-budget-requests-fy2027/fy2025/index.html
```

### One input is not in this repo

`build_all_boards.py` expects a committee-assignment form export:

    Submitting Budget Requests to Budget Committee (Responses) - Form Responses 1.csv

That is a CB2 internal Google Form containing the names of the board members who
filed each request, so it is deliberately not published here. It gives Queens CB2's
FY2027 requests their exact committee assignments, and it covers only FY2027. Without
it the build still works, and CB2's committees come from `pipeline/committee_labels.csv`
like every other board's. Those labels match the form's primary committee for 58 of
CB2's 65 FY2027 requests.

## Adding a fiscal year

1. Add the year to `YEARS` in `pipeline/shared.py`, with its two Register publications
   in `PUBLICATIONS`. Each year has a January round in which `responded_by` holds an
   agency code, and an April or May round in which it is `OMB`. Grouping the Register
   by `publication` and `responded_by` shows both.
2. If that year's Statement PDFs carry per-request "Agency Response:" blocks, add the
   year to `PDF_YEARS`.
3. Build the year's CSV, then label its new requests with `label_committees/prepare_years.py`
   and `label_committees/assemble_years.py`. Requests resubmitted from earlier years
   keep their existing labels.
4. Run `./update.sh`.

## Committees

Every request is assigned to one of Queens CB2's seven committees, defined in
`label_committees/rubric.md`. CB2's own FY2027 requests take theirs from CB2's
committee form. Everything else is labeled by a model following the rubric, and
`label_committees/README.md` describes the method and its validation. A request with
no label falls back to an agency and keyword rule, and the build log reports how many
did. A board with a different committee structure would need its own rubric and
labels.

## Follow-up letters

The Follow-up column gives the next step for a board that still wants a request. The step is one of these:

- contact the agency
- contact elected officials
- contact both
- track the request with the agency
- use 311 or another channel
- no follow-up needed

A model read each pair of agency and OMB responses and chose the step, following `label_followup/rubric.md`. `label_followup/README.md` describes the method and its validation.

The Draft letter button opens a panel of recipients. Depending on the step, it pre-selects the agency's office for the board, the Council Members whose districts cover at least 10% of the board's land area, and the Borough President. It drafts a separate letter for each recipient or one joint letter. Each letter quotes the request, its tracking code and both responses. The letter opens in the viewer's email program, or it can be copied into an agency's contact form. The page drafts letters in the browser from fixed templates and sends nothing itself.

Recipients come from `pipeline/contacts/`. `pipeline/build_contacts.py` rebuilds the Council Members and their districts from council.nyc.gov and DCP's district maps. Agency and Borough President contacts were gathered from official websites in September 2026, and every row cites its source page. Agency staff change, so check a contact before relying on it.
