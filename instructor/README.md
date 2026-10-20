# Instructor build

Before the lab, the workspace needs the shared data and the four **dev assets** that students import:
a pipeline, an AI/BI dashboard, a Genie agent, and a job. This folder holds those assets in their
"built in dev" form, including the hard-coding the lab teaches students to remove.

| File | What it becomes |
|---|---|
| `pipeline/silver_encounters.sql`, `pipeline/gold_encounters.sql` | The pipeline's SQL, with the catalog written in |
| `encounters_outcomes.lvdash.json` | The `Encounters & Outcomes` dashboard (one dataset on your `gold_encounters`) |
| `encounters_outcomes_genie.json` | The `Encounters & Outcomes Genie` agent (table, instructions, example SQL, sample questions) |
| `encounters_refresh.job.json` | The `encounters_refresh` job (refreshes the pipeline daily, paused) |
| `build_dev_assets.sh` | Creates all four from these files |

`<catalog>`, `<schema>`, and `<source_schema>` in the files are filled in by the script.

## 1. Load the shared data (about 5 min)

1. Add this repo to the workspace as a **Git folder** (**Workspace → Create → Git folder**).
2. Open `setup/generate_workshop_data`, connect it to **Serverless**, and set the widgets:
   - `catalog` — the workshop catalog
   - `schema` — `analyst101_shared`
   - `profile` — `adult` or `pediatric`
3. **Run all.** It builds `fact_encounters` (80,000 rows) and six `dim_*` tables.

## 2. Build the four dev assets (about 3 min)

Use **your own schema** for these, not one a student will use. A table can belong to only one
pipeline, so a student deploying into the same schema would collide with yours.

1. Open a notebook, connect it to **Serverless**, and open its **Terminal**.
2. From your Git folder, run:

   ```bash
   cd dabs-workshop
   WORKSPACE_URL=https://<your-workspace-url> bash instructor/build_dev_assets.sh <catalog> <your_schema>
   ```

   For example, `bash instructor/build_dev_assets.sh dev-training jane_doe`. Add a third argument
   if the shared data isn't in `analyst101_shared`, and set `WAREHOUSE_NAME=…` if the workspace's
   serverless warehouse isn't called **Serverless Starter Warehouse**.

The script:

1. Puts the pipeline SQL in `/Users/<you>/encounters_pipeline/transformations/`, creates the
   `encounters_pipeline` pipeline (serverless, writing to your schema), and runs it once so
   `gold_encounters` exists.
2. Creates the dashboard, Genie agent, and job in your home folder.
3. Prints a link to each asset.

Open each link to check it: the pipeline graph (`silver_encounters` → `gold_encounters`, 80K rows),
the dashboard, a question to the Genie agent, and the paused job.

## 3. Share and grant access

Send students the four links. Grant the students' group:

- **Can view** on the pipeline, the dashboard, the Genie agent, and the job
- **Can read** on `/Users/<you>/encounters_pipeline` (`bundle generate` downloads the SQL from there)
- Read access to the shared data:

  ```sql
  GRANT USE CATALOG ON CATALOG `<catalog>` TO `<students_group>`;
  GRANT USE SCHEMA, SELECT ON SCHEMA `<catalog>`.analyst101_shared TO `<students_group>`;
  ```

Each student also needs their own schema in the catalog (ownership, or `USE SCHEMA`, `CREATE TABLE`,
and `CREATE MATERIALIZED VIEW`), serverless notebooks, serverless pipelines, Genie, and **Can use**
on the serverless warehouse.

## Building the assets by hand instead

If you'd rather show how the assets were made, build them in the UI with these names, so the files
students generate match the guide:

| Asset | Name | How |
|---|---|---|
| Pipeline | `encounters_pipeline` | **Jobs & Pipelines → Create → ETL pipeline**, serverless, default catalog and schema = yours. Add the two SQL files from `pipeline/` (replace `<catalog>` and `<source_schema>`), then run it. |
| Dashboard | `Encounters & Outcomes` | **Dashboards → Create → Import dashboard from file**, using `encounters_outcomes.lvdash.json` with `<catalog>` and `<schema>` replaced. Keep it to **one dataset** that names the full table; the student guide edits that one query. |
| Genie agent | `Encounters & Outcomes Genie` | **Genie → New**, add your `gold_encounters`, then paste the instructions, example SQL, and sample questions from `encounters_outcomes_genie.json`. |
| Job | `encounters_refresh` | **Jobs & Pipelines → Create → Job**, one **Pipeline** task on `encounters_pipeline`, a daily schedule, then **Pause**. |

### Optional: build them live with Genie Code

To demo the "built in dev" story, Genie Code can write the pipeline SQL. In the new pipeline's
editor, ask:

> Create a materialized view `silver_encounters` that selects all columns from
> `<catalog>`.`<source_schema>`.fact_encounters, with three expectations: `encounter_id` is not null
> (drop the row), `discharge_date >= admit_date` (drop the row), and `total_charges >= 0` (warn only).

> Create a materialized view `gold_encounters` from `silver_encounters`, joined to
> `<catalog>`.`<source_schema>`.dim_provider on `provider_id`, `dim_facility` on `facility_id`, and
> `dim_diagnosis` on `primary_icd10_code = icd10_code`. Include `encounter_id`, `admit_date`,
> `encounter_type`, `payer_type`, `length_of_stay_days`, `total_charges`, `total_paid`,
> `readmitted_30d`, `mortality_flag`, `complication_flag`; `readmit_pct`, `mortality_pct`, and
> `complication_pct` as each flag × 100.0; and `provider_name`, `specialty`, `facility_name`,
> `region`, `facility_type`, `clinical_category`.

Compare the result with `pipeline/*.sql` and use those files if it differs; students' dashboards and
Genie agents depend on these exact column names. For the dashboard, import the file rather than
generating it, so it keeps the single dataset the guide expects.
