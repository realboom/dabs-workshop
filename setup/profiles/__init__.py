"""Workshop data profiles.

A profile is the single source of truth for one synthetic population. The generator and the
ETL-lab raw-CSV builder both load a profile by name, so the two never drift. Add a vertical by
dropping a new module in here that exposes a `PROFILE` dict (see adult.py / pediatric.py) and
registering it below.
"""
from . import adult, pediatric

PROFILES = {
    adult.PROFILE["name"]: adult.PROFILE,
    pediatric.PROFILE["name"]: pediatric.PROFILE,
}


def get_profile(name):
    """Return the PROFILE dict for `name` (e.g. 'adult', 'pediatric')."""
    key = (name or "").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"Unknown profile {name!r}. Available: {', '.join(sorted(PROFILES))}")
    return PROFILES[key]
