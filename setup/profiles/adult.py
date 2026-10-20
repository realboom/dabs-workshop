"""Adult / acute-care profile.

Adult hospital encounters (inpatient / outpatient / emergency) with condition-dependent
outcomes (readmission, mortality, complications). Generic synthetic data — facility and
place names are illustrative, not tied to any real health system.
"""

# (icd10_code, description, clinical_category, base_mortality, base_complication, base_readmit)
DIAGNOSES = [
    ("I21.4",  "Non-ST elevation myocardial infarction (NSTEMI)", "Cardiovascular", 0.06, 0.18, 0.20),
    ("I50.9",  "Heart failure, unspecified",                      "Cardiovascular", 0.05, 0.15, 0.24),
    ("I63.9",  "Cerebral infarction (stroke), unspecified",       "Cardiovascular", 0.08, 0.20, 0.18),
    ("I48.91", "Atrial fibrillation, unspecified",                "Cardiovascular", 0.02, 0.08, 0.14),
    ("J18.9",  "Pneumonia, unspecified organism",                 "Respiratory",    0.04, 0.12, 0.16),
    ("J44.1",  "COPD with acute exacerbation",                    "Respiratory",    0.03, 0.11, 0.21),
    ("J96.00", "Acute respiratory failure",                       "Respiratory",    0.10, 0.22, 0.19),
    ("M17.11", "Unilateral primary osteoarthritis, right knee",   "Orthopedic",     0.002,0.06, 0.07),
    ("M17.12", "Unilateral primary osteoarthritis, left knee",    "Orthopedic",     0.002,0.06, 0.07),
    ("M16.11", "Unilateral primary osteoarthritis, right hip",    "Orthopedic",     0.002,0.06, 0.07),
    ("S72.001A","Fracture of femur, initial encounter",           "Orthopedic",     0.02, 0.10, 0.12),
    ("E11.65", "Type 2 diabetes with hyperglycemia",              "Endocrine",      0.01, 0.07, 0.13),
    ("E11.10", "Type 2 diabetes with ketoacidosis",              "Endocrine",      0.03, 0.10, 0.17),
    ("N17.9",  "Acute kidney failure, unspecified",               "Renal",          0.07, 0.16, 0.22),
    ("N18.6",  "End stage renal disease",                         "Renal",          0.06, 0.14, 0.25),
    ("K35.80", "Acute appendicitis, unspecified",                 "Gastrointestinal",0.005,0.05, 0.06),
    ("K85.90", "Acute pancreatitis, unspecified",                 "Gastrointestinal",0.03, 0.12, 0.15),
    ("A41.9",  "Sepsis, unspecified organism",                    "Infectious",     0.14, 0.25, 0.20),
    ("O80",    "Encounter for full-term uncomplicated delivery",  "Maternity",      0.0005,0.03, 0.04),
    ("O14.90", "Pre-eclampsia, unspecified",                      "Maternity",      0.004,0.09, 0.10),
    ("C50.911","Malignant neoplasm of right breast",              "Oncology",       0.05, 0.13, 0.16),
    ("C34.90", "Malignant neoplasm of lung",                      "Oncology",       0.12, 0.20, 0.19),
    ("F32.9",  "Major depressive disorder, single episode",       "Behavioral",     0.005,0.04, 0.11),
    ("R07.9",  "Chest pain, unspecified",                         "Cardiovascular", 0.005,0.04, 0.09),
]

# (procedure_code, description, category); None => no procedure performed
PROCEDURES = [
    ("27447", "Total knee arthroplasty (knee replacement)",       "Orthopedic Surgery"),
    ("27130", "Total hip arthroplasty (hip replacement)",         "Orthopedic Surgery"),
    ("27236", "Open treatment of femoral fracture",               "Orthopedic Surgery"),
    ("92928", "Percutaneous coronary intervention (stent)",       "Cardiac Procedure"),
    ("33533", "Coronary artery bypass graft (CABG)",              "Cardiac Surgery"),
    ("93010", "Electrocardiogram interpretation",                 "Cardiac Diagnostic"),
    ("44970", "Laparoscopic appendectomy",                        "General Surgery"),
    ("47562", "Laparoscopic cholecystectomy",                     "General Surgery"),
    ("59400", "Routine obstetric care incl. vaginal delivery",    "Maternity"),
    ("59510", "Routine obstetric care incl. cesarean delivery",   "Maternity"),
    ("90935", "Hemodialysis procedure",                           "Renal"),
    ("31500", "Endotracheal intubation, emergency",               "Critical Care"),
    ("99291", "Critical care, first 30-74 minutes",               "Critical Care"),
    ("99223", "Initial hospital inpatient care, high complexity", "Evaluation & Mgmt"),
    ("99285", "Emergency department visit, high complexity",      "Emergency"),
    ("19303", "Mastectomy, simple, complete",                     "Oncology Surgery"),
    ("96413", "Chemotherapy administration, IV infusion",         "Oncology Treatment"),
    (None,    "No procedure performed",                           "None"),
]

SPECIALTIES = ["Cardiology", "Pulmonology", "Orthopedic Surgery", "Internal Medicine",
               "Nephrology", "General Surgery", "Obstetrics & Gynecology", "Oncology",
               "Emergency Medicine", "Hospitalist"]

# Specialties that serve as a patient's assigned primary care provider (PCP).
PRIMARY_CARE_SPECIALTIES = {"Internal Medicine", "Hospitalist"}

# (facility_name, facility_type, city, state_code, region). Salt Lake City / Provo appear
# more than once so the gold "derive region from a same-city sibling" step has data to work with.
FACILITY_SEED = [
    ("Wasatch Regional Medical Center",   "Inpatient Hospital", "Salt Lake City", "UT", "Wasatch Front"),
    ("Canyon View Hospital",              "Inpatient Hospital", "Provo",          "UT", "Wasatch Front"),
    ("Great Salt Lake Medical Center",    "Inpatient Hospital", "Ogden",          "UT", "Northern Utah"),
    ("Red Rock Regional Hospital",        "Inpatient Hospital", "St. George",     "UT", "Southern Utah"),
    ("Cache Valley Community Hospital",    "Critical Access",    "Logan",          "UT", "Northern Utah"),
    ("Treasure Valley Medical Center",    "Inpatient Hospital", "Boise",          "ID", "Idaho"),
    ("Snake River Hospital",              "Critical Access",    "Idaho Falls",    "ID", "Idaho"),
    ("High Desert Specialty Clinic",      "Outpatient Clinic",  "Las Vegas",      "NV", "Nevada"),
    ("Mountain West Surgical Center",     "Ambulatory Surgery", "Salt Lake City", "UT", "Wasatch Front"),
    ("Bonneville Family Clinic",          "Outpatient Clinic",  "Provo",          "UT", "Wasatch Front"),
    ("Summit Cardiology Institute",       "Specialty Center",   "Salt Lake City", "UT", "Wasatch Front"),
    ("Valley Women's & Children's",       "Specialty Center",   "Murray",         "UT", "Wasatch Front"),
]

PROFILE = {
    "name": "adult",
    "label": "Adult / acute care",
    "description": "Adult hospital encounters with outcomes (readmission, mortality, complications).",
    "facility_seed": FACILITY_SEED,
    "diagnoses": DIAGNOSES,
    "procedures": PROCEDURES,
    "specialties": SPECIALTIES,
    "primary_care_specialties": PRIMARY_CARE_SPECIALTIES,
    "age": {"mean": 58, "std": 18, "min": 0, "max": 99},
    # Per-band cost multiplier on charges (paid tracks charges): adult spend rises with age —
    # 65+ highest (chronic disease, more intervention), under-40 lowest. [low, high, mult].
    "age_cost_bands": [[0, 39, 0.8], [40, 64, 1.1], [65, 99, 1.6]],
}
