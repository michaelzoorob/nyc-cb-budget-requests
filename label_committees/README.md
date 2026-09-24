# Committee labels

The dashboard assigns every budget request to one of Queens CB2's seven committees. CB2's own FY2027 requests take their committee from CB2's committee form. Every other request, in every fiscal year, takes it from `pipeline/committee_labels.csv`, which this folder produces.

## The old rule

The old rule chose a committee from the responsible agency. It appended Engagement and Inclusion when a request's text contained "esol", "language access" or "immigrant", and it tested these as raw substrings. The string "esol" matched "resolution" and "resolve", which placed 35 unrelated requests in Engagement and Inclusion, including DOT street requests and a Union Square garbage request. The agency default also sent requests about a board's own office, staff, website and meeting technology to City Services, because DCAS, OTI and OMB default there. The old rule therefore missed all nine of CB2's own Engagement and Inclusion requests.

## Method

`rubric.md` defines the seven committees. It follows CB2's FY2027 committee-form assignments and the agency defaults in `pipeline/shared.py`. It is the exact prompt the labelers received.

`prepare_chunks.py` splits the requests into chunks. It gives each request the id that the pipeline computes from its board, title and explanation.

Claude Sonnet agents labeled the 3,733 distinct non-CB2 requests in 13 chunks. Each agent read `rubric.md` and one chunk, and it wrote its labels in batches of 50. Each request received one primary committee. A secondary committee was added only when a request sat evenly across two committees.

`assemble_labels.py` validates the labelers' output and writes `pipeline/committee_labels.csv`. It writes nothing if any request is missing, duplicated or given a committee outside the seven. The file also holds the validation labels for CB2's 65 requests (see below). The build uses those only when CB2's private committee form is absent, as in a fork of this repository.

The build reads the labels by id. A request without a label falls back to the agency and keyword rule, which now matches whole words only. The build log reports how many requests fell back on each board.

## Validation

A Sonnet agent labeled CB2's 65 requests without seeing CB2's committees. Ten of those 65 are excluded from scoring, because the code assigned their committees itself when they matched no form entry. On the remaining 55, the labeler matched CB2's primary committee for 50 (91%), and the old agency rule matched 40 (73%). The labeler found all nine of CB2's Engagement and Inclusion requests, and the old rule found none. These figures overstate accuracy somewhat, because `rubric.md` was written after reading CB2's assignments.

An Opus agent labeled a random sample of 100 requests from other boards without seeing the Sonnet labels. The two labelers chose the same primary committee for 96 of the 100, including all 71 requests the Opus labeler rated high confidence. The old agency rule matched the Opus labeler on 82 of the 100. The four disagreements were rodent baiting, bridge rehabilitation, promenade lighting and an EDC cleaning initiative, and the Opus labeler rated each of them medium or low confidence.

Rebuilding the dashboard with the labels changed only the Committees column, and CB2's own committees stayed the same. The primary committee changed for 643 of the 3,741 non-CB2 requests (17%).

## Judgment calls

Three rules in `rubric.md` extend CB2's precedent to cases CB2 never filed. Each is a choice the board may want to revisit.

- **Schools go to Health and Human Services.** CB2 filed no school requests in FY2027. CB2 placed after-school programs in Health and Human Services, and the rubric extends that to education. In FY2027 this moved 275 of the 279 DOE and SCA requests out of City Services, the old catch-all.
- **Street reconstruction, resurfacing and street lighting go to City Services.** Traffic safety, bike lanes, bus service and transit stay in Transportation. This follows CB2's placement of its Winfield street reconstruction request in City Services. In FY2027 it moved 203 of the 609 DOT requests out of Transportation.
- **A board's own operations go to Engagement and Inclusion.** CB2's Engagement and Inclusion requests cover its storefront, website, newsletter, meeting technology and events. The rubric extends that to a board's office, staff, budget and training. In FY2027, 42 of the 59 non-CB2 requests labeled Engagement and Inclusion were filed with OMB, DCAS or OTI and concern board operations.

To change a call, edit `rubric.md` and relabel, or edit `committee_labels.csv` directly.

## Earlier fiscal years

FY2020 through FY2026 hold 25,537 requests. Of those, 4,021 are identical to an FY2027 request and share its label. Another 1,334 reuse the committee of the same board's FY2027 request with the same explanation, which carries CB2's human form assignments back to its resubmitted requests. The remaining 20,182 reduce to 11,566 distinct request texts, because boards resubmit the same request across years. `prepare_years.py` groups them by board and explanation, and each text was labeled once by Claude Sonnet agents following the unchanged `rubric.md`. `assemble_years.py` then wrote the label to every request that shares the text.

An Opus agent labeled a random sample of 100 of these texts without seeing the Sonnet labels. The two chose the same primary committee for 95 of the 100, including all 67 the Opus labeler rated high confidence. The agency and keyword rule matched the Opus labeler on 79. No request in the sample was Engagement and Inclusion, so this check says nothing specific about that committee in earlier years.

Three of the five disagreements were DOT street reconstructions. Across all eight years, DOT's "Reconstruct streets" category splits 77% City Services and 23% Transportation. About 40% of the Transportation share are safety or street-redesign projects, which the rubric sends to Transportation. The other 120 or so are plain reconstructions and sit on the boundary the rubric draws.

A September 2026 audit fixed the PDF parser and rebuilt every year. Fixing a request's title or text changes its id, so 281 such requests were given the label of the same request's old id. Ten new texts were labeled with the same method. They are Brooklyn CB16's FY2025 requests, which come from its Statement, and requests the parser had garbled or dropped.

## Labeling a new fiscal year

1. Add the year to `pipeline/shared.py` and build its CSV with `pipeline/build_all_boards.py --fy YEAR`.
2. Run `prepare_years.py DATA_DIR WORK_DIR`. It skips requests that already have a label, reuses labels for resubmitted requests, and writes one record per new request text.
3. Label each chunk with `rubric.md`, reading and writing no more than 50 records at a time. Larger reads and writes timed out in these runs.
4. Run `assemble_years.py WORK_DIR`, then rebuild with `REUSE=1 ./update.sh`.

`prepare_chunks.py` and `assemble_labels.py` are the single-year scripts that produced the FY2027 labels. They are kept as a record of that run.
