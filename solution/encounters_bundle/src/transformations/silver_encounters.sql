-- Silver: encounters from the shared source, with data quality expectations.
CREATE MATERIALIZED VIEW silver_encounters (
  CONSTRAINT valid_encounter_id EXPECT (encounter_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_stay EXPECT (discharge_date >= admit_date) ON VIOLATION DROP ROW,
  CONSTRAINT non_negative_charges EXPECT (total_charges >= 0)
)
COMMENT "Encounters with basic data quality checks."
AS SELECT * FROM `<your_catalog>`.analyst101_shared.fact_encounters;
