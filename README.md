# NYC Community Board Budget Requests Dashboard

A browsable dashboard of community board budget requests and the city's responses to
them, for **all 59 NYC community boards** and **fiscal years 2020 through 2027**. Each
request shows what the board asked for, how the responsible agency responded, and
OMB's Executive Budget response.

**Live:** https://nyc-cb-budget-requests.vercel.app

The site root is a map of the 59 community districts. Clicking a district opens its
requests on the dashboard, which shows the latest year at `/dashboard/`. Earlier years are at
`/fy2026/`, `/fy2025/` and so on. The Year menu switches between them and keeps the board,
committee, search and column filters. The address shows `?board=all` when every board is
selected. A link such as `/dashboard/?board=QCB2` opens one board,
and `?year=2024&board=QCB2` also works. Older links to `/?board=...` and `/home/` forward to the
right page.

Each year is one self-contained HTML page of 7 to 10 MB, with the data embedded inline
and no backend or external JS. The pages are deployed as a Vercel static site.

## Filtering and sharing a view

The summary cards above the table are filters. Expense and Capital filter the Type
column, and Support, Oppose and Neutral/Unclear filter the Agency Stance column.
Requests clears both. In a row, clicking the type, agency, years requested, stance or follow-up shows
only the requests with that value. Clicking the board narrows the board menu to that
board. Clicking the same value again removes the filter. The follow-up cards work the
same way. Each column filter in use appears as a label above the table. Clicking the
label opens that column's filter menu, which is how a phone reaches it, and its × removes
the filter.

Every filter is saved in the page's address, so a copied link opens the same view.

| Parameter | What it sets |
| --- | --- |
| `year` | Opens that year's page, as in `?year=2024&board=QCB2`. |
| `board` | The boards shown, as in `board=QCB1,QCB2`. |
| `board=all&xboard=` | Every board except those listed in `xboard`. A switch to a year with other boards keeps this form. |
| `q` | The search box. |
| `committee` | The committee menu. |
| `c_<column>` | A column filter. The name is the column's name in lowercase without spaces or punctuation, such as `c_agency`, `c_type`, `c_yearsrequested`, `c_agencystance` or `c_followup`. Priority, Type, Board, Agency, Years Requested, Agency Stance and Follow-up take checkbox filters, which repeat the parameter for each value kept (`c_agency=Fire Department&c_agency=Police Department`). The value `__none__` keeps none. The other columns take text, as in `c_title=school`. |
| `sort` | The sort column and direction, as in `sort=priority.desc`. |
| `fu` | `fu=unsent` shows requests that need follow-up and have no letter marked sent. `fu=sent` shows requests with a letter marked sent. Both use the marks saved in the viewer's browser. |

Agency used to take text, so an older link such as `?c_agency=parks` still shows every
agency whose name contains that text.

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
requests from Brooklyn CB6, CB12 or CB16, and none from Brooklyn CB6 in FY2020. OMB's
January and April 2024 Register files leave out the same three boards. Brooklyn CB16's
FY2025 Statement lists its 70 requests, so the site shows them. No agency or OMB response
to them was published. DCP published no Statement in the other cases, so those boards are
absent from those years.

Priority numbers mean different things in different years. In FY2027 a board ranks its
requests to each agency separately, so several requests share each number. In earlier
years a board ranks its whole capital list and its whole expense list.

The Register has no agency round for FY2019 and no data before it, so earlier years are
not included.

## Repo layout

| Path | What it is |
| --- | --- |
| `index.html` | The home page, a map of the community districts built by `home/build_map.py`. |
| `summary/index.html` | How agencies answered the requests, by agency and by board, for each year, and how many requests the boards made in at least three budget years. Built by `pipeline/build_summary.py`. |
| `dashboard/index.html`, `fy<YEAR>/index.html` | The dashboard pages, with the latest year at `/dashboard/`. Generated, but committed. |
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
| `pipeline/locate_requests.py`, `pipeline/request_locations.csv` | The council district of each request whose site is known, from the park or street intersection it names. |
| `pipeline/enrich_years.py` | Links each request to the same board's requests in other years, and adds the site's council district, to every year's CSV. |
| `pipeline/letter_facts.py`, `pipeline/letter_facts.csv` | The letters' local data. A sentence or two from the City's open data about a request's site or need, with its source. Downloads are cached in the data directory. |
| `pipeline/build_contacts.py`, `pipeline/contacts/` | The follow-up letters' recipients, with Council Members by district, Borough Presidents and agency offices. See its README. |
| `label_followup/` | The follow-up rubric, labeling scripts and validation. See its README. |
| `label_committees/` | The committee definitions, labeling scripts and validation. See its README. |
| `plan/index.html` | The next-cycle planner at `/plan/?board=QCB2`: a board's 311 conditions next to its requests, how the City answers each request category, and the district profile. Static; reads `plan/planner.json`. |
| `pipeline/build_planner_data.py`, `plan/planner.json` | The next-cycle planner's data: 311 need rates per board over three years, the district profile from nyc-cd-atlas, which Register requests address each need, and how agencies have answered each request category. Standard library only; run it from `pipeline/`. |
| `update.sh` | Rebuilds every year's page. Merging them into `main` deploys them. |

## Rebuilding

Requires `python3` with `pandas` and `pdftotext` (poppler).

```sh
./update.sh              # full rebuild; the data directory defaults to ~/Downloads
REUSE=1 ./update.sh      # reuse parsed PDFs and Registers (labels or post-parse code changed)
DATA=/some/dir ./update.sh
```

Code runs from `pipeline/`. Downloaded Registers and intermediate CSVs go to the data
directory, and Statement PDFs with their text go to its `statement_text/` folder. After
every year is built, `update.sh` runs `locate_requests.py` and `enrich_years.py`, since
both read all the years at once, and then writes the pages. Use
`REUSE=1` only when the PDF parser is unchanged, since it skips re-parsing. To rebuild
one year's page after the other years exist, run these from the data directory.

```sh
python3 ~/cb2-budget-requests-fy2027/pipeline/build_all_boards.py --fy 2025
python3 ~/cb2-budget-requests-fy2027/pipeline/enrich_years.py .
python3 ~/cb2-budget-requests-fy2027/pipeline/generate_cb2_html.py --fy 2025 \
    "CB FY2025 Requests (all boards, detailed, 2-stage).csv" ~/cb2-budget-requests-fy2027/fy2025/index.html
```

### Deploying

`main` is protected, so every change goes through a pull request. Vercel builds a
preview of each pull request and deploys `main` to the live site when a pull request
merges. Nobody deploys from their own machine. The page files are rewritten on every
rebuild, so two pull requests that both rebuild pages will conflict. If yours does,
rebase onto `main` and rerun the generator instead of merging the HTML by hand.

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
4. Run `./update.sh`, then open a pull request with the rebuilt pages.

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

A count of each step appears above the table. Clicking a count, clicking the step in a row, or choosing a step in the Follow-up menu shows only those requests. The menu can also show the requests that still need follow-up and have not been marked sent. The Marked sent count, or the menu, shows the requests with a letter marked sent.

The Draft letter button opens a panel of recipients. Depending on the step, it pre-selects the agency's office for the board (or the office of the agency a response points to, when the response says another agency handles the request), the Council Member for the request and the Borough President. For a request whose obstacle is money, it pre-selects the Borough President's budget office. It drafts a separate letter for each recipient or one joint letter. Each letter describes the request and the agency's response in plain words (from `pipeline/letter_descriptions.csv`, see `label_letters/`), gives the tracking code, and says how many budget years the board has made the request. OMB's Executive Budget response appears as a short summary when it bears on the letter, such as OMB's recommendation to bring a request to elected officials, and is left out when it only restates the agency or refers the board back to it. A letter to elected officials asks them to advocate for the request in the City's budget, and for a capital project also to consider Reso A funds. The letter opens in the viewer's email program, or it can be copied into an agency's contact form. The page drafts letters in the browser from fixed templates and sends nothing itself.

The Draft one letter per official button writes one letter to each official for all the requests shown, with each request's own recipients. With the Contact elected officials filter on, for example, each Council Member gets a single letter listing that member's requests.

The Council Member for a request is the member whose district holds the request's site, when the site is known. `pipeline/locate_requests.py` places a request that names a park with NYC Parks Properties, and a Statement explanation that begins with a street and its cross streets with the NYC Street Centerline. It keeps a site only if the site lies in one of the board's own council districts. It places 2,182 of the 16,872 distinct requests from FY2020 to FY2027 (identical requests in different years count once), 1,730 by park and 452 by street intersection. The letters for other requests go to the Council Members whose districts cover at least 10% of the board's land area.

A letter can also cite local data, a sentence or two from the City's open data about the request's site or need. `pipeline/letter_facts.py` writes them to `pipeline/letter_facts.csv`. It adds a fact only where the fact clearly applies to the request and supports it, so most requests get none. Of the 16,872 distinct requests from FY2020 to FY2027, 2,504 get one. A fact's topic must appear in the request's title or the first two sentences of its explanation. A site comes from the request's location line or the park it names, and must lie in the board's own district.

| Kind | For | What the letter says | Source |
| --- | --- | --- | --- |
| Park inspections | A Parks request about one named park | How often NYC Parks inspectors rated the park, or the feature the request is about, unacceptable in the last two years. At least two such ratings. Large parks inspected zone by zone are left out. | [Parks Inspection Program](https://data.cityofnewyork.us/d/yg3y-7juh) |
| School | A school request that names one school | The school's enrollment, and its share of target capacity when that is over 100%. A request for more seats gets the fact only then. | [Enrollment, Capacity and Utilization](https://data.cityofnewyork.us/d/gkd7-3vk7) |
| Crashes | A traffic safety request at a located intersection or street | Crashes, injuries and deaths within 150 feet of the intersection, or along the street, over the last three years | [Motor Vehicle Collisions](https://data.cityofnewyork.us/d/h9gi-nx95) |
| 311 at the site | A request about flooding, sewer backups, street lights, a broken signal or speeding at a located site | 311 reports nearby over the last three years. 311 logs broken signals and takes no requests for new ones, so a new signal gets the crash count instead. | [311 Service Requests](https://data.cityofnewyork.us/d/erm2-nwe9) |
| Park access | A request for a new park or open space | The share of the district's residents beyond walking distance of a park, when it is above the city's | [Walk to a Park](https://data.cityofnewyork.us/d/99ii-hwh9) and 2020 Census blocks |
| Street trees | A tree planting request | Empty street tree beds in the district | [Forestry Planting Spaces](https://data.cityofnewyork.us/d/82zj-84is) |
| District 311 | A request on a need that 311 measures | The district's 311 complaints in the last year, when its rate or count ranks in the top quarter of districts or the count rose by a quarter in two years | The planner's 311 counts |

The panel lists a request's local data with its source. Each item has a checkbox, and a checked item goes in the letter after the request. Park access follows NYC Parks' method, weighting each Census block by the share of its area within walking distance. Citywide that gives 83.8% of New Yorkers within walking distance of a park. NYC Parks reported 83.9% for FY2023 with the same service area. A check of 14 facts against queries run on NYC Open Data itself found every number the same.

`pipeline/enrich_years.py` links a request to the same board's requests in other years when their explanations begin with the same text. In FY2027, 2,549 of the 3,809 requests also appear in another year. The letter panel lists those years and the most recent earlier response.

The Years Requested column counts the budget years from FY2020 through the page's year in which the board made the request. Because the link rests on the explanation's opening words, a reworded request starts over. In FY2027, 1,997 of the 3,809 requests were made in at least three budget years, and 561 were made every year since FY2020. The column sorts and filters like the others. From FY2022 on, the summary page counts the requests made in at least three budget years and links to them. FY2020 is the first year on the site, so its page has no such column.

Mark as sent records the date and the recipients of a letter, and the Follow-up column then shows the date. A board can also add its own contact for an agency, which the panel offers first for that agency's requests. Both are saved only in the viewer's browser. The CSV download adds the tracking code, the agency a response points to, the reason for the step, the years of the request, and the sent date with its recipients.

Recipients come from `pipeline/contacts/`. `pipeline/build_contacts.py` rebuilds the Council Members and their districts from council.nyc.gov and DCP's district maps. Agency and Borough President contacts were gathered from official websites in September 2026, and every row cites its source page. Agency staff change, so check a contact before relying on it.
