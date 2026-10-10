# Check the plain-language descriptions in the follow-up letters

A public dashboard drafts follow-up letters that NYC community boards send to City agencies
and elected officials about their FY2027 budget requests. Each letter describes the board's
request and the agency's response in plain words that a model wrote earlier. Your job is to
find the descriptions that misstate their source, and to correct those. Most descriptions are
fine. Judge from the text in your file only. Do not look anything up.

## How a letter uses the descriptions

> On behalf of Queens Community Board 2, I am writing to follow up on one of our FY2027
> budget requests. We asked your agency to {request}.
>
> Your agency {response}.

The letter may instead name the agency ("asked the Department of Transportation to ...",
"The Department of Transportation said ...") or go to an elected official. A description has
to read correctly in all of these.

## What counts as an error

Mark a description `fix` only for one of these.

1. **Wrong fact.** A place, number, amount, date, program, office or agency that differs from
   the source, or a meaning turned around ("a waterfront site" for "a site off the
   waterfront", "over a hundred permits" for "permits for buildings with over a hundred
   units").
2. **Dropped place.** The source names a specific site (an address, street and cross streets,
   a stretch of a street, a park, school, station or building) and the description leaves it
   out or makes it vaguer, such as a whole avenue for one intersection.
3. **Dropped part.** The source asks for several distinct things and the description leaves
   out one the board plainly treats as a main ask. A second site in a list counts.
4. **Added content.** Something the source does not say: a reason, a commitment, a place, a
   number, or a stronger or weaker claim.
5. **Response only.** A wrong stance (supports or not, can or can't accommodate), a status the
   response does not give ("was done" for "will be completed"), a "because" the response does
   not give, a dropped instruction or caveat that matters (an office or person to contact,
   locations to submit, "within existing resources", a condition), or a statement made by
   another agency or by the board presented as this agency's own.
6. **Unreadable.** Grammar that hides or changes the meaning, a word missing, a clause that
   attaches to the wrong thing, a pronoun with nothing to refer to, or a second sentence that
   reads as the board speaking.
7. **Stale.** A request asks for a meeting or an action on a date that has passed, such as
   "meet with us in November 2025".

Do not mark these: an omitted background detail, reason or statistic that the letter does not
need; wording you would phrase differently; a description that is short but accurate; the
source's own errors or contradictions, which the letter relays as written.

## How to write a correction

Write the whole corrected description, following the rules the descriptions were written to.

- A **request** description is a verb phrase in the base form that completes "asked the
  agency to ...", such as "build catch basins at ...". It does not start with "to". Keep it
  under about 230 characters.
- A **response** description starts with "said" and completes "The agency ...". Keep it under
  about 290 characters. A second sentence, when one is needed, starts with "It also said" or
  with "It" and a verb, never with a bare "It said".
- "it" and "its" mean the agency that responded. "we", "us" and "our" mean the community board.
  Name any other agency or office in full the first time.
- Use plain words and contractions. No quotation marks, colons, semicolons, parentheses,
  dashes between words, web addresses, email addresses or phone numbers. Spell out street
  abbreviations. No final period.
- Change only what the error needs. Keep everything else the description says.

## Output

Write a JSON array to the output file named in your task, one object per item, in input
order:

    {"key": "<the item's key>", "verdict": "ok" | "fix",
     "problem": "<for fix: the error, at most 25 words>",
     "text": "<for fix: the corrected description>"}

For `ok`, leave "problem" and "text" empty.
