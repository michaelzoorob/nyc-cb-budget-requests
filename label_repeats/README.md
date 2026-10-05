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
   either request has no explanation counts as unsure, since a DCP category title alone does
   not show what was asked. The `judge` column says which verdicts came from Sonnet, from that
   rule, or from a ruling.

## Checks

- **Pilot.** 198 pairs, including all 122 Queens CB2 pairs into FY2026 and FY2027. Sonnet
  and a blind Opus judge agreed on 92% of them. Sonnet's two errors linked one board's
  street reconstruction request to its sewer request for the same blocks. The rubric now
  calls those different requests, and a request keeps only its closest match.
- **Full run.** 4,407 pairs from FY2021 to FY2027. Sonnet judged 3,449 the same request,
  732 different and 226 unsure.
- **Validation.** Two blind Opus judges each took 150 random pairs that Sonnet judged the
  same and 50 random others, with no pair in both samples. Opus agreed with 291 of the 300
  "same" verdicts. Every disagreement was then ruled on by hand (`resolved.json`, 29
  rulings). 6 of the 300 "same" verdicts were wrong, so about 98% of the links are right.
  Most of the six rested on a generic line such as "To prevent flooding and property
  damage." with no request or place. Opus judged 13 of the 100 other pairs the same; on
  review, 2 of them were.
- **Final.** 3,420 pairs judged the same request, 735 different and 252 unsure.
- **Left out.** Pairs below 0.30 similarity. In the pilot, about 2% of them were the same
  request.

## Effect

In FY2027, requests made in at least three budget years went from 1,997 to 2,535 of 3,809.
Requests made every year since FY2020 went from 561 to 1,188. Queens CB2's FY2026 requests
made in at least three years went from 26 to 60.

## A new fiscal year

1. Build the year's CSV and run `pipeline/enrich_years.py`, as `update.sh` does.
2. Run `prepare.py DATA_DIR WORK_DIR`. It leaves out the pairs already in
   `pipeline/repeat_links.csv`, so only the new year's pairs remain, about 500 to 700.
3. Judge each chunk with `rubric.md` and write `WORK_DIR/out/pairs_NN.json`.
4. Run `assemble.py WORK_DIR`, which adds the new verdicts to the CSV, then run
   `enrich_years.py` again and rebuild the pages.
