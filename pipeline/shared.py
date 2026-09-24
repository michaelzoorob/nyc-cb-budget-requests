"""Logic shared by every fiscal year's builder: request ids, agency stance,
committee assignment, agency names, and which Register publications make up
each year.

build_statement_sheet.py (PDF years) and build_register_year.py (Register-only
years) both import from here, so a request gets the same id, stance rule and
committee lookup whichever source it came from.
"""
import hashlib
import os
import re

import pandas as pd

# Fiscal years on the dashboard. PDF_YEARS have per-request agency responses in
# their Statement PDFs, fuller than the Register's for FY2027. The other years
# take every column from the Register: their PDFs either have no responses
# (FY2017-FY2023) or repeat the Register's text (FY2024-FY2025).
YEARS = ["2027", "2026", "2025", "2024", "2023", "2022", "2021", "2020"]
LATEST = YEARS[0]
PDF_YEARS = {"2027", "2026"}

# Register publications for each fiscal year, read off the Register itself
# (NYC Open Data vn4m-mk4t). Each year has a January agency round (responded_by
# holds an agency code) and an April/May OMB Executive round. FY2027's agency
# round is stamped 20270217 in the Register, apparently for 20260217.
PUBLICATIONS = {  # fiscal year: (agency round, OMB Executive round)
    "2027": ("20270217", "20260512"),
    "2026": ("20250116", "20250501"),
    "2025": ("20240116", "20240424"),
    "2024": ("20230112", "20230428"),
    "2023": ("20220216", "20220426"),
    "2022": ("20210114", "20210426"),
    "2021": ("20200116", "20200416"),
    "2020": ("20190207", "20190425"),
}

BORO_ABBR = {"1": "M", "2": "BX", "3": "BK", "4": "Q", "5": "SI"}
# The open Register codes boroughs ALPHABETICALLY (1=Bronx, 2=Brooklyn, 3=Manhattan,
# 4=Queens, 5=Staten Island) -- NOT the standard 1=Manhattan. Map our standard code
# (used for the PDF/board label) to the Register's code for the join.
REG_BORO = {"1": "3", "2": "1", "3": "2", "4": "4", "5": "5"}
REG_BORO_ABBR = {"1": "BX", "2": "BK", "3": "M", "4": "Q", "5": "SI"}

AGENCY = {
    "DCP": "Department of City Planning", "DOT": "Department of Transportation",
    "DCAS": "Department of Citywide Administrative Services",
    "DEP": "Department of Environmental Protection",
    "DPR": "Department of Parks & Recreation", "NYPD": "Police Department",
    "FDNY": "Fire Department", "DSNY": "Department of Sanitation",
    "DOE": "Department of Education", "DOHMH": "Dept. of Health & Mental Hygiene",
    "HPD": "Housing Preservation & Development", "DOB": "Department of Buildings",
    "DOITT": "Office of Technology & Innovation (DoITT)",
    "DFTA": "Department for the Aging", "DYCD": "Youth & Community Development",
    "HRA": "Human Resources Administration", "HHC": "NYC Health + Hospitals",
    "DCLA": "Department of Cultural Affairs", "SBS": "Small Business Services",
    "QL": "Queens Public Library", "NYCTA": "MTA / NYC Transit",
    "SCA": "School Construction Authority", "EDC": "Economic Development Corporation",
    "NYCHA": "NYC Housing Authority", "NYPL": "New York Public Library",
    "BPL": "Brooklyn Public Library", "DHS": "Department of Homeless Services",
    "OMB": "Office of Management & Budget", "ACS": "Administration for Children's Services",
    "LPC": "Landmarks Preservation Commission", "MOCJ": "Mayor's Office of Criminal Justice",
    "NYCEM": "NYC Emergency Management", "DCWP": "Dept. of Consumer & Worker Protection",
    "MOME": "Mayor's Office of Media & Entertainment",
    "CECM": "Citywide Event Coordination & Management",
    "CUNY": "City University of New York",
    "TLC": "Taxi and Limousine Commission",
}
AGENCY_ABBR = {v: k for k, v in AGENCY.items()}

# The Register spells some agencies differently from the dashboard (and older
# years use old agency names). Map them onto the dashboard's names so the
# Agency filter treats each agency as one across years. Renamed agencies map to
# their successor: DoITT -> OTI, Consumer Affairs -> DCWP, OEM -> NYCEM.
REGISTER_AGENCY_NAMES = {
    "Department of Parks and Recreation": "Department of Parks & Recreation",
    "Department of Housing Preservation & Development": "Housing Preservation & Development",
    "Department of Housing Preservation and Development": "Housing Preservation & Development",
    "Department of Health and Mental Hygiene": "Dept. of Health & Mental Hygiene",
    "Transit Authority": "MTA / NYC Transit",
    "Department of Youth & Community Development": "Youth & Community Development",
    "Housing Authority": "NYC Housing Authority",
    "Department of Small Business Services": "Small Business Services",
    "Mayor's Office of Management and Budget": "Office of Management & Budget",
    "Health and Hospitals Corporation": "NYC Health + Hospitals",
    "Queens Borough Public Library": "Queens Public Library",
    "Dept of Information Technology & Telecommunication": "Office of Technology & Innovation (DoITT)",
    "Department of Consumer and Worker Protection": "Dept. of Consumer & Worker Protection",
    "Department of Consumer Affairs": "Dept. of Consumer & Worker Protection",
    "Office of Emergency Management": "NYC Emergency Management",
    "Citywide Event Coordination and Management": "Citywide Event Coordination & Management",
    "Mayor's Office of Media and Entertainment": "Mayor's Office of Media & Entertainment",
    "Taxi and Limousine Commission": "Taxi and Limousine Commission",
}


def stance(resp):
    """Classify from the leading disposition sentence only -- incidental phrases
    later in the prose ("NYC supports 100,000 youth jobs...") must not count."""
    t = " ".join(("" if resp is None else str(resp)).split()).strip()
    if not t or t.lower() == "nan":
        return "Neutral/Unclear"
    first = re.split(r"(?<=[.!?])\s", t)[0].lower()
    if "does not support" in first:
        return "Oppose"
    if "supports" in first or "recommends funding" in first:
        return "Support"
    return "Neutral/Unclear"


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower()).strip()


# Citywide agency -> CB2-style committee defaults, following CB2's own form
# assignments (DOT->Transportation, HPD/DCP/DOB/SBS->Land Use, DEP/NYPD/QL->City
# Services, DCAS/DOITT->Engagement and Inclusion...) and extended to agencies CB2
# never used. Anything unlisted falls to "City Services".
AGENCY_COMMITTEE = {
    "DOT": "Transportation", "NYCTA": "Transportation",
    "DPR": "Parks and Environment",
    "DCP": "Land Use", "HPD": "Land Use", "DOB": "Land Use", "SBS": "Land Use",
    "NYCHA": "Land Use", "EDC": "Land Use", "LPC": "Land Use",
    "DCLA": "Arts and Culture", "MOME": "Arts and Culture",
    # (DCAS/DOITT intentionally NOT mapped to CB2's "Engagement and Inclusion" --
    # that reflects CB2's language-access asks; citywide their requests are
    # facilities/IT, i.e. City Services.)
    "DOHMH": "Health and Human Services", "HHC": "Health and Human Services",
    "HRA": "Health and Human Services", "DFTA": "Health and Human Services",
    "DYCD": "Health and Human Services", "ACS": "Health and Human Services",
    "DHS": "Health and Human Services",
}


# Whole words only. A bare substring test for "esol" matched r-ESOL-ution and
# r-ESOL-ve, which put 35 unrelated requests into Engagement and Inclusion.
# "language accessibility" is spelled out because it means language access.
EI_KEYWORDS = re.compile(r"\b(esol|language access(?:ibility)?|immigrants?)\b")


def infer_committees(title, expl, ab):
    """Fallback CB2-taxonomy guess, used only for requests with no entry in
    committee_labels.csv (e.g. a new fiscal year before it has been labeled).
    Agency decides the primary committee; the language-access/immigrant keyword
    only APPENDS Engagement and Inclusion (never replaces the topic). No
    memorial/monument rule here -- citywide it false-positives on park names
    ("Flushing Memorial Field") and landmark mentions."""
    t = (str(title) + " " + str(expl)).lower()
    out = [AGENCY_COMMITTEE.get(ab, "City Services")]
    if EI_KEYWORDS.search(t) and "Engagement and Inclusion" not in out:
        out.append("Engagement and Inclusion")
    return out


# Model-assigned committees, produced by label_committees/ (see its README) and
# keyed by request_id(). CB2's FY2027 committee form, when supplied, overrides it.
LABELS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "committee_labels.csv")


def request_id(board, title, expl):
    """Stable id for one request: survives re-parsing, changes if the text changes.
    Identical requests in different years share an id, and so share a label."""
    return hashlib.sha1(f"{board}|{norm(title)}|{norm(expl)}".encode()).hexdigest()[:12]


def load_labels():
    if not os.path.exists(LABELS_CSV):
        return {}
    lab = pd.read_csv(LABELS_CSV, dtype=str).fillna("")
    return {i: [c for c in (p, s) if c] for i, p, s in zip(lab["id"], lab["primary"], lab["secondary"])}


# Hand overrides (MZ's judgment where the standardized leading disposition is
# misleading). Keyed by (fiscal year, board, normalized title).
STANCE_OVERRIDE = {
    # "Agency supports but cannot accommodate" -- but the prose says Parks only
    # supports IF a formalized dog-run group exists, and none does, so Parks
    # currently does not support the funding ask.
    ("2027", "QCB1", "whitey ford field dogpark request"): "Oppose",
}

COLS = ["Priority", "Type", "Board", "Agency", "Title", "Explanation",
        "Agency Response", "OMB Executive Response", "Agency Stance (MZ added)", "Committees"]
