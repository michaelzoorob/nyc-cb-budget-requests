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
counted over all letters:

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

## Describing a new fiscal year

1. Build the year's CSV with `pipeline/build_all_boards.py --fy YEAR`.
2. Run `prepare.py DATA_DIR WORK_DIR`. It skips text that already has a description.
3. Describe each chunk with `rubric.md`, reading and writing no more than 50 records at a time.
4. Run `assemble.py WORK_DIR`, then rebuild the pages.
