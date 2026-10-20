"""Shared building blocks for workshop data profiles.

A *profile* is the single source of truth for one synthetic population (e.g. `adult`,
`pediatric`). It supplies the seed lists — facilities, diagnoses, procedures, specialties,
age distribution — that the data generator and the ETL-lab raw CSV are BOTH derived from,
so the two never drift. Add a new vertical by adding a new profile module; the generator
and the raw-CSV builder pick it up unchanged.

This module holds the parts every profile shares: name pools, visit types, reference lists,
a US state map, and the deterministic "messiness recipe" that turns a clean facility list
into the intentionally-messy `facilities_raw` CSV for the Lakeflow Designer lab — plus
`conform()`, the answer key that the lab's transforms reproduce.
"""

# --- shared reference data (population-agnostic) --------------------------------------------

FIRST_NAMES = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David",
               "Elizabeth","William","Barbara","Richard","Susan","Joseph","Karen","Thomas","Nancy",
               "Maria","Carlos","Wei","Priya","Ahmed","Sofia","Hyun","Fatima","Diego","Aisha"]
LAST_NAMES = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez",
              "Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore",
              "Nguyen","Patel","Kim","Chen","Okafor","Singh","Ali","Romero","Schultz","Bennett"]

COMPLICATION_TYPES = ["Surgical site infection", "Post-op bleeding", "Hospital-acquired pneumonia",
                      "Venous thromboembolism", "Acute kidney injury", "Adverse drug reaction",
                      "Pressure ulcer", "Sepsis"]
ENCOUNTER_TYPES = ["Inpatient", "Outpatient", "Emergency"]
PAYER_TYPES = ["Commercial", "Medicare", "Medicaid", "Self-Pay"]

# Visit types shared by all profiles. Non-standard types are EXCLUDED from PCP continuity.
# (visit_type_id, visit_type_name, is_standard, weight)
VISIT_TYPES = [
    ("OFFICE",       "Standard office visit",   True,  0.82),
    ("TELEHEALTH",   "Telehealth admin",        False, 0.06),
    ("NURSE",        "Nurse-only visit",        False, 0.06),
    ("IMMUNIZATION", "Immunization-only visit", False, 0.06),
]

# Full US state name -> 2-letter code. Used to standardize the messy `State` column. This is
# standard reference data (not profile-specific), so the ETL lab stays generic across profiles.
US_STATES = {
    "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA","colorado":"CO",
    "connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA","hawaii":"HI","idaho":"ID",
    "illinois":"IL","indiana":"IN","iowa":"IA","kansas":"KS","kentucky":"KY","louisiana":"LA",
    "maine":"ME","maryland":"MD","massachusetts":"MA","michigan":"MI","minnesota":"MN",
    "mississippi":"MS","missouri":"MO","montana":"MT","nebraska":"NE","nevada":"NV",
    "new hampshire":"NH","new jersey":"NJ","new mexico":"NM","new york":"NY","north carolina":"NC",
    "north dakota":"ND","ohio":"OH","oklahoma":"OK","oregon":"OR","pennsylvania":"PA",
    "rhode island":"RI","south carolina":"SC","south dakota":"SD","tennessee":"TN","texas":"TX",
    "utah":"UT","vermont":"VT","virginia":"VA","washington":"WA","west virginia":"WV",
    "wisconsin":"WI","wyoming":"WY",
}


def standardize_state(raw):
    """Messy state value (full name / code / any case / whitespace) -> 2-letter code."""
    s = (raw or "").strip()
    if not s:
        return s
    up = s.upper()
    if len(s) == 2:
        return up
    return US_STATES.get(s.lower(), up)


def facilities_with_ids(facility_seed):
    """Assign FAC001.. ids to a profile's clean facility seed.

    facility_seed: list of (name, type, city, state_code, region).
    returns: list of (facility_id, name, type, city, state_code, region).
    """
    return [(f"FAC{i+1:03d}", name, ftype, city, state, region)
            for i, (name, ftype, city, state, region) in enumerate(facility_seed)]


def build_messy_facility_csv(facility_seed):
    """Turn a profile's clean facility seed into the intentionally-messy raw CSV (a string).

    The messiness is deterministic and generic across profiles:
      - header with spaces / mixed case
      - leading/trailing whitespace on some names
      - State rendered inconsistently (full name, lowercase code, trailing space, correct code)
      - Type in mixed casing (lower / UPPER / proper)
      - Region blanked on up to two facilities that share a city with a populated sibling
        (so the gold step can derive it from the sibling — no external lookup needed)
      - one duplicated facility row (re-cased)
      - a trailing blank line
    After the lab's transforms (see conform()) it collapses to the clean facility dimension.
    """
    rows = facilities_with_ids(facility_seed)
    code_to_name = {v: k.title() for k, v in US_STATES.items()}

    # choose up to 2 facilities to blank region on, each sharing a city with a populated sibling
    by_city = {}
    for r in rows:
        by_city.setdefault(r[3], []).append(r[0])
    blank_ids = []
    for r in rows:
        if len(by_city[r[3]]) >= 2 and by_city[r[3]][0] != r[0] and len(blank_ids) < 2:
            blank_ids.append(r[0])

    def render_state(code, i):
        variants = [code_to_name.get(code, code), f"{code} ", code.lower(), code]
        return variants[i % len(variants)]

    def render_type(t, i):
        return [t.lower(), t.upper(), t][i % 3]

    lines = ["Facility ID,Facility Name,Type,City,State,Region"]
    def emit(r, i, name_pad=False):
        fid, name, ftype, city, state, region = r
        nm = f"  {name} " if name_pad else name
        reg = "" if fid in blank_ids else region
        lines.append(f"{fid},{nm},{render_type(ftype,i)},{city},{render_state(state,i)},{reg}")

    for i, r in enumerate(rows):
        emit(r, i, name_pad=(i % 4 == 0))
        if i == 2:  # duplicate the 3rd facility, re-cased, right after it
            emit((r[0], r[1], r[2], r[3] + " ", r[4], r[5]), i + 1)
    lines.append("")  # trailing blank line
    return "\n".join(lines) + "\n"


def conform(csv_rows):
    """Answer key: apply the ETL lab's documented transforms to the raw rows.

    csv_rows: list of dicts with keys Facility ID, Facility Name, Type, City, State, Region.
    Returns the clean facility dimension as a list of tuples, matching the star-schema dim.
    Mirrors the Lakeflow Designer steps: trim -> standardize state -> proper-case type ->
    drop blank rows -> dedupe on facility_id -> fill region from a same-city sibling.
    """
    cleaned = {}
    city_region = {}
    for r in csv_rows:
        fid = (r.get("Facility ID") or "").strip()
        if not fid:
            continue
        name = " ".join((r.get("Facility Name") or "").split())
        ftype = " ".join((r.get("Type") or "").split()).title()
        city = " ".join((r.get("City") or "").split())
        state = standardize_state(r.get("State"))
        region = " ".join((r.get("Region") or "").split())
        if region:
            city_region.setdefault(city, region)
        cleaned[fid] = [fid, name, ftype, city, state, region]  # dedupe on facility_id
    for row in cleaned.values():
        if not row[5]:                       # fill blank region from a same-city sibling
            row[5] = city_region.get(row[3], None)
    return sorted(tuple(r) for r in cleaned.values())
