# Contacts for follow-up letters

The dashboard's Draft letter button addresses follow-up letters with these files.

| File | What it holds | Source |
| --- | --- | --- |
| `board_council_districts.csv` | For each community board, the council districts covering at least 1% of its land area, with that share | DCP's community district and city council district boundaries (Bytes of the Big Apple), overlaid by `build_contacts.py` |
| `council_members.csv` | Each council district's member, salutation, email and page | council.nyc.gov/districts, parsed by `build_contacts.py` |
| `borough_presidents.csv` | Each Borough President and the office's public email, contact form and phone | The Borough Presidents' official websites |
| `agency_contacts.csv` | For each agency, its head and the public channels a community board can use, including borough offices. It also covers the state agencies, authorities and mayoral offices that responses most often point boards to, such as NYS DOT's New York City region and the Battery Park City Authority | Agencies' official websites and the contacts agencies name in their budget responses |

Run `python3 build_contacts.py` after a council election or redistricting. It rewrites the first two files.

The other two files are curated by hand, because no official source lists these contacts in one place. Every row gives the page it came from (`source_url`) and a short excerpt from that page (`evidence`). An email address appears only if an official page or the agency's own budget response publishes it. The `role` column marks the agency head (`head`), a citywide liaison office (`liaison`), borough offices (`borough`), press offices (`press`) and single facilities (`facility`). An office with an email or a contact form is pre-selected in this order. An office listed for specific boards comes first for those boards, then the office for the board's borough, a liaison office and the head. A press office is pre-selected only when it is a body's one published channel. The letter panel lists every other office for the viewer to add.

Of the 787 requests whose responses point to another agency or public body, 769 go to a body with a contact on file. The rest name bodies that come up once or twice, or that publish no contact.

A letter to a Council Member goes by default to the member whose district holds the request's site, when `locate_requests.py` found it. Otherwise it goes to the members whose districts cover at least 10% of the board's land area. The letter panel lists the others, so a request in a small part of the board can reach the right member. A letter about funding goes to the Borough President's budget office when that office publishes an email or form. Other letters go to the Borough President.

A board can add its own contact for an agency in the letter panel. It is saved only in the viewer's browser.
