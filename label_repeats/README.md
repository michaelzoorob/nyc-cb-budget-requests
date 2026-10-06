# Reworded requests

Boards rewrite their budget requests from year to year. `pipeline/enrich_years.py` links a
board's requests across years when the first 150 characters of one explanation appear in
the other, so a reworded request used to start its history over. This folder finds the
reworded requests that a model judges to be the same request and writes them to
`pipeline/repeat_links.csv`. `enrich_years.py` adds those links to its own. The dashboard's
Years Requested column, the summary page's repeat-request line and the letters' request
history all follow.

A board may also send one text for several sites, such as one paragraph on speeding for each
of four streets. The same text in two years is then two requests when the sites differ. This
folder judges those pairs too.

## Method

1. `prepare.py` pairs each request that has no link to the year before with the same
   board's most similar request from that year. Similarity is the cosine of TF-IDF vectors
   over the title and explanation, so rare words such as a park, school or street name count
   most. It keeps pairs with a similarity of 0.30 or more.
2. Claude Sonnet agents judged each pair with `rubric.md`, about 180 pairs per agent. The
   test is whether granting one request would grant the other. The wording, the reason, the
   amount, the title and a related agency may change. A different site, or different work
   at the same site, makes a different request. A pair judged `unsure` is not linked. A
   request from FY2020 to FY2025 shows the judge the site that the City's Register records
   for it (its Location column).
3. `assemble.py` checks that every pair has a verdict, keeps at most one match per request
   per year, applies the rulings in `resolved.json`, and writes the CSV. A pair in which
   neither request has an explanation counts as unsure, since a DCP category title alone in
   both years does not show what was asked. The `judge` column says which verdicts came from
   Sonnet, from that rule, or from a ruling.
4. `prepare.py --sites` pairs the same text in two years when both requests name a site and
   the sites are not plainly one place (`shared.site_match`). Plainly one place means the
   same main street with cross streets in common, or one corner named the other way round.
   The judges decide the rest with the same rubric, since the Register may also name one
   site in several ways. These pairs have `kind` set to `site`, and they name each request
   by its site key (`shared.site_key`, the Label ID with a short hash of the site).
   `enrich_years.py` links such a pair only when it was judged the same request.
5. `prepare.py --gaps` covers a request the board skipped for a year or two. A request with
   no link to the year before is paired with its most similar request two or three years
   earlier, at a similarity of 0.30 or more, when neither appears in the years between. The
   judges use the same rubric.

`enrich_years.py` makes the strongest links first: the same text, then a shared opening,
then pairs a model judged, closest first. A judged link, or one that rests only on a shared
opening, never joins two histories that each hold a different request from the same year.
The board listed those side by side, so they are two requests, such as Queens CB3's housing
for seniors and housing for families, or the Morris-Jumel Mansion's repairs and its
water-damage work in Manhattan CB12. Two rows from one year with the same text and site
count as one request listed twice. Two requests judged different never end up in one
history through a third. A request without a site does not link to the same text that the
board sent for several sites in another year, since a general request and a specific one
are different requests. When a board splits one request in two, its earlier years go to one
side only.

## Checks

- **Pilot.** 198 pairs, including all 122 Queens CB2 pairs into FY2026 and FY2027. Sonnet
  and a blind Opus judge agreed on 92% of them. Sonnet's two errors linked one board's
  street reconstruction request to its sewer request for the same blocks. The rubric now
  calls those different requests, and a request keeps only its closest match.
- **Full run.** 4,407 pairs from FY2021 to FY2027. Sonnet judged 3,449 the same request,
  732 different and 226 unsure.
- **Validation.** Four blind Opus reviews of 200 pairs each, with no pair in two of them.
  Three drew links at random (500 in all) and agreed with 488 of them. The fourth drew hard
  cases: 100 links with low similarity, 50 links with a very short explanation, and 50 pairs
  judged unsure. Every disagreement was then ruled on by hand (`resolved.json`). 6 of the 500
  random links were wrong, so about 99% of the links are right. Most of the six rested on a
  line such as "To prevent flooding and property damage." with no request or place. The hard
  cases held 6 wrong links among 150 and 12 missed links among the 50 unsure pairs, all now
  fixed.
- **Register sites.** Sonnet judged again the 1,155 pairs in which either request has a
  Register site, this time with the site shown. 64 verdicts changed, and a blind Opus check
  of those 64 led to 21 rulings by hand.
- **The same text at two sites.** 1,011 pairs from FY2020 to FY2027. Sonnet judged 219 the
  same request, 788 different and 4 unsure. Brooklyn CB9 and CB3 account for 749 of them,
  since both send one text for many streets or intersections. A board that lists both sites
  as separate requests in one year has made two requests, and 780 of the 788 different
  verdicts were on such pairs. 5 same verdicts were too, and 4 of those were wrong. A blind
  Opus review of 200 pairs agreed with 190. It held 120 same verdicts drawn at random, one of
  them wrong (two playgrounds in St. Nicholas Park), and 71 different verdicts, one of them
  wrong (one stretch of Commonwealth Boulevard). Every disagreement was ruled on by hand.
- **Requests that lost a link.** Once the same text at two sites stopped linking, 43
  requests were paired again with the year before. Every verdict was read by hand, 4 were
  ruled on, and one missed pair was added (Brooklyn CB3's Lafayette Gardens request). 36
  earlier verdicts named a text that a board sent for two sites in one year by its Label ID
  alone. They were dropped, and those requests were judged again with their sites.
- **Skipped years.** 524 pairs of a request two or three years apart. Sonnet judged 184 the
  same request, 286 different and 54 unsure. Blind Opus reviews covered all 184 same verdicts
  and 20 others. They disagreed on 15, 14 of them same verdicts, most a district-wide request
  paired with a later request for one of its sites. Each was ruled on by hand.
- **Final.** 5,081 reworded pairs, of which 3,634 were judged the same request, 1,162
  different and 285 unsure. 1,011 site pairs, of which 214 were judged the same request and
  797 different. `resolved.json` holds 114 rulings.
- **Live audit.** 300 requests drawn at random from the live site in October 2026, weighted
  to FY2027 and FY2026. Sonnet read each linked year against the request it links to, and
  the closest request in each year left out. Of 1,288 linked years, 532 were the same text
  and 714 of the other 756 were judged the same request. 29 were wrong, nearly all because a
  judged link joined two requests that the board lists side by side. The rule above now
  removes 27 of them and keeps every same-text link. It also removes 25 links the audit
  judged the same, and in each of those the board had listed both versions in one year.
- **Left out.** Pairs below 0.30 similarity, a request's second-best match, and requests four
  or more years apart. In the pilot, about 2% of pairs below 0.30 were the same request. The
  live audit found 37 years left out among its 300 requests that were in fact the same
  request. The skipped-year pairs recovered 19 of them. Most of the rest fall just below 0.30
  or were a request's second-best match.

## Effect

In FY2027, requests made in at least three budget years went from 1,997 to 2,530 of 3,809.
Requests made every year since FY2020 went from 557 to 1,153. Queens CB2's FY2026 requests
made in at least three years went from 26 to 62.

## A new fiscal year

1. Build the year's CSV and run `pipeline/enrich_years.py`, as `update.sh` does. It prints
   how many pairs of the same text at two sites await a judge.
2. Run `prepare.py DATA_DIR WORK_DIR --sites`, judge each chunk with `rubric.md` (write
   `WORK_DIR/out/pairs_NN.json`), run `assemble.py WORK_DIR`, and run `enrich_years.py`
   again.
3. Run `prepare.py DATA_DIR WORK_DIR` with a new work folder. It leaves out the pairs already
   in `pipeline/repeat_links.csv`, so only the new year's pairs remain, about 500 to 700.
4. Judge each chunk in the same way and run `assemble.py WORK_DIR`. Then run
   `enrich_years.py` again.
5. Run `prepare.py DATA_DIR WORK_DIR --gaps` with a new work folder, judge it the same way,
   run `assemble.py WORK_DIR` and `enrich_years.py`, and rebuild the pages.
