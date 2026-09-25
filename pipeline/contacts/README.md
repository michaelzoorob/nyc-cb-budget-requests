# Contacts for follow-up letters

The dashboard's Draft letter button addresses follow-up letters with these files.

| File | What it holds | Source |
| --- | --- | --- |
| `board_council_districts.csv` | For each community board, the council districts covering at least 1% of its land area, with that share | DCP's community district and city council district boundaries (Bytes of the Big Apple), overlaid by `build_contacts.py` |
| `council_members.csv` | Each council district's member, salutation, email and page | council.nyc.gov/districts, parsed by `build_contacts.py` |
| `borough_presidents.csv` | Each Borough President and the office's public email, contact form and phone | The Borough Presidents' official websites |
| `agency_contacts.csv` | For each agency, its head and the public channels a community board can use, including borough offices | Agencies' official websites and the contacts agencies name in their budget responses |

Run `python3 build_contacts.py` after a council election or redistricting. It rewrites the first two files.

The other two files are curated by hand, because no official source lists these contacts in one place. Every row gives the page it came from (`source_url`) and a short excerpt from that page (`evidence`). An email address appears only if an official page or the agency's own budget response publishes it. The `role` column marks the agency head (`head`), a citywide liaison office (`liaison`) and borough offices (`borough`). A letter goes by default to the borough office for the board's borough, then to a liaison office, then to the head.

A letter to the Council Members goes by default to those whose districts cover at least 10% of the board's land area. The letter panel lists the others, so a request in a small part of the board can reach the right member.
