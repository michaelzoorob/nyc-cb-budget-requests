# Plain-language letters

The dashboard's Draft letter button writes a follow-up letter from a community board. Letters used to quote the board's request and the agency's response word for word, stock phrases and capital letters included. This folder produces `pipeline/letter_descriptions.csv`, which lets a letter describe both in plain words instead.

## What gets described

| Kind | What | Used as |
| --- | --- | --- |
| `request` | Each distinct FY2026 or later request, from its title and explanation | "…asked your agency to {description} (capital request, priority 1, tracking code …)." |
| `response` | Each distinct agency response, from every year | "Your agency {description}." |
| `omb` | OMB Executive Budget text that a letter would otherwise quote | "In the Executive Budget, OMB {description}." |

Each row is keyed by `text_key()` in `pipeline/shared.py`, a hash of the text described with whitespace and case normalized. A request's text is its title and explanation joined by ` || `, so identical requests share a description across boards and years.

Requests from before FY2026 have DCP's category as their title, so they are not in the CSV. `generate_cb2_html.py` rewords the board's own first sentence when it starts with what the board asked for ("Provide funding to…" becomes "provide funding to…"). Otherwise, and for any text without a description, the letter quotes the board's own words, from the start through the first sentence that states the ask, and at least two sentences. A request from FY2020 to FY2025 also gets the site the City's Register records when the letter's words leave it out ("The City's Register gives its site as Montgomery Street between Nostrand Avenue and Rogers Avenue."). `hand.json` also holds corrections from an October 2026 audit of live letters, such as a response description that gave a reason the agency never gave.

## Method

`rubric.md` is the exact prompt the writers received. It fixes each description's grammar so it reads correctly after "your agency", "the agency" or "OMB", keeps every fact that matters, adds nothing, and leaves out web addresses, stock "contact the agency" lines and ALL CAPS.

The 70 most common responses, which answer 63% of all requests, were written by hand (`hand.json`). A pilot of 90 records checked the rubric before the full run. Claude Sonnet agents then described the rest in 39 chunks, reading and writing 50 records at a time.

`assemble.py` writes nothing if a record is missing, duplicated or unknown, or if a description has the wrong form. It lists style slips such as colons or web addresses, and `--strict` makes them errors too.

## Reasons checked

A response description that gives a reason ("can't accommodate it because ...") can turn the
agency's context, a caveat or a statement of support into its reason. In October 2026,
Sonnet compared all 1,535 response descriptions with a "because" against their responses
and rewrote 281 of them. A blind Opus check of 50 rewrites found 35 better, 14 no
different and 1 worse, which was put back.

## Live audit of the letters

In October 2026, 200 requests were drawn at random from the live site, weighted to FY2027
and FY2026. None was in the first live audit. The audit took every letter the panel drafts
for each one. That is the letters to the recipients selected by default, a letter to the
other kind of recipient (an elected official or the agency), and the joint letter, 668
letters in all. It also took the one-letter-per-official digests of eight boards. Sonnet read
each letter against the request and the City's responses and named the source of each issue.
A script then drafted all 102,373 letters on the eight pages, to count each issue everywhere
before and after the changes.

The judges found 376 issues, 1 of them high. 211 came from the templates, mostly in joint
letters and letters to elected officials, which the first audit did not read. The changes,
counted over all letters, follow.

- A joint letter asked officials "to help us getting a response" (19,281 letters).
- A letter to elected officials asked for help "getting a response" right after it reported
  the agency's response (38,413). It now asks for help following up, unless no response was
  published.
- The status ask assumed a project with work to finish (12,459). It now asks for the next
  steps and timeline.
- The clarify ask now leads with a meeting with the right staff and offers to send what the
  agency needs, which its response often names already (3,253).
- A response that named only a phone number or an email was called "the staff your response
  named" (242). The letter now gives the number or address.
- A program for others, such as grants for nonprofits or services for residents, was treated
  as a process the board could submit through (112). The letter now asks for details to
  share.
- The redirect ask no longer says "in the next budget" (1,760).
- What OMB says about funding or status now goes in every letter, in up to two clauses. It
  was left out of about 4,000 letters whose follow-up was about something else.
- A subject keeps up to 90 characters of the title and drops asides before any cut. A
  catch-all title such as "Other capital budget request for DEP" gives way to the start of
  the plain description.
- An agency with no email or form on file gets a letter to its community liaison. 237
  requests with an agency step had no letter. 13 remain, all with the agency "Other".
- A digest names the agency each request asked, says when some requests came from other
  agencies, and gives a fact about the whole district once.
- A Parks inspection fact stays out of a letter whose description names other parks only. A
  board had copied one park's explanation under another park's title.

The rubric described a stock "contact the agency directly" line as "gave no reason". A
letter to that agency then said it gave no reason and left out what it asked the board to do.
These responses, for 1,751 requests, now read "asked us to contact it directly for more
information". 41 descriptions were corrected by hand in `hand.json`, among them one with the
wrong stretch of Foch Boulevard and ten that ran "because although" together.

A request from FY2020 to FY2025 without a model description uses its first sentence as the
letter's words. Text in capitals, two sentences run together or a sentence cut inside a
parenthesis read badly that way, as in "pROVIDE HISTORIC LIGHTING". Such text, in 189 of
6,243 requests, is now quoted instead. A quote drops the City's stray "Explanation:" and "Request:" labels and puts back
lost quotation marks and spaces.

A blind Opus comparison of 55 changed letters, five for each kind of change, preferred the new
letter 49 times, saw no difference 4 times and preferred the old letter twice. Both were the
clarify ask, which then asked the agency to confirm what it needs. It was reworded to propose a
meeting again. The same check found the contact number for some requests in OMB's response, so
the letter now says which response gave it.

24 issues came from the City's own data, such as a response that does not answer the request
or a date in the board's text that has passed. The letters relay them as written. Letters to
NYC Health + Hospitals and the Brooklyn Public Library go to their press offices, and letters
to the MTA to its feedback form, since those are the channels they publish. The judges
questioned 13 follow-up labels, which stay as they are.

## A second live audit of the letters

A board drafts letters for the current year's requests, so the second audit leaned on FY2027.
It drew 300 new requests from the live site, 200 of them from FY2027, and the digests of
eight more boards. The judges and the rubric were the same as in the first audit, so the two
can be compared. In FY2027 the judges found 0.78 issues per request, down from 1.36, and 0.35
of medium or high severity, down from 0.68. 42% of requests had no issue, up from 32%. Fixed
wording in the templates had caused most issues in the first audit and caused few in the
second. Most that remain come from the follow-up labels, the City's own data and the
descriptions.

Each change below gives the number of FY2027 letters it touched.

- A letter to the office a response named asked that office to put the board in touch with
  itself (30 letters). It now asks to meet.
- A letter to the agency a response pointed to said only "the agency said". It now names the
  agency that responded (170).
- A joint letter's study ask mixed "the agency" with "you" (180).
- The ask for a request that needs no follow-up assumed some work remained. A program now gets
  an ask about further steps (242), and a capital project keeps the ask about remaining work.
- OMB's condition "if approved" was dropped (23). OMB's stock paragraph on sidewalks, curbs and
  ramps now keeps only the parts a request is about (100), and a request about none of them
  leaves it out.
- A response that gave a cost was asked for the cost (22). The letter now asks whether the
  funding is planned.
- A link meant for residents or businesses was treated as a way for the board to submit the
  request (7). A program for businesses is now shared with businesses.
- An expense request's letter to the Borough President went to a capital programs office
  (98). It now goes to a budget office or to the Borough President.
- A subject built from a description could end on a dangling word, as in "Hire more workers to
  inspect". It now ends at the first comma only where the words read whole. A title's unclosed
  quotation mark is dropped (9).

59 descriptions were corrected by hand, nearly all for FY2027. Two were wrong in substance. One
put a garage on a waterfront site when the board asked for one off the waterfront. The other
gave a Department of Transportation reply, filed under Parks, to Parks itself. Others restored
a dropped place or a dropped part of the request, split a run-on, said which agency spoke, or
named the speaker of a second sentence. A fix keyed by a response or OMB text applies to every
request with that text, so it has to fit all of them. One that read an OMB sentence about "this
practice" as being about cameras was wrong for other requests and was taken back.

A blind Opus comparison of 66 changed FY2027 letters preferred the new letter 47 times. The
17 losses came from four changes, which were reworked: OMB's stock sidewalk paragraph, the
subject cut, the ask for a request that needs no follow-up, and the OMB description above. A
second blind check of 24 letters with the reworked changes preferred the new letter 20 times,
saw no difference twice and preferred the old letter twice.

## FY2027 descriptions checked

Boards draft letters for the current year's requests, so in October 2026 every FY2027
description was checked against its source. Sonnet compared each of the 3,499 request
descriptions and 2,153 response descriptions with the board's text or the agency's response,
following `verify_rubric.md`. It corrected a description only for a wrong or reversed fact,
a dropped site or main part of the request, something added, a wrong stance or status, a
statement given to the wrong party, unreadable grammar or a meeting date that has passed.
338 request descriptions and 103 response descriptions were corrected, about one in ten and
one in twenty. Among them were a request to send officers to a precinct that read as sending
them from it, and a curb request whose description had dropped the curbs.

Two blind Opus checks of 99 corrections preferred the new text 95 times and saw no
difference once. Of the three it preferred the old text for, one was left out. The other two
dropped a meeting date that had passed, as the rubric intends. Opus also read 120 of the
descriptions left as they were and found an error in one. The corrections change the letters
of 533 FY2027 requests. The 300 FY2027 requests the live audits had read were left out, since
their errors were corrected by hand. A response description serves every request with the
same response, so a few corrections also reach other years.

## A third live audit of the letters

After the FY2027 descriptions and follow-up labels were checked, a third audit drew 200 more
FY2027 requests and the digests of five more boards, with the same judges and rubric. The
judges found 0.61 issues per request, down from 0.78, and 0.23 of medium severity, down from
0.35. None was high. Half the requests had no issue, up from 42%. Issues with descriptions fell
from 41 to 23 and issues with labels from 14 to 8. A fifth of the medium issues come from the
City's own responses, such as a reply about a different site or one that calls unfinished work
complete. A letter can only report these. The five digests had 31 issues, 11 of medium
severity. Five of those come from the City's responses, four from descriptions and two from
labels.

Each change below gives the number of FY2027 requests it touched.

- A subject too long to fit was cut between words and could end mid-phrase ("…between
  Brighton Beach…"). It now ends where a phrase ends, before a reason, a purpose, a range of
  streets or a list of examples (90). 159 subjects are still cut, down from 247.
- A request made only last year and this year read "every year since FY2026" (499). It now
  reads "We also made this request in FY2026."
- OMB's advice to give the agency more detail was left out, so a letter offering details gave
  no reason for it (7).
- A response that named the State or federal government as the body that must act was asked
  which level of government must act (10). It is now asked how the board can help.
- A letter to OMB asked for "the funding your agency would need" (37). It now asks whether the
  budget can fund the request.
- A capital project the agency called completed was asked where it stands (72). It is now
  asked what work was completed and whether any part remains. A program called completed is
  usually one that runs on, and Opus preferred its old ask, so it keeps it.
- A digest to an office that received requests from other agencies now names the agency that
  sent them when there is only one.

14 follow-up labels changed (15 requests). Ten responses funded part of a request and said the
rest needs money, yet the letter only asked to discuss it. They now ask elected officials for
funding, and `label_followup/rubric.md` says so. A Cultural Affairs response that needs a
specific organization and project, where OMB recommends elected officials, now goes to both.
The others are a Sanitation response saying it does not build public restrooms, an HRA
request outside its budget and a Parks reply about developers' tree planting.

12 descriptions were corrected by hand. Among them are the three Broadway plazas, cameras on
Junius Street between Livonia and New Lots Avenues, basketball courts that only the agency's
response placed at Lafayette Playground, two plans dated to FY2026, which has ended, and a
response that called a request a duplicate of its own tracking code.

Blind Opus checks preferred the new version in 78 of 84 pairs of changes and saw no difference
in 1. Of the other 5, three led to the old ask for programs and one fix was taken back. The
fifth was preferred once Opus could see the request's tracking code. Five judges' notes
questioned the salutation "Commissioner" for the Commissioner of Youth and Community
Development. The contact directory confirms her title.

## Ten letters read closely

In October 2026, 10 more FY2027 requests were read letter by letter, and the problems found
were checked across all FY2027 letters. Each change gives the number of FY2027 requests it
touched.

- A response written in early 2026 said "this fiscal year", "the FY 27 Adopted Budget" or
  "spring 2026", and the letter repeated it as still to come. 28 descriptions now put these
  plans in the past, naming fiscal year 2026 (32). Two more were corrected by hand.
- A subject fell back to a catch-all title ("Other expense budget request for HPD") when the
  description said "its". "Its" now becomes "the" (35).
- A category title's example could mislead, as in "Enhance park safety through design
  interventions, e.g. better lighting" for cameras. The example is dropped when the request
  never mentions it (10).
- A response that says elected officials pay for the work (Argus cameras) was asked for "the
  funding your agency would need". It is now asked for the cost, so the board can take it to
  them (33).
- A letter sent to the email address a response named asked that person to put the board in
  touch with the staff the response named (3). It now asks to meet.

A second reading of 10 more letters led to two changes.

- A school's enrollment was local data in letters where it bears on nothing, such as a status
  check on a ramp. It now starts unchecked unless the letter asks for money, where it shows how
  many students the request would serve, or the request is about room for students
  (`shared.SCHOOL_CAPACITY`, class size, seating). A board member can still check it (22).
- `pipeline/locate_requests.py` now finds a park in the board's own district that the board
  gives another kind of name, as "Sixteen Sycamores Park" for Sixteen Sycamores Playground.
  A request that names two or more parks is left as it was, since a letter about one would
  leave out the rest. 46 more requests across the years are placed, 6 of them in FY2027, and
  four FY2027 letters now go only to the Council Member whose district holds the park.

## Describing a new fiscal year

1. Build the year's CSV with `pipeline/build_all_boards.py --fy YEAR`.
2. Run `prepare.py DATA_DIR WORK_DIR`. It skips text that already has a description.
3. Describe each chunk with `rubric.md`, reading and writing no more than 50 records at a time.
4. Run `assemble.py WORK_DIR`.
5. Check the year's descriptions against their sources with `verify_rubric.md`, and put the
   corrections in `WORK_DIR/out/fix_request_*.json` and `fix_response_*.json`, which
   replace the first descriptions. Run `assemble.py WORK_DIR` again, then rebuild the pages.
