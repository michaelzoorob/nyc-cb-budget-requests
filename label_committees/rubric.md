# Assigning NYC community board budget requests to Queens CB2's committees

Each record is one budget request that a New York City community board sent to the city. Assign it to the committee of **Queens Community Board 2 (CB2)** that would own it — the committee whose subject matter the request is primarily about, and which would draft, champion and follow up on it.

CB2 has exactly seven committees. Use these names verbatim:

- Land Use
- Transportation
- Parks and Environment
- Health and Human Services
- Arts and Culture
- Engagement and Inclusion
- City Services

## How to decide

Pick **one primary committee** for every request. Add a **secondary** committee only when the request genuinely sits in two committees' subject areas in roughly equal measure. That should be rare: CB2's own board gave a second committee to 1 request out of 65. When in doubt, leave secondary empty.

The responsible agency is strong evidence, and CB2 mostly follows it (defaults below). But decide on **what the request is about**, not only who it is addressed to. The agency default is where you start, not where you must end.

## What each committee covers

**Land Use** — Housing: affordable housing creation and preservation, senior and supportive housing, tenant protection and legal services, homeownership programs, basement/ADU conversions, HPD inspections, NYCHA buildings and developments. Zoning, rezonings, neighborhood and corridor plans, planning and feasibility studies (DCP). Building construction and code enforcement (DOB). Economic development and small business support: SBS, EDC, BIDs, industrial business zones, commercial corridors, storefront grants. Landmarks and historic preservation (LPC). Plans for specific development sites, including public amenities promised as part of a development deal.

**Transportation** — Streets as travel infrastructure and mobility: traffic safety and calming, pedestrian safety, daylighting, speed cameras and traffic enforcement studies, bike lanes, bus service and bus lanes, subway service, station accessibility (ADA elevators), parking and curb management, EV charging, street redesign studies, **street reconstruction** (see below), ferries, and clearing snow from bike lanes and transit routes. Agencies: DOT, MTA / NYC Transit.

**Parks and Environment** — Parks, playgrounds, greenways, park facilities and their maintenance and lighting, recreation centers in parks, athletic fields, dog runs, comfort stations in parks, street trees and forestry, open space, waterfront access, and environmental initiatives centered on green space. Agency: DPR.

**Health and Human Services** — Health care, hospitals and clinics, mental health, substance use treatment, seniors and senior centers (DFTA), youth services and after-school programs (DYCD), childcare, children's and family services (ACS), homelessness prevention and shelters (DHS), food assistance and pantries (HRA), and social services generally. **Schools and education (DOE, SCA) also go here** — CB2 treats youth and education together.

**Arts and Culture** — Arts funding, cultural institutions and facilities, performance spaces and amphitheatres, public art, cultural programming, film and media (DCLA, MOME). Memorials and monuments get Arts and Culture as a **secondary** when they sit on park land.

**Engagement and Inclusion** — Two things only:
1. **The community board's own operations and its engagement with the public**: the board's office, storefront or street presence, staffing, budget and supplies; meeting technology (Zoom, hybrid meetings, audio-visual equipment); the board's website, newsletter and social media; outreach, event promotion, community events, tabling and giveaways; civic participation programs.
2. **Language access and inclusion**: ESOL and English classes, translation and interpretation, language access programs, and programs whose main purpose is including immigrants or other underrepresented groups in civic life or city services.

**Not** Engagement and Inclusion:
- A request that merely *mentions* immigrants, seniors, a language, or a community group while being about something else. Affordable housing for immigrant families is Land Use; a senior center that serves a diverse population is Health and Human Services.
- A request that talks about *resolving* a problem or passing a *resolution*. These words have nothing to do with ESOL.
- Accessibility of infrastructure (ADA elevators, curb cuts, accessible playgrounds) stays with the infrastructure's own committee.
- Immigrant legal and social services are Health and Human Services primary, with Engagement and Inclusion as secondary.

**City Services** — Core city services and the catch-all. Police: precinct staffing, enforcement, patrols, even police programs with a social-service flavor (NYPD). Fire and EMS (FDNY). Sanitation, trash and litter baskets (DSNY). Water mains, sewers, catch basins, flooding, stormwater and green infrastructure such as rain gardens (DEP). **Resurfacing, repaving, milling, and pothole or trench repair** (upkeep of the road surface). Street lighting. Libraries (NYPL, BPL, QPL). 311, noise and quality-of-life enforcement, emergency management, and city agency operations (DCAS, DoITT, OMB) — **except** requests about the community board's own office, staff, technology or outreach, which are Engagement and Inclusion.

**Street reconstruction versus road upkeep.** A request to reconstruct or rebuild a street, or a capital project that rebuilds a street segment's roadway together with its curbs, sidewalks, sewers or water mains, is **Transportation**. A request whose main ask is resurfacing, repaving, milling, or pothole or trench repair is City Services, even when it is filed under DCP's "Reconstruct streets" category. Sewers, water mains and catch basins alone, sidewalks or curbs alone, and street lights stay with their usual committees. Bridges, viaducts, retaining walls and seawalls are not street reconstruction.

## Agency defaults (where to start)

| Agency | Default committee |
| --- | --- |
| DOT, MTA / NYC Transit | Transportation |
| DPR | Parks and Environment |
| DCP, HPD, DOB, SBS, NYCHA, EDC, LPC | Land Use |
| DCLA, MOME | Arts and Culture |
| DOHMH, H+H, HRA, DFTA, DYCD, ACS, DHS, DOE, SCA | Health and Human Services |
| NYPD, FDNY, DSNY, DEP, libraries, DCAS, DoITT, OMB, anything else | City Services |

## Output

For each record return `id`, `primary` (one of the seven names, verbatim), and `secondary` (one of the seven names, or `null`). When either `primary` or `secondary` is Engagement and Inclusion, also return `ei_reason`: 5 to 12 words naming what makes it an engagement or inclusion request. Otherwise omit `ei_reason`.
