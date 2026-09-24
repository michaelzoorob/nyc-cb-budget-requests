# Committee labels

The dashboard assigns every budget request to one of Queens CB2's seven committees. CB2's own requests take their committee from CB2's committee form. Requests from the other 58 boards take it from `pipeline/committee_labels.csv`, which this folder produces.

## The old rule

The old rule chose a committee from the responsible agency. It appended Engagement and Inclusion when a request's text contained "esol", "language access" or "immigrant", and it tested these as raw substrings. The string "esol" matched "resolution" and "resolve", which placed 35 unrelated requests in Engagement and Inclusion, including DOT street requests and a Union Square garbage request. The agency default also sent requests about a board's own office, staff, website and meeting technology to City Services, because DCAS, OTI and OMB default there. The old rule therefore missed all nine of CB2's own Engagement and Inclusion requests.

## Method

`rubric.md` defines the seven committees. It follows CB2's FY2027 committee-form assignments and the agency defaults in `pipeline/build_statement_sheet.py`. It is the exact prompt the labelers received.

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

- **Schools go to Health and Human Services.** CB2 filed no school requests in FY2027. CB2 placed after-school programs in Health and Human Services, and the rubric extends that to education. This moved 275 of the 279 DOE and SCA requests out of City Services, the old catch-all.
- **Street reconstruction, resurfacing and street lighting go to City Services.** Traffic safety, bike lanes, bus service and transit stay in Transportation. This follows CB2's placement of its Winfield street reconstruction request in City Services. It moved 203 of the 609 DOT requests out of Transportation.
- **A board's own operations go to Engagement and Inclusion.** CB2's Engagement and Inclusion requests cover its storefront, website, newsletter, meeting technology and events. The rubric extends that to a board's office, staff, budget and training. Of the 59 non-CB2 requests now labeled Engagement and Inclusion, 42 were filed with OMB, DCAS or OTI and concern board operations.

To change a call, edit `rubric.md` and relabel, or edit `committee_labels.csv` directly.

## Labeling a new fiscal year

1. Build the new year's combined CSV with `pipeline/build_all_boards.py`.
2. Run `prepare_chunks.py` on that CSV.
3. Label each chunk with `rubric.md`, writing no more than 50 labels per write. Larger single writes timed out in the FY2027 run.
4. Run `assemble_labels.py`, then rebuild with `pipeline/build_all_boards.py --reuse-parsed`.
