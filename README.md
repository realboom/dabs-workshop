# DABs Workshop — Productionize what you built in dev with Declarative Automation Bundles

A one-hour, hands-on lab for **Declarative Automation Bundles (DABs)**, run entirely from the
**web terminal** of a serverless notebook. No laptop setup and no local CLI. Everything runs on
**serverless**.

The story: a pipeline, an AI/BI dashboard, a Genie agent, and a job were built in the **dev**
workspace through the UI. Each student takes them into a bundle so CI/CD can promote them:

1. **Import** the four assets with `databricks bundle generate`
2. **Remove the dev hard-coding**: variables for catalog and schema, a warehouse lookup, the job's
   pipeline reference, and the Genie agent's table
3. **Define production** and compare `validate -t dev` with `validate -t prod`, without deploying to prod
4. **Deploy their own dev copy**, run it, and check it
5. **See how CI/CD promotes it** (`cicd/deploy-prod.yml`)

The data is the synthetic **encounters star schema** from
[analyst101-workshop](https://github.com/realboom/analyst101-workshop). It contains no PHI. Use the
`adult` or `pediatric` profile to match the audience.

## What's in here

```
dabs-workshop/
├── README.md
├── lab/GUIDE.md                    · the student guide
├── setup/
│   ├── generate_workshop_data.py   · instructor: builds the shared star schema (run once)
│   └── profiles/                   · adult / pediatric data profiles used by the generator
├── tools/inline_genie.py           · students run it in Part 2 to make the Genie agent's table a variable
├── cicd/deploy-prod.yml            · example GitHub Actions workflow for Part 5
└── solution/encounters_bundle/     · the finished bundle (after Parts 0–3)
```

## Instructor setup (once per workspace)

1. **Shared data.** Add this repo as a **Git folder**, open `setup/generate_workshop_data.py` on
   serverless, and run it with widgets `catalog` = the workshop catalog, `schema` = `analyst101_shared`,
   `profile` = `adult` or `pediatric`. It builds `fact_encounters` (80,000 rows) and the `dim_*` tables.
2. **The four dev assets.** Build them in the UI in **your own schema** (not one a student will use),
   with exactly these names so the guide's file names match:

   | Asset | Name | What it does |
   |---|---|---|
   | ETL pipeline (serverless, SQL) | `encounters_pipeline` | `silver_encounters` (3 expectations) → `gold_encounters`, reading `analyst101_shared` |
   | AI/BI dashboard | `Encounters & Outcomes` | One dataset, `SELECT * FROM <catalog>.<your_schema>.gold_encounters` |
   | Genie agent | `Encounters & Outcomes Genie` | On `gold_encounters`, with instructions and sample questions |
   | Job | `encounters_refresh` | One pipeline task that refreshes `encounters_pipeline`, daily (paused) |

   The SQL and the dashboard layout are in `solution/encounters_bundle/src/` if you want to start from them.
3. **Share and grant.** Give students the link to each asset, and grant the students' group:
   - **Can view** on the pipeline, dashboard, Genie agent, and job
   - **Can read** on the pipeline's source folder in your home folder (`generate` downloads the SQL from it)
   - Read access to the shared data:
     ```sql
     GRANT USE CATALOG ON CATALOG `<workshop_catalog>` TO `<students_group>`;
     GRANT USE SCHEMA, SELECT ON SCHEMA `<workshop_catalog>`.analyst101_shared TO `<students_group>`;
     ```
4. **Each student** needs their own schema in the workshop catalog (ownership, or `USE SCHEMA`,
   `CREATE TABLE`, and `CREATE MATERIALIZED VIEW`), serverless notebooks (for the web terminal),
   serverless pipelines, Genie, and **Can use** on the **Serverless Starter Warehouse** (the bundle
   looks it up by that name).

Catalog names with hyphens (for example `dev-training`) work: the pipeline SQL quotes them, and Genie
quotes them in the SQL it generates.

## Notes and gotchas (all found in testing)

- **Host.** In the web terminal, `bundle init` writes `host: http://127.0.0.1:7073` (the terminal's
  local proxy). Students replace it with the workspace URL so the same bundle also works from a laptop
  or CI/CD.
- **One owner per table.** A table can belong to only one pipeline. If you build the UI version of
  the pipeline yourself, build it in a different schema from the one you use to walk the lab.
- **One bundle per user.** Bundle state is per user, bundle name, and target, and pipeline names
  must be unique in a workspace. Two copies of this bundle deployed as the same user collide.
- **Genie needs its table first.** A Genie agent can't be created until `gold_encounters` exists, so a
  student's first `deploy` fails on the agent. Running the job (which runs the pipeline) and deploying
  again fixes it. CI/CD has the same first-deploy ordering in a new environment.
- **Generated dev values.** `generate` copies everything, including the dev schema, the warehouse ID,
  the job's `pause_status: PAUSED`, and the Genie agent's `parent_path` (the builder's home folder).
  Part 2 removes each of them.
- **Destroy can leave tables.** `bundle destroy` deletes the pipeline but can leave its tables in the
  schema, still marked as owned by the deleted pipeline. Drop them before deploying into that schema again.
