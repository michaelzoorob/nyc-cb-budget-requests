# Is it the same request?

Each record pairs two budget requests from the same community board in consecutive fiscal
years: `then` (the earlier year) and `now` (the later year). Each side has the year, the
agency, Capital or Expense, a title and an explanation. Decide whether `now` asks for
substantively the same thing as `then`, so that a reader would say the board made this
request in both years.

Judge the substance of the ask. Boards rewrite their requests every year, and the wording
can change a great deal while the request stays the same.

## The test

If the City fully granted `then`, would the board consider `now` granted too, and the
reverse? If yes, the two are the same request. Small additions or removals do not change
the answer.

## Still the same request

A request stays the same when only these change.

- The wording, the order of sentences, the length or the amount of detail.
- The reason given. "More officers at the 90th Precinct to cut response times" and "more
  officers at the 90th Precinct for community policing" are the same request.
- The dollar amount, or the phase of one project ("Phase 2 of the reconstruction of
  Smith Playground").
- The title, including a DCP category title such as "Reconstruct or upgrade a park or
  amenity".
- The agency, when the same work is asked of a related agency, such as a school
  addition asked of DOE and then of the School Construction Authority.
- The places a service covers, when the later request names the branches, precincts or
  schools within the board's district that the earlier one meant ("more hours at our
  library branches" and "open the Elm Street and Oak Street branches seven days a week").
- The precision of the place for the same project, such as a park in one year and its
  playground in the next.
- The suggested location of one facility the board keeps asking for, when the text shows
  it is the same facility, such as "a new library to replace the closed Elm Street branch"
  proposed first for one block and then for another.

## A different request

- A different site: another park, school, building, intersection or stretch of street.
  "Traffic calming at Main Street and 1st Avenue" and "traffic calming at Main Street and
  9th Avenue" are different requests.
- A different kind of thing for the same place or group: more officers and a new precinct
  house; more home-delivered meals and higher reimbursement rates for meal providers.
- Different work at the same place, even to solve the same problem: rebuilding the
  streets on some blocks and rebuilding the sewers under them; cleaning an underpass and
  netting it against pigeons. A board often asks for both in the same year.
- Requests that only share a theme: two different school upgrades, two different studies.
- A district-wide or general request and a specific one ("plant street trees across the
  district" and "plant trees on Elm Street"), unless the text makes clear they are the same
  project.

## When unsure

If the records do not let you tell, answer `unsure`. Do not guess. A pair you are not sure
about counts as different.

## Output

A JSON array with one object per record, in the order of the input:

    {"id": "<the record's id>", "verdict": "same" | "different" | "unsure", "why": "<at most 15 words>"}

The `why` names what decided it, for example "same playground reconstruction, new amount" or
"different intersection".
