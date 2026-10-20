# Databricks notebook source
# MAGIC %md
# MAGIC # Analyst 101 Workshop — Synthetic Medical Dataset
# MAGIC
# MAGIC Generates a realistic (but 100% synthetic, no PHI) hospital/clinic encounters dataset
# MAGIC for the Analyst 101 workshop. The schema mirrors the kind of data
# MAGIC the analysts work with day to day: **something happened** (a diagnosis / procedure),
# MAGIC **where it happened** (provider + facility), and **the outcome** (readmission,
# MAGIC mortality, complication) — designed so we can demonstrate:
# MAGIC
# MAGIC - **Aggregations** by provider and facility
# MAGIC - **Trends** over time (36 months of encounters)
# MAGIC - **Drill-downs** (region → facility → provider → encounter)
# MAGIC - **Outcome rates** (readmit / mortality / complication) for quality dashboards
# MAGIC
# MAGIC ### Output tables (star schema)
# MAGIC | Table | Grain | Purpose |
# MAGIC |---|---|---|
# MAGIC | `dim_provider` | one row per provider | provider name, specialty, region |
# MAGIC | `dim_facility` | one row per facility | hospital/clinic name, type, city/state/region |
# MAGIC | `dim_diagnosis` | one row per ICD-10 code | ICD-10 code + description + clinical category |
# MAGIC | `dim_procedure` | one row per procedure code | procedure code + description + category |
# MAGIC | `dim_patient` | one row per patient | assigned PCP + home facility (drives PCP continuity) |
# MAGIC | `dim_visit_type` | one row per visit type | visit-type reference; non-standard types are excluded from PCP continuity |
# MAGIC | `fact_encounters` | one row per patient encounter | the analytic fact table |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters
# MAGIC All values are parameterized via widgets — never hardcoded. Adjust catalog/schema to
# MAGIC point at wherever the workshop workspace stages content.

# COMMAND ----------

dbutils.widgets.text("catalog", "demo", "Target catalog")
dbutils.widgets.text("schema", "analyst101_shared", "Target schema")
dbutils.widgets.text("num_encounters", "80000", "Number of encounters to generate")
dbutils.widgets.text("num_providers", "45", "Number of providers")
dbutils.widgets.text("num_facilities", "12", "Number of facilities")
dbutils.widgets.text("num_patients", "12000", "Number of patients (for PCP continuity)")
dbutils.widgets.dropdown("profile", "adult", ["adult", "pediatric"], "Data profile (population)")
dbutils.widgets.text("start_date", "2023-01-01", "Encounter start date")
dbutils.widgets.text("end_date", "2025-12-31", "Encounter end date")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
NUM_ENCOUNTERS = int(dbutils.widgets.get("num_encounters"))
NUM_PROVIDERS = int(dbutils.widgets.get("num_providers"))
NUM_FACILITIES = int(dbutils.widgets.get("num_facilities"))
NUM_PATIENTS = int(dbutils.widgets.get("num_patients"))
PROFILE_NAME = dbutils.widgets.get("profile")
START_DATE = dbutils.widgets.get("start_date")
END_DATE = dbutils.widgets.get("end_date")

print(f"Generating {NUM_ENCOUNTERS:,} encounters into {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create catalog + schema

# COMMAND ----------

# Ensure the target catalog exists. If it already exists, do nothing (no misleading warning).
# If it is missing, try to auto-create it — but on metastores with no default storage root,
# CREATE CATALOG without a location fails ("Metastore storage root URL does not exist"); in that
# case stop with a clear, actionable message rather than continuing into confusing errors.
if spark.sql(f"SHOW CATALOGS LIKE '{CATALOG}'").count() == 0:
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
    except Exception as e:
        raise Exception(
            f"Catalog '{CATALOG}' does not exist and could not be auto-created (no default storage "
            f"root). Create it once in the Catalog UI (Catalog > Create catalog) or with an explicit "
            f"MANAGED LOCATION, then re-run. Details: {e}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load the data profile
# MAGIC A **profile** (see `profiles/`) is the single source of truth for one synthetic population
# MAGIC — its facilities, diagnoses, procedures, specialties, and age distribution. The `profile`
# MAGIC widget (`adult` / `pediatric`) selects it. The ETL-lab raw CSV is built from the SAME
# MAGIC profile (`etl_lab/build_raw_csv.py`), so the workshop data and the lab file never drift.
# MAGIC
# MAGIC Requires the repo on the Python path — works in a Databricks Git folder or local checkout.

# COMMAND ----------

import os, sys

# Make the repo root importable (Databricks Git folder or local checkout).
_d = os.getcwd()
for _ in range(6):
    if os.path.exists(os.path.join(_d, "profiles", "__init__.py")):
        if _d not in sys.path:
            sys.path.insert(0, _d)
        break
    _d = os.path.dirname(_d)

from profiles import get_profile
from profiles.common import (FIRST_NAMES as FIRST, LAST_NAMES as LAST, VISIT_TYPES,
                             COMPLICATION_TYPES, ENCOUNTER_TYPES, PAYER_TYPES)

PROFILE = get_profile(PROFILE_NAME)
DIAGNOSES = PROFILE["diagnoses"]
PROCEDURES = PROFILE["procedures"]
SPECIALTIES = PROFILE["specialties"]
PRIMARY_CARE_SPECIALTIES = PROFILE["primary_care_specialties"]
FACILITY_SEED = PROFILE["facility_seed"]
AGE = PROFILE["age"]
# Optional band-weighted age sampling: [[low, high, weight], ...]. When present (e.g. pediatric),
# age is drawn band-first so every age group is well represented rather than bunched at the mean.
_AGE_BANDS = PROFILE.get("age_bands")
if _AGE_BANDS:
    _age_ranges = [(b[0], b[1]) for b in _AGE_BANDS]
    _age_weights = [b[2] for b in _AGE_BANDS]

# Optional per-band cost multiplier on charges, so avg charges/paid vary by age band the way real
# claims data does (e.g. pediatric infants highest, mid-childhood lowest). [[low, high, mult], ...].
_AGE_COST = PROFILE.get("age_cost_bands")
def _age_cost_mult(a):
    for lo, hi, m in (_AGE_COST or []):
        if lo <= a <= hi:
            return m
    return 1.0
print(f"Profile: {PROFILE['name']} — {PROFILE['label']} "
      f"({len(DIAGNOSES)} diagnoses, {len(FACILITY_SEED)} facilities, ages {AGE['min']}-{AGE['max']})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build dimension tables

# COMMAND ----------

import random
from pyspark.sql import functions as F, types as T
from datetime import date

random.seed(42)

# --- dim_diagnosis ---
dim_diagnosis = spark.createDataFrame(
    [(c, d, cat) for (c, d, cat, *_ ) in DIAGNOSES],
    "icd10_code string, icd10_description string, clinical_category string",
)
dim_diagnosis.write.mode("overwrite").saveAsTable("dim_diagnosis")

# --- dim_procedure ---
dim_procedure = spark.createDataFrame(
    [(code if code else "NONE", desc, cat) for (code, desc, cat) in PROCEDURES],
    "procedure_code string, procedure_description string, procedure_category string",
)
dim_procedure.write.mode("overwrite").saveAsTable("dim_procedure")

# --- dim_facility ---
facility_rows = [
    (f"FAC{idx+1:03d}", name, ftype, city, state, region)
    for idx, (name, ftype, city, state, region) in enumerate(FACILITY_SEED[:NUM_FACILITIES])
]
dim_facility = spark.createDataFrame(
    facility_rows,
    "facility_id string, facility_name string, facility_type string, city string, state string, region string",
)
dim_facility.write.mode("overwrite").saveAsTable("dim_facility")

# --- dim_provider --- (FIRST / LAST name pools imported from profiles.common)
provider_rows = []  # [provider_id, npi, name, specialty, primary_facility_id, is_pcp]
for i in range(NUM_PROVIDERS):
    npi = str(random.randint(1000000000, 9999999999))  # 10-digit NPI-style id
    name = f"Dr. {random.choice(FIRST)} {random.choice(LAST)}"
    specialty = random.choice(SPECIALTIES)
    fac = random.choice(facility_rows)
    is_pcp = specialty in PRIMARY_CARE_SPECIALTIES
    provider_rows.append([f"PRV{i+1:03d}", npi, name, specialty, fac[0], is_pcp])

# Guarantee every facility that has providers has at least one PCP, so each patient's home
# facility can supply an assigned PCP.
prov_by_fac = {}
for r in provider_rows:
    prov_by_fac.setdefault(r[4], []).append(r)
for fac_id, plist in prov_by_fac.items():
    if not any(p[5] for p in plist):
        plist[0][5] = True  # promote the first provider at this facility to PCP

dim_provider = spark.createDataFrame(
    [tuple(r) for r in provider_rows],
    "provider_id string, npi string, provider_name string, specialty string, "
    "primary_facility_id string, is_pcp boolean",
)
dim_provider.write.mode("overwrite").saveAsTable("dim_provider")

# --- dim_visit_type --- (no is_standard flag; the "standard visit" rule lives in the governed
# assets as visit_type_id = 'OFFICE', not as a column here)
dim_visit_type = spark.createDataFrame(
    [(vid, vname) for (vid, vname, _s, _w) in VISIT_TYPES],
    "visit_type_id string, visit_type_name string",
)
dim_visit_type.write.mode("overwrite").saveAsTable("dim_visit_type")

# --- dim_patient --- each patient has a home facility and an assigned PCP practicing there
pcp_by_fac = {fac_id: [p[0] for p in plist if p[5]] for fac_id, plist in prov_by_fac.items()}
pcp_facilities = [f for f, pcps in pcp_by_fac.items() if pcps]
patient_rows = []  # (patient_id, assigned_pcp_id, home_facility_id, patient_sex)
for i in range(NUM_PATIENTS):
    home_fac = random.choice(pcp_facilities)
    patient_rows.append((f"PAT{i+1:08d}", random.choice(pcp_by_fac[home_fac]),
                         home_fac, random.choice(["F", "M"])))
dim_patient = spark.createDataFrame(
    patient_rows,
    "patient_id string, assigned_pcp_id string, home_facility_id string, patient_sex string",
)
dim_patient.write.mode("overwrite").saveAsTable("dim_patient")

print("Dimensions written (diagnosis, procedure, facility, provider, visit_type, patient).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build fact_encounters
# MAGIC Outcomes are condition-dependent (driven by the baseline rates per diagnosis) and
# MAGIC nudged by age and length of stay, so quality dashboards show meaningful variation
# MAGIC across diagnoses, providers, and facilities — not uniform noise.

# COMMAND ----------

diag_lookup = {c: (mort, comp, readm) for (c, d, cat, mort, comp, readm) in DIAGNOSES}
diag_codes = [c for (c, *_) in DIAGNOSES]
proc_codes = [code if code else "NONE" for (code, *_) in PROCEDURES]
provider_ids = [r[0] for r in provider_rows]
prov_to_fac = {r[0]: r[4] for r in provider_rows}

# --- PCP-continuity lookups ---
prov_ids_by_fac = {}
for r in provider_rows:
    prov_ids_by_fac.setdefault(r[4], []).append(r[0])
pcp_ids = [r[0] for r in provider_rows if r[5]]
# Each PCP has a base continuity propensity, so per-provider/facility ratios vary realistically.
pcp_continuity_base = {pid: random.uniform(0.55, 0.90) for pid in pcp_ids}
patient_ids = [p[0] for p in patient_rows]
patient_pcp = {p[0]: p[1] for p in patient_rows}
patient_home = {p[0]: p[2] for p in patient_rows}
patient_sex_map = {p[0]: p[3] for p in patient_rows}
visit_type_ids = [v[0] for v in VISIT_TYPES]
visit_type_weights = [v[3] for v in VISIT_TYPES]
visit_is_standard = {v[0]: v[2] for v in VISIT_TYPES}

# COMPLICATION_TYPES / ENCOUNTER_TYPES / PAYER_TYPES imported from profiles.common
start = date.fromisoformat(START_DATE)
end = date.fromisoformat(END_DATE)
span_days = (end - start).days

# --- monthly volume curve: YoY growth + seasonality, so trends and forecasts aren't flat ---
import calendar
ANNUAL_GROWTH = 0.10  # ~+10% year over year
# seasonal multiplier by calendar month (Jan..Dec); profile-aware
_SEASONAL = {
    "pediatric": [1.30, 1.20, 1.05, 0.90, 0.80, 0.75, 0.75, 0.80, 0.95, 1.10, 1.25, 1.35],  # winter respiratory peak
    "adult":     [1.10, 1.05, 1.00, 0.98, 0.97, 0.95, 0.95, 0.97, 1.00, 1.03, 1.05, 1.08],  # mild winter bump
}
_seasonal = _SEASONAL.get(PROFILE_NAME, _SEASONAL["adult"])
# one weighted bucket per calendar month in [start, end]
_month_lo, _month_hi, _month_wt = [], [], []
_y, _m, _idx = start.year, start.month, 0
while (_y, _m) <= (end.year, end.month):
    _month_lo.append(max(date(_y, _m, 1), start).toordinal())
    _month_hi.append(min(date(_y, _m, calendar.monthrange(_y, _m)[1]), end).toordinal())
    _month_wt.append(((1 + ANNUAL_GROWTH) ** (_idx / 12.0)) * _seasonal[_m - 1])
    _idx += 1
    _y, _m = (_y + 1, 1) if _m == 12 else (_y, _m + 1)
_month_ix = list(range(len(_month_wt)))

def gen_row(i):
    rnd = random.random
    icd = random.choice(diag_codes)
    base_mort, base_comp, base_readm = diag_lookup[icd]

    # patient drives facility (their home facility) and sex
    pid = random.choice(patient_ids)
    fac = patient_home[pid]
    assigned_pcp = patient_pcp[pid]
    sex = patient_sex_map[pid]

    # visit type; continuity is measured on standard visits only
    vtype = random.choices(visit_type_ids, weights=visit_type_weights)[0]
    is_std = visit_is_standard[vtype]

    # attending provider: on a standard visit the patient sees their assigned PCP with a
    # PCP-specific propensity (yields realistic, varying continuity ratios); otherwise they
    # see another provider practicing at the same facility.
    if is_std and rnd() < pcp_continuity_base[assigned_pcp]:
        prov = assigned_pcp
    else:
        others = [p for p in prov_ids_by_fac[fac] if p != assigned_pcp]
        prov = random.choice(others) if others else assigned_pcp

    enc_type = random.choices(ENCOUNTER_TYPES, weights=[0.45, 0.35, 0.20])[0]
    # outpatient encounters usually have no procedure / short stay
    if enc_type == "Outpatient":
        proc = random.choice(proc_codes)
        los = 0
    else:
        proc = random.choice(proc_codes)
        los = max(0, int(random.gauss(4, 3)))

    if _AGE_BANDS:
        _alo, _ahi = random.choices(_age_ranges, weights=_age_weights)[0]
        age = random.randint(_alo, _ahi)
    else:
        age = min(AGE["max"], max(AGE["min"], int(random.gauss(AGE["mean"], AGE["std"]))))

    # place the encounter in a month drawn from the volume curve (growth + seasonality),
    # then a random day within it — capped so discharge (admit + los) never spills past END_DATE
    _b = random.choices(_month_ix, weights=_month_wt)[0]
    _lo, _hi = _month_lo[_b], min(_month_hi[_b], end.toordinal() - los)
    if _hi < _lo:
        _hi = _lo
    admit = random.randint(_lo, _hi)
    admit_date = date.fromordinal(admit)
    discharge_date = date.fromordinal(admit + los)

    # age / LOS multipliers make outcomes realistic
    age_mult = 1.0 + max(0, (age - 65)) * 0.012
    los_mult = 1.0 + los * 0.03

    mortality = 1 if rnd() < base_mort * age_mult else 0
    complication = 1 if rnd() < base_comp * los_mult else 0
    comp_type = random.choice(COMPLICATION_TYPES) if complication else None
    # only survivors can be readmitted
    readmit = 1 if (mortality == 0 and rnd() < base_readm * age_mult) else 0

    # base charges from LOS + procedure, then scaled by an age-band cost multiplier so charges
    # (and paid, which tracks charges) vary realistically across age bands
    charges = round((random.uniform(800, 4000) + los * random.uniform(1500, 4500)
                     + (8000 if proc != "NONE" else 0) * random.uniform(0.5, 2.5))
                    * _age_cost_mult(age), 2)
    paid = round(charges * random.uniform(0.35, 0.85), 2)
    payer = random.choices(PAYER_TYPES, weights=[0.5, 0.3, 0.15, 0.05])[0]

    return (
        f"ENC{i+1:08d}", pid,
        prov, fac, icd, proc, enc_type, payer, vtype,
        admit_date, discharge_date, los, age, sex,
        charges, paid, readmit, mortality, complication, comp_type,
    )

schema = T.StructType([
    T.StructField("encounter_id", T.StringType()),
    T.StructField("patient_id", T.StringType()),
    T.StructField("provider_id", T.StringType()),
    T.StructField("facility_id", T.StringType()),
    T.StructField("primary_icd10_code", T.StringType()),
    T.StructField("primary_procedure_code", T.StringType()),
    T.StructField("encounter_type", T.StringType()),
    T.StructField("payer_type", T.StringType()),
    T.StructField("visit_type_id", T.StringType()),
    T.StructField("admit_date", T.DateType()),
    T.StructField("discharge_date", T.DateType()),
    T.StructField("length_of_stay_days", T.IntegerType()),
    T.StructField("patient_age", T.IntegerType()),
    T.StructField("patient_sex", T.StringType()),
    T.StructField("total_charges", T.DoubleType()),
    T.StructField("total_paid", T.DoubleType()),
    T.StructField("readmitted_30d", T.IntegerType()),
    T.StructField("mortality_flag", T.IntegerType()),
    T.StructField("complication_flag", T.IntegerType()),
    T.StructField("complication_type", T.StringType()),
])

# Generate in the driver in batches (80k rows is small) then parallelize.
rows = [gen_row(i) for i in range(NUM_ENCOUNTERS)]
fact = spark.createDataFrame(rows, schema)
fact.write.mode("overwrite").saveAsTable("fact_encounters")
print(f"fact_encounters written: {fact.count():,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Add table + column comments (helps Genie + AI/BI Assistant)
# MAGIC Good comments make Genie answers and AI-assisted dashboard authoring noticeably better.
# MAGIC Every column is commented, not just a few.

# COMMAND ----------

TABLE_COMMENTS = {
    "fact_encounters": "One row per patient encounter (inpatient, outpatient, or emergency). Central fact table for the Analyst 101 workshop. Synthetic data, no PHI.",
    "dim_provider": "Providers (physicians) with specialty and primary facility. One row per provider.",
    "dim_facility": "Hospitals and clinics with type, city, state, and region. One row per facility.",
    "dim_diagnosis": "ICD-10 diagnosis codes with plain-language descriptions and clinical category. One row per code.",
    "dim_procedure": "Procedure codes (CPT-style) with descriptions and category. One row per code.",
    "dim_patient": "Patients with their assigned primary care provider (PCP) and home facility. One row per patient. PCP continuity compares each visit's attending provider to the patient's assigned PCP.",
    "dim_visit_type": "Visit type reference. One row per visit type.",
}

COLUMN_COMMENTS = {
    "fact_encounters": {
        "encounter_id": "Primary key. Unique identifier for the encounter.",
        "patient_id": "Foreign key to dim_patient. The patient seen at this encounter (a patient can have multiple encounters).",
        "provider_id": "Foreign key to dim_provider. The attending provider actually seen (may differ from the patient's assigned PCP).",
        "facility_id": "Foreign key to dim_facility. Where the encounter happened (the patient's home facility).",
        "primary_icd10_code": "Foreign key to dim_diagnosis. Primary ICD-10 diagnosis code.",
        "primary_procedure_code": "Foreign key to dim_procedure. Primary procedure code (NONE if no procedure).",
        "encounter_type": "Encounter setting: Inpatient, Outpatient, or Emergency.",
        "payer_type": "Payer category: Commercial, Medicare, Medicaid, or Self-Pay.",
        "visit_type_id": "Foreign key to dim_visit_type. Non-standard visit types are excluded from PCP continuity.",
        "admit_date": "Date the patient was admitted or seen.",
        "discharge_date": "Date the patient was discharged (same day as admit for outpatient).",
        "length_of_stay_days": "Number of days between admit and discharge.",
        "patient_age": "Patient age in years at the time of the encounter.",
        "patient_sex": "Patient sex: F or M.",
        "total_charges": "Total billed charges in USD.",
        "total_paid": "Total amount paid in USD.",
        "readmitted_30d": "1 if the patient was readmitted within 30 days of discharge, else 0.",
        "mortality_flag": "1 if the patient died during the encounter, else 0.",
        "complication_flag": "1 if a complication occurred during the encounter, else 0.",
        "complication_type": "Type of complication when complication_flag = 1, else null.",
    },
    "dim_provider": {
        "provider_id": "Primary key. Unique identifier for the provider.",
        "npi": "10-digit National Provider Identifier (synthetic).",
        "provider_name": "Provider display name.",
        "specialty": "Clinical specialty (e.g., Cardiology, Orthopedic Surgery).",
        "primary_facility_id": "Foreign key to dim_facility. The provider's primary facility.",
        "is_pcp": "TRUE if this provider serves as an assigned primary care provider (PCP).",
    },
    "dim_facility": {
        "facility_id": "Primary key. Unique identifier for the facility.",
        "facility_name": "Hospital or clinic name.",
        "facility_type": "Facility type (e.g., Inpatient Hospital, Outpatient Clinic).",
        "city": "City where the facility is located.",
        "state": "Two-letter state code.",
        "region": "Business region grouping for the facility.",
    },
    "dim_diagnosis": {
        "icd10_code": "Primary key. ICD-10 diagnosis code.",
        "icd10_description": "Plain-language description of the diagnosis.",
        "clinical_category": "Clinical grouping (e.g., Cardiovascular, Orthopedic, Oncology).",
    },
    "dim_procedure": {
        "procedure_code": "Primary key. CPT-style procedure code (NONE means no procedure).",
        "procedure_description": "Plain-language description of the procedure.",
        "procedure_category": "Procedure grouping (e.g., Orthopedic Surgery, Cardiac Procedure).",
    },
    "dim_patient": {
        "patient_id": "Primary key. Unique patient identifier.",
        "assigned_pcp_id": "Foreign key to dim_provider. The patient's assigned primary care provider (PCP). PCP continuity compares each visit's attending provider to this provider.",
        "home_facility_id": "Foreign key to dim_facility. The patient's home facility.",
        "patient_sex": "Patient sex: F or M.",
    },
    "dim_visit_type": {
        "visit_type_id": "Primary key. Visit type code.",
        "visit_type_name": "Human-readable visit type.",
    },
}

for tbl, comment in TABLE_COMMENTS.items():
    spark.sql(f"COMMENT ON TABLE {tbl} IS '{comment.replace(chr(39), chr(39)*2)}'")
for tbl, cols in COLUMN_COMMENTS.items():
    for col, comment in cols.items():
        safe = comment.replace("'", "''")  # escape quotes so comments stay valid SQL
        spark.sql(f"ALTER TABLE {tbl} ALTER COLUMN {col} COMMENT '{safe}'")

print("Comments applied to all tables and columns.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Add primary key and foreign key relationships
# MAGIC These are informational (RELY) constraints in Unity Catalog. They are not enforced at
# MAGIC write time, but Genie and the AI/BI Assistant use them to join tables automatically and
# MAGIC to understand the star schema. Primary-key columns must be NOT NULL first.

# COMMAND ----------

# 1) Make key columns NOT NULL (required before a PRIMARY KEY can be added).
NOT_NULL = {
    "dim_provider": "provider_id",
    "dim_facility": "facility_id",
    "dim_diagnosis": "icd10_code",
    "dim_procedure": "procedure_code",
    "dim_patient": "patient_id",
    "dim_visit_type": "visit_type_id",
    "fact_encounters": "encounter_id",
}
for tbl, col in NOT_NULL.items():
    spark.sql(f"ALTER TABLE {tbl} ALTER COLUMN {col} SET NOT NULL")

# 2) Primary + foreign keys. Order matters for re-runs: a PK can't be dropped while child FKs still
#    reference it, so we (a) drop all FKs first, (b) re-create the PKs, (c) re-create the FKs. This
#    keeps the notebook fully re-runnable — the naive "drop PKs then FKs" order fails on the 2nd run.
PRIMARY_KEYS = {
    "dim_provider": ("pk_dim_provider", "provider_id"),
    "dim_facility": ("pk_dim_facility", "facility_id"),
    "dim_diagnosis": ("pk_dim_diagnosis", "icd10_code"),
    "dim_procedure": ("pk_dim_procedure", "procedure_code"),
    "dim_patient": ("pk_dim_patient", "patient_id"),
    "dim_visit_type": ("pk_dim_visit_type", "visit_type_id"),
    "fact_encounters": ("pk_fact_encounters", "encounter_id"),
}
FOREIGN_KEYS = [
    ("fact_encounters", "fk_enc_provider",   "provider_id",            "dim_provider",   "provider_id"),
    ("fact_encounters", "fk_enc_facility",   "facility_id",            "dim_facility",   "facility_id"),
    ("fact_encounters", "fk_enc_diagnosis",  "primary_icd10_code",     "dim_diagnosis",  "icd10_code"),
    ("fact_encounters", "fk_enc_procedure",  "primary_procedure_code", "dim_procedure",  "procedure_code"),
    ("fact_encounters", "fk_enc_patient",    "patient_id",             "dim_patient",    "patient_id"),
    ("fact_encounters", "fk_enc_visit_type", "visit_type_id",          "dim_visit_type", "visit_type_id"),
    ("dim_provider",    "fk_provider_facility", "primary_facility_id", "dim_facility",   "facility_id"),
    ("dim_patient",     "fk_patient_pcp",       "assigned_pcp_id",     "dim_provider",   "provider_id"),
    ("dim_patient",     "fk_patient_facility",  "home_facility_id",    "dim_facility",   "facility_id"),
]
# (a) drop child FKs first (IF EXISTS — safe on the first run too)
for tbl, name, *_ in FOREIGN_KEYS:
    spark.sql(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS {name}")
# (b) (re)create primary keys — now nothing references them
for tbl, (name, col) in PRIMARY_KEYS.items():
    spark.sql(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS {name}")
    spark.sql(f"ALTER TABLE {tbl} ADD CONSTRAINT {name} PRIMARY KEY ({col})")
# (c) (re)create foreign keys
for tbl, name, col, ref_tbl, ref_col in FOREIGN_KEYS:
    spark.sql(f"ALTER TABLE {tbl} ADD CONSTRAINT {name} FOREIGN KEY ({col}) REFERENCES {ref_tbl} ({ref_col})")

print("Primary keys and foreign keys applied. Dataset fully documented and ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick sanity checks

# COMMAND ----------

display(spark.sql("""
  SELECT f.region_check, cnt, ROUND(100.0*readmits/cnt,1) AS readmit_pct,
         ROUND(100.0*deaths/cnt,2) AS mortality_pct, ROUND(100.0*comps/cnt,1) AS complication_pct
  FROM (
    SELECT fac.region AS region_check, COUNT(*) cnt,
           SUM(readmitted_30d) readmits, SUM(mortality_flag) deaths, SUM(complication_flag) comps
    FROM fact_encounters e JOIN dim_facility fac USING (facility_id)
    GROUP BY fac.region
  ) f ORDER BY cnt DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sanity check: PCP continuity
# MAGIC Continuity = share of STANDARD visits where the attending provider is the patient's
# MAGIC assigned PCP. Expect an overall ratio in roughly the 0.55–0.90 band, with meaningful
# MAGIC variation across facilities (this is what makes the Databricks Day metric-view / SQL-function
# MAGIC / Genie demo interesting).

# COMMAND ----------

display(spark.sql("""
  SELECT fac.region,
         COUNT(*) AS standard_visits,
         ROUND(100.0 * AVG(CASE WHEN e.provider_id = p.assigned_pcp_id THEN 1 ELSE 0 END), 1)
           AS pcp_continuity_pct
  FROM fact_encounters e
  JOIN dim_patient p     ON e.patient_id = p.patient_id
  JOIN dim_facility fac  ON e.facility_id = fac.facility_id
  WHERE e.visit_type_id = 'OFFICE'
  GROUP BY fac.region
  ORDER BY standard_visits DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## (Optional) Stage the messy ETL-lab file into a Volume
# MAGIC For the Foundations + ETL lab (Attendee Workbook, Part 0), attendees upload the raw CSV
# MAGIC themselves. This optional cell stages a **backup copy** in a shared volume so instructors
# MAGIC have it on hand if a laptop upload hiccups. It builds the deliberately-messy extract from the
# MAGIC **same profile** as the dataset (via `profiles.common`), so it always matches — no drift.
# MAGIC
# MAGIC Set `stage_raw_csv=true` to run it; it creates
# MAGIC `{catalog}.{schema}.landing/facilities_raw.{profile}.csv`.

# COMMAND ----------

dbutils.widgets.dropdown("stage_raw_csv", "false", ["true", "false"], "Stage ETL-lab raw CSV to a volume?")

if dbutils.widgets.get("stage_raw_csv") == "true":
    from profiles.common import build_messy_facility_csv
    RAW_CSV = build_messy_facility_csv(FACILITY_SEED)   # deterministic messy CSV for this profile
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.landing")
    vol_path = f"/Volumes/{CATALOG}/{SCHEMA}/landing/facilities_raw.{PROFILE_NAME}.csv"
    dbutils.fs.put(vol_path, RAW_CSV, overwrite=True)
    print(f"Staged messy ETL-lab CSV ({PROFILE_NAME}) at {vol_path}")
else:
    print("stage_raw_csv=false — skipped (attendees upload the profile's facilities_raw CSV themselves).")
