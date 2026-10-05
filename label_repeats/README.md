# Reworded requests

Boards rewrite their budget requests from year to year. `pipeline/enrich_years.py` links a
board's requests across years when the first 150 characters of one explanation appear in
the other, so a reworded request used to start its history over. This folder finds the
reworded requests that a model judges to be the same request and writes them to
`pipeline/repeat_links.csv`. `enrich_years.py` adds those links to its own. The dashboard's
Years Requested column, the summary page's repeat-request line and the letters' request
history all follow.

## Method

1. `prepare.py` pairs each request that has no link to the year before with the same
   board's most similar request from that year. Similarity is the cosine of TF-IDF vectors
   over the title and explanation, so rare words such as a park, school or street name count
   most. It keeps pairs with a similarity of 0.30 or more.
2. Claude Sonnet agents judged each pair with `rubric.md`, about 180 pairs per agent. The
   test is whether granting one request would grant the other. The wording, the reason, the
   amount, the title and a related agency may change. A different site, or different work
   at the same site, makes a different request. A pair judged `unsure` is not linked.
3. `assemble.py` checks that every pair has a verdict, keeps at most one match per request
   per year, applies the rulings in `resolved.json`, and writes the CSV. A pair in which
   neither request has an explanation counts as unsure, since a DCP category title alone in
   both years does not show what was asked. The `judge` column says which verdicts came from
   Sonnet, from that rule, or from a ruling.

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
  judged unsure. Every disagreement was then ruled on by hand (`resolved.json`, 64 rulings).
  Where the place mattered, the ruling checked the Register's street columns, which the
  FY2020 to FY2025 explanations leave out. 6 of the 500 random links were wrong, so about
  99% of the links are right. Most of the six rested on a line such as "To prevent flooding
  and property damage." with no request or place. The hard cases held 6 wrong links among
  150 and 12 missed links among the 50 unsure pairs, all now fixed.
- **Final.** 3,439 pairs judged the same request, 742 different and 226 unsure.
- **Left out.** Pairs below 0.30 similarity. In the pilot, about 2% of them were the same
  request.

## Effect

In FY2027, requests made in at least three budget years went from 1,997 to 2,535 of 3,809.
Requests made every year since FY2020 went from 561 to 1,191. Queens CB2's FY2026 requests
made in at least three years went from 26 to 60.

## A new fiscal year

1. Build the year's CSV and run `pipeline/enrich_years.py`, as `update.sh` does.
2. Run `prepare.py DATA_DIR WORK_DIR`. It leaves out the pairs already in
   `pipeline/repeat_links.csv`, so only the new year's pairs remain, about 500 to 700.
3. Judge each chunk with `rubric.md` and write `WORK_DIR/out/pairs_NN.json`.
4. Run `assemble.py WORK_DIR`, which adds the new verdicts to the CSV, then run
   `enrich_years.py` again and rebuild the pages.
