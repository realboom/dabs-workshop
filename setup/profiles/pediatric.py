"""Pediatric profile.

Children's-health encounters (ages 0-18): primary-care and specialty visits plus some
inpatient / ED, with pediatric diagnoses and procedures. Mortality is very low (as in real
pediatrics); continuity of care with an assigned pediatrician is the headline quality metric.
Generic synthetic data — facility and place names are illustrative, not tied to any real
health system.
"""

# (icd10_code, description, clinical_category, base_mortality, base_complication, base_readmit)
DIAGNOSES = [
    ("J45.909", "Asthma, unspecified, uncomplicated",            "Respiratory",     0.0002, 0.03, 0.08),
    ("J45.901", "Asthma with (acute) exacerbation",              "Respiratory",     0.0005, 0.05, 0.12),
    ("J21.0",   "Acute bronchiolitis due to RSV",                "Respiratory",     0.001,  0.06, 0.10),
    ("J06.9",   "Acute upper respiratory infection",             "Respiratory",     0.0001, 0.02, 0.05),
    ("J12.9",   "Viral pneumonia, unspecified",                  "Respiratory",     0.002,  0.08, 0.11),
    ("H66.90",  "Otitis media, unspecified (ear infection)",     "ENT",             0.0,    0.01, 0.06),
    ("J02.9",   "Acute pharyngitis (sore throat)",               "ENT",             0.0,    0.01, 0.04),
    ("J03.90",  "Acute tonsillitis, unspecified",                "ENT",             0.0,    0.02, 0.05),
    ("A09",     "Infectious gastroenteritis",                    "Gastrointestinal",0.0005, 0.03, 0.07),
    ("K35.80",  "Acute appendicitis, unspecified",               "Gastrointestinal",0.001,  0.05, 0.05),
    ("R50.9",   "Fever, unspecified",                            "General",         0.0002, 0.02, 0.06),
    ("Z00.129", "Routine child health exam (well-child)",        "Preventive",      0.0,    0.005,0.02),
    ("E10.9",   "Type 1 diabetes mellitus",                      "Endocrine",       0.002,  0.08, 0.15),
    ("E10.10",  "Type 1 diabetes with ketoacidosis",             "Endocrine",       0.005,  0.12, 0.18),
    ("F90.9",   "Attention-deficit hyperactivity disorder",      "Behavioral",      0.0,    0.02, 0.09),
    ("F41.9",   "Anxiety disorder, unspecified",                 "Behavioral",      0.0,    0.02, 0.10),
    ("G40.909", "Epilepsy, unspecified",                         "Neurology",       0.002,  0.07, 0.13),
    ("R56.00",  "Febrile convulsions",                           "Neurology",       0.0005, 0.03, 0.08),
    ("S52.501A","Fracture of the radius, initial encounter",     "Orthopedic",      0.0,    0.04, 0.05),
    ("N39.0",   "Urinary tract infection",                       "Renal",           0.0002, 0.03, 0.09),
    ("P59.9",   "Neonatal jaundice, unspecified",                "Neonatal",        0.001,  0.04, 0.10),
    ("Q21.0",   "Ventricular septal defect (congenital)",        "Congenital",      0.006,  0.10, 0.16),
]

# (procedure_code, description, category); None => no procedure performed
PROCEDURES = [
    ("90460", "Immunization administration",                     "Preventive"),
    ("99392", "Well-child preventive visit",                     "Preventive"),
    ("99213", "Office/outpatient visit, established patient",    "Evaluation & Mgmt"),
    ("99283", "Emergency department visit, moderate complexity", "Emergency"),
    ("42820", "Tonsillectomy and adenoidectomy",                 "ENT Surgery"),
    ("69436", "Tympanostomy (ear tubes)",                        "ENT Surgery"),
    ("44970", "Laparoscopic appendectomy",                       "General Surgery"),
    ("25600", "Closed treatment of radius fracture",             "Orthopedic"),
    ("94640", "Nebulizer / inhalation treatment",                "Respiratory"),
    ("94010", "Spirometry (breathing test)",                     "Respiratory Diagnostic"),
    ("93000", "Electrocardiogram",                               "Cardiac Diagnostic"),
    ("96110", "Developmental screening",                         "Behavioral"),
    ("51701", "Bladder catheterization (urine sample)",          "Urology"),
    ("99460", "Newborn care, initial hospital",                  "Neonatal"),
    ("62270", "Lumbar puncture (spinal fluid tap)",              "Neurology"),
    (None,    "No procedure performed",                          "None"),
]

SPECIALTIES = ["General Pediatrics", "Pediatric Cardiology", "Pediatric Pulmonology",
               "Neonatology", "Pediatric Surgery", "Pediatric Emergency Medicine",
               "Pediatric Hospitalist", "Pediatric Endocrinology", "Pediatric Neurology",
               "Pediatric Gastroenterology"]

# A child's assigned PCP is a general pediatrician (or peds hospitalist covering primary care).
PRIMARY_CARE_SPECIALTIES = {"General Pediatrics", "Pediatric Hospitalist"}

# (facility_name, facility_type, city, state_code, region). Denver / Seattle / Phoenix each
# appear twice so the gold "derive region from a same-city sibling" step has data to work with.
FACILITY_SEED = [
    ("Summit Children's Hospital",         "Pediatric Hospital", "Denver",      "CO", "Mountain"),
    ("Riverside Pediatric Center",         "Pediatric Hospital", "Denver",      "CO", "Mountain"),
    ("Bayview Children's Medical Center",  "Pediatric Hospital", "Seattle",     "WA", "Pacific Northwest"),
    ("Lakeshore Pediatric Clinic",         "Pediatric Clinic",    "Seattle",     "WA", "Pacific Northwest"),
    ("Prairie Children's Hospital",        "Pediatric Hospital", "Kansas City", "MO", "Midwest"),
    ("Gateway Pediatric Specialty Center", "Specialty Center",    "St. Louis",   "MO", "Midwest"),
    ("Harborview Children's Clinic",       "Pediatric Clinic",    "Boston",      "MA", "Northeast"),
    ("Piedmont Children's Hospital",       "Pediatric Hospital", "Atlanta",     "GA", "Southeast"),
    ("Sunrise Pediatric Urgent Care",      "Urgent Care",         "Phoenix",     "AZ", "Southwest"),
    ("Cactus Children's Clinic",           "Pediatric Clinic",    "Phoenix",     "AZ", "Southwest"),
    ("Magnolia Children's Medical Center", "Pediatric Hospital","Dallas",      "TX", "South Central"),
    ("Bluebonnet Pediatric Clinic",        "Pediatric Clinic",    "Austin",      "TX", "South Central"),
]

PROFILE = {
    "name": "pediatric",
    "label": "Pediatric / children's health",
    "description": "Children's-health encounters (ages 0-18); PCP continuity of care is the headline metric.",
    "facility_seed": FACILITY_SEED,
    "diagnoses": DIAGNOSES,
    "procedures": PROCEDURES,
    "specialties": SPECIALTIES,
    "primary_care_specialties": PRIMARY_CARE_SPECIALTIES,
    "age": {"mean": 9, "std": 5, "min": 0, "max": 18},
    # Age is drawn from these bands (young-skewed, as real pediatric utilization is) so every
    # band is well represented instead of bunching in 5-12. Each entry is [low, high, weight].
    "age_bands": [[0, 0, 0.12], [1, 4, 0.28], [5, 12, 0.35], [13, 18, 0.25]],
    # Per-band cost multiplier on charges (paid tracks charges), mirroring real pediatric spend:
    # infants highest (NICU / congenital / neonatal), mid-childhood lowest (healthiest years),
    # teens rising (sports injuries, behavioral health, chronic-disease onset). [low, high, mult].
    "age_cost_bands": [[0, 0, 1.7], [1, 4, 1.05], [5, 12, 0.8], [13, 18, 1.2]],
}
