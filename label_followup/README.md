# Follow-up actions

The dashboard's Follow-up column gives the next step for a board that still wants a request. Its Draft letter button writes the follow-up letter. This folder produces `pipeline/followup_labels.csv`, and `pipeline/contacts/` holds the letters' recipients.

## Method

Requests that received the same agency response and the same OMB response share one label. The 29,428 requests from FY2020 to FY2027 received 6,678 distinct pairs of responses, because many agencies answered with standard phrases. `prepare.py` writes one record per pair, keyed by `response_key()` in `pipeline/shared.py`. The 81 requests with no published response get Contact agency by rule.

`rubric.md` defines six actions (who to contact) and ten purposes (why, which shapes the letter). It is the exact prompt the labelers received. Claude Sonnet agents labeled the pairs in 33 chunks, reading and writing 50 records at a time. Each label also names what in the responses decides it, and copies any office, person, email or link a response names. `assemble.py` validates the output and writes nothing if a pair is missing, duplicated or labeled with an action and purpose that do not go together.

| Action | Response pairs | Requests |
| --- | --- | --- |
| Contact agency | 2,407 | 12,034 (40.9%) |
| Contact elected officials | 1,622 | 8,804 (29.9%) |
| Track with agency | 1,807 | 6,628 (22.5%) |
| Use 311 or another channel | 325 | 1,028 (3.5%) |
| No follow-up needed | 478 | 799 (2.7%) |
| Contact agency and elected officials | 39 | 135 (0.5%) |

## Pilot

Before the full run, a Sonnet agent and an Opus agent each labeled 120 pairs without seeing the other's labels. The sample held the 60 most common pairs, which answer 44% of all requests, and 60 random pairs. The two chose the same action for 107 of the 120 pairs, which cover 99% of the requests in the sample, and for all 76 the Opus agent rated high confidence.

Both agents flagged the same gaps, and the rubric now settles them. The most specific statement decides, so OMB text that only restates the agency defers to the agency's own reason. An instruction to contact the agency makes the purpose discuss, even when the agency also declines the request. Partial funding goes to the agency to discuss. A request that needs legislation or a decision beyond the agency goes to elected officials, with the purpose advocacy. After release, a user pointed out that a letter went to the Department of Cultural Affairs although its response said the request belongs to Parks. The rubric now gives such responses the purpose redirect and names the agency they point to, and the letter goes to that agency. Every pair labeled Use 311 or another channel, every pair naming a contact and every pair with redirect wording (1,591 pairs) was relabeled under the new rule. Of these, 341 pairs (787 requests) now point to another agency or public body.

## Validation

An Opus agent labeled 150 more pairs without seeing the Sonnet labels. Half were drawn in proportion to the number of requests each pair answers, and half uniformly. Neither half overlaps the pilot.

The first comparison found one systematic error. The Sonnet agents often chose Track with agency for "Agency supports but cannot accommodate" when the response went on to describe related work. The rubric now says that this disposition means the agency will not do the request now, and it adds three related rules. A Sonnet agent relabeled the 296 pairs that matched these patterns under the sharpened rubric, and the action changed for 143 of them.

After that relabel, the two labelers chose the same action for 87% of the request-weighted sample (65 of 75) and 73% of the uniform sample (55 of 75). They agreed on 61 of the 64 pairs the Opus agent rated high confidence. The remaining disagreements are responses that support more than one next step. An example is an agency that supports a request, lacks the funds and says it will look for them, which could go to the agency or to elected officials. The letter panel lets the board choose other recipients in such cases.

## Relabel after the live audit

A live audit of 300 requests in October 2026 found letters whose closing ask did not fit the
responses. Examples are an ask to reconsider sent to an agency that supported the request, and
an ask for a timeline when the agency had declined or finished the work. The rubric now limits
four purposes (reconsider, status, advocacy and clarify). Sonnet relabeled 891 pairs whose
label conflicted with their responses, in two rounds, and `assemble.py --replace` merged
them. A blind Opus labeler checked 120 of the changed labels. In the first round it chose the
new label for 60 of 80 and the old one for 6. In the second it chose the new label for 22 of
40 and the old one for 7, and it kept "status" where OMB says a citywide allocation funds the
work. Its label is used wherever it differed from Sonnet's, and the second round keeps the old
"status" label for 9 more pairs of that kind. Of the 38 closing asks the audit flagged, 32
now read correctly.

`pipeline/refresh_followup.py DATA_DIR` applies `followup_labels.csv` to each year's CSV again
after a relabel, so the pages can be rebuilt without rebuilding the years.

## FY2027 labels checked

Boards draft letters for the current year's requests, so this pass checked the labels of the
2,389 FY2027 response pairs. A pilot gave Sonnet 200 pairs and every misfit rule. It changed
6, and a blind Opus check preferred 4 of them. The pilot was too cautious. Opus judged 11 of
40 labels it had kept unfit.

Rules then flagged 180 pairs whose label might not fit. Examples are study when no study is
pending, redirect when the response says the work is done, and discuss when the agency can
accommodate the request and names no one to contact. Sonnet decided each flagged pair and
changed 49. A blind Opus check preferred the new label for 42 and the old one for 7. Six old
labels stay. The seventh is a School Construction Authority response that did not understand
the request and said funding was not available. Its label now sends the agency a letter
offering details and asks the elected officials for funding. Opus also read 40 labels the pass
had kept and judged 5 unfit. Two of them were corrected by hand, and the other 3 are close
calls.

In all, 46 labels changed. They change the letters of 94 FY2027 requests and 1 FY2026
request. The largest group moved from study to funding (21 pairs, 64 requests). NYC Aging's "Need
additional funding to meet this request" is one. Its letter had asked the agency how its
review was going and now asks elected officials to advocate for funding. `rubric.md` now
allows study only for a study under way or planned, and redirect only for a body that should
take the request up.

A third live audit of the letters then found ten pairs labeled discuss where the agency funded
part of a request and said the rest needs money. They now ask elected officials for funding,
and the rubric's rule on partial funding says so. Four more labels were corrected by hand. A
blind Opus check preferred all 14 new labels.

## Labeling a new fiscal year

1. Build the year's CSV with `pipeline/build_all_boards.py --fy YEAR`.
2. Run `prepare.py DATA_DIR WORK_DIR`. It skips pairs that already have a label.
3. Label each chunk with `rubric.md`, reading and writing no more than 50 records at a time.
4. Run `assemble.py WORK_DIR`, then rebuild with `REUSE=1 ./update.sh`.
