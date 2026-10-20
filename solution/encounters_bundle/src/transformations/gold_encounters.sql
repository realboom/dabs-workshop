-- Gold: one row per encounter with provider, facility, and diagnosis details.
-- The dashboard and the Genie agent both read this table.
CREATE MATERIALIZED VIEW gold_encounters
COMMENT "Encounters with provider, facility, and diagnosis details, ready for reporting."
AS SELECT
  e.encounter_id, e.admit_date, e.encounter_type, e.payer_type, e.length_of_stay_days,
  e.total_charges, e.total_paid, e.readmitted_30d, e.mortality_flag, e.complication_flag,
  e.readmitted_30d * 100.0 AS readmit_pct, e.mortality_flag * 100.0 AS mortality_pct,
  e.complication_flag * 100.0 AS complication_pct,
  p.provider_name, p.specialty, f.facility_name, f.region, f.facility_type, d.clinical_category
FROM silver_encounters e
JOIN `${source_catalog}`.`${source_schema}`.dim_provider p USING (provider_id)
JOIN `${source_catalog}`.`${source_schema}`.dim_facility f USING (facility_id)
JOIN `${source_catalog}`.`${source_schema}`.dim_diagnosis d ON e.primary_icd10_code = d.icd10_code;
