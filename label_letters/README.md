# Plain-language letters

The dashboard's Draft letter button writes a follow-up letter from a community board. Letters used to quote the board's request and the agency's response word for word, stock phrases and capital letters included. This folder produces `pipeline/letter_descriptions.csv`, which lets a letter describe both in plain words instead.

## What gets described

| Kind | What | Used as |
| --- | --- | --- |
| `request` | Each distinct FY2026 or later request, from its title and explanation | "…asked your agency to {description} (capital request, priority 1, tracking code …)." |
| `response` | Each distinct agency response, from every year | "Your agency {description}." |
| `omb` | OMB Executive Budget text that a letter would otherwise quote | "In the Executive Budget, OMB {description}." |

Each row is keyed by `text_key()` in `pipeline/shared.py`, a hash of the text described with whitespace and case normalized. A request's text is its title and explanation joined by ` || `, so identical requests share a description across boards and years.

Requests from before FY2026 have DCP's category as their title, so they are not in the CSV. `generate_cb2_html.py` rewords the board's own first sentence when it starts with what the board asked for ("Provide funding to…" becomes "provide funding to…"). Otherwise, and for any text without a description, the letter falls back to a short quote.

## Method

`rubric.md` is the exact prompt the writers received. It fixes each description's grammar so it reads correctly after "your agency", "the agency" or "OMB", keeps every fact that matters, adds nothing, and leaves out web addresses, stock "contact the agency" lines and ALL CAPS.

The 70 most common responses, which answer 63% of all requests, were written by hand (`hand.json`). A pilot of 90 records checked the rubric before the full run. Claude Sonnet agents then described the rest in 39 chunks, reading and writing 50 records at a time.

`assemble.py` writes nothing if a record is missing, duplicated or unknown, or if a description has the wrong form. It lists style slips such as colons or web addresses, and `--strict` makes them errors too.

## Describing a new fiscal year

1. Build the year's CSV with `pipeline/build_all_boards.py --fy YEAR`.
2. Run `prepare.py DATA_DIR WORK_DIR`. It skips text that already has a description.
3. Describe each chunk with `rubric.md`, reading and writing no more than 50 records at a time.
4. Run `assemble.py WORK_DIR`, then rebuild the pages.
