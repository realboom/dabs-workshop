# DABs Workshop — Declarative Automation Bundles, hands-on

A one-hour, hands-on lab for **Declarative Automation Bundles (DABs)**, run entirely from the
**web terminal** of a serverless notebook. No laptop setup and no local CLI. Everything runs on
**serverless**.

Each student starts from `databricks bundle init`, then adds one resource at a time to their bundle and
deploys it:

1. A **Lakeflow pipeline** (SQL) that builds `silver_encounters` → `gold_encounters` in their schema
2. An **AI/BI dashboard** on `gold_encounters`
3. A **Genie agent** on `gold_encounters`
4. A **job** that refreshes the pipeline

Development mode gives every student their own copy of each resource (`[dev <name>] …`), and the
`catalog` / `schema` variables send each student's tables to their own schema.

The data is the synthetic **encounters star schema** from
[analyst101-workshop](https://github.com/realboom/analyst101-workshop). It contains no PHI. Use the
`adult` or `pediatric` profile to match the audience.

## What's in here

```
dabs-workshop/
├── README.md
├── setup/
│   ├── generate_workshop_data.py   · instructor: builds the shared star schema (run once)
│   └── profiles/                   · adult / pediatric data profiles used by the generator
├── lab/
│   ├── GUIDE.md                    · the student guide
│   ├── 1_pipeline/                 · files students copy into their bundle, one folder per step
│   ├── 2_dashboard/
│   ├── 3_genie/
│   └── 4_job/
└── solution/dabs_workshop/         · the finished bundle (bundle init + all four steps)
```

## Instructor setup (once per workspace)

1. Add this repo to the workspace as a **Git folder**.
2. Open `setup/generate_workshop_data.py` on serverless and run it with widgets
   `catalog` = the workshop catalog, `schema` = `analyst101_shared`, `profile` = `adult` or `pediatric`.
   It builds `fact_encounters` (80,000 rows) and the `dim_*` tables.
3. Make sure each student has their own schema in the workshop catalog, and grant read access to the
   shared data:
   ```sql
   GRANT USE CATALOG ON CATALOG `<workshop_catalog>` TO `<students_group>`;
   GRANT USE SCHEMA, SELECT ON SCHEMA `<workshop_catalog>`.analyst101_shared TO `<students_group>`;
   ```
4. Students need serverless notebooks (for the web terminal), serverless pipelines, and **Can use** on
   the **Serverless Starter Warehouse** (the bundle looks it up by that name).

Catalog names with hyphens (for example `dev-training`) work: the pipeline SQL quotes them, and Genie
quotes them in the SQL it generates.

## Notes and gotchas (all found in testing)

- **Host.** In the web terminal, `bundle init` writes `host: http://127.0.0.1:7073` (the terminal's
  local proxy). Students replace it with the workspace URL so the same bundle also works from a laptop
  or CI/CD.
- **Genie needs its table first.** A Genie agent can't be created until `gold_encounters` exists, so
  run the pipeline (Part 1) before deploying the Genie agent (Part 3). Deploying `solution/` in one go
  needs `deploy` → `bundle run encounters_pipeline` → `deploy`.
- **One owner per table.** A table can belong to only one pipeline. If you build the UI version of
  the pipeline yourself, build it in a different schema from the one you use to walk the lab.
- **One bundle per user.** Bundle state is per user, bundle name, and target, and pipeline names
  must be unique in a workspace. Two copies of this bundle deployed as the same user collide.
- **Refreshing the lab files.** If you change the pipeline, dashboard, or Genie agent in the UI, re-export
  with `databricks bundle generate pipeline | dashboard | genie-space --existing-id <id>`, then put the
  workspace-specific values back as variables (catalog, schema, warehouse) before copying them into `lab/`.
