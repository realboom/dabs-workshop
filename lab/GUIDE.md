# DABs Hands-On Lab — Deploy a Pipeline, Dashboard, and Genie Agent with Declarative Automation Bundles

**Time:** about 1 hour  ·  **Compute:** serverless only  ·  **Data:** synthetic hospital encounters (no PHI)

In this lab you build a Declarative Automation Bundle (DAB) one piece at a time. By the end, a single
folder of files deploys four things to your workspace:

1. A **Lakeflow pipeline** that builds `silver_encounters` and `gold_encounters` in your schema
2. An **AI/BI dashboard** on `gold_encounters`
3. A **Genie agent** that answers questions about `gold_encounters`
4. A **job** that refreshes the pipeline every day

Everything runs from a **web terminal** inside the workspace. You don't need anything installed on your laptop.

## Before you start

You need:

- **Your catalog and schema.** Your instructor will give you these: the workshop catalog, and a
  schema named after you, such as `jane_doe`.
- **The shared data.** `<your_catalog>.analyst101_shared` holds the encounters tables
  (`fact_encounters`, `dim_provider`, `dim_facility`, `dim_diagnosis`, …). You read from it; you never
  write to it.
- **This repo in your workspace.** In the workspace sidebar, open your home folder, select
  **Create → Git folder**, and paste `https://github.com/realboom/dabs-workshop`. It appears as
  `dabs-workshop` in your home folder.

Throughout the lab you'll use two browser tabs:

- **Tab 1 — Terminal.** For `databricks` commands.
- **Tab 2 — Workspace file browser.** For opening and editing files in your bundle.

---

## Part 0 — Start a bundle (10 min)

### 0.1 Open the web terminal

1. Create a new notebook (any language) and connect it to **Serverless**.
2. Open the notebook's **Terminal**.
3. The terminal opens in your home folder, `/Workspace/Users/<you>`. Check that the Databricks CLI is
   already signed in as you:

   ```bash
   databricks current-user me
   ```

   The first time you run a `databricks` command, the terminal installs the CLI for you. You should
   see your user name and email in the output. There is no login step.

### 0.2 Create the bundle from a template

```bash
databricks bundle init default-python
```

Answer the prompts like this:

| Prompt | Answer |
|---|---|
| Unique name for this project | `encounters_bundle` |
| Include a job that runs a notebook | `no` |
| Include an ETL pipeline | `no` |
| Include a sample Python package that builds into a wheel file | `no` |
| Use serverless compute | `yes` |
| Default catalog for any tables created by this project | your workshop catalog, for example `dev-training` |

Accept the default for any other prompt. You now have an empty bundle in
`/Workspace/Users/<you>/encounters_bundle`. Move into it:

```bash
cd encounters_bundle
ls
```

`databricks.yml` is the one required file in every bundle. It names the bundle, declares variables,
and defines **targets** (the environments you deploy to). `resources/` will hold one YAML file per
thing you deploy, and `src/` will hold their code.

### 0.3 Edit `databricks.yml`

In **Tab 2**, open `encounters_bundle/databricks.yml` and make these changes.

1. **Host.** The template wrote `host: http://127.0.0.1:7073`. That's the terminal's private address and
   only works inside this terminal. Replace it on **both** `host:` lines with your workspace URL. Copy
   it from your browser's address bar, up to and including `.azuredatabricks.net`:

   ```yaml
   host: https://adb-1234567890123456.7.azuredatabricks.net
   ```

2. **Catalog and schema.** Under `targets: → dev: → variables:`, `catalog` already shows the catalog
   you typed during `bundle init`. Check it, then set `schema` to your own schema. The template's
   default, `${workspace.current_user.short_name}`, is your user name, which may not match your schema:

   ```yaml
       variables:
         catalog: <your_catalog>      # already filled in from bundle init
         schema: <your_schema>        # for example: jane_doe
   ```

3. Save the file.

Back in **Tab 1**, check your work:

```bash
databricks bundle validate
```

You should see `Validation OK!`. Validation checks your YAML, fills in your variables, and confirms
it can reach your workspace. It doesn't deploy anything.

> **What `mode: development` does.** The `dev` target uses development mode. Everything you deploy is
> renamed with a `[dev <your_name>]` prefix and lives in your own `.bundle` folder, so 20 people can
> deploy the same bundle without stepping on each other. Schedules are paused. Your **data** goes
> where your `catalog` and `schema` variables point.

---

## Part 1 — Add the pipeline (15 min)

### 1.1 Copy in the pipeline files

Your instructor built the pipeline once in the workspace UI and exported it with
`databricks bundle generate pipeline`. You'll add that exported definition to your bundle:

```bash
cp -r ../dabs-workshop/lab/1_pipeline/. .
```

That adds four files:

| File | What it is |
|---|---|
| `resources/encounters_pipeline.pipeline.yml` | The pipeline definition |
| `resources/variables.yml` | Two new variables: where the shared data lives |
| `src/transformations/silver_encounters.sql` | Silver table, with data quality expectations |
| `src/transformations/gold_encounters.sql` | Gold table, joined to provider, facility, and diagnosis |

### 1.2 Read the pipeline definition

Open `resources/encounters_pipeline.pipeline.yml` in **Tab 2**:

```yaml
resources:
  pipelines:
    encounters_pipeline:
      name: encounters_pipeline
      catalog: ${var.catalog}
      schema: ${var.schema}
      serverless: true
      root_path: ../src
      libraries:
        - glob:
            include: ../src/transformations/**
      configuration:
        source_catalog: ${var.source_catalog}
        source_schema: ${var.source_schema}
```

- `encounters_pipeline` (under `pipelines:`) is the **resource key**. Commands like `bundle run` use it.
- `${var.catalog}` and `${var.schema}` are **variables**. The pipeline writes its tables to the catalog
  and schema you set in Part 0.
- `configuration` passes values into the SQL. Open `src/transformations/silver_encounters.sql` and
  find `${source_catalog}` and `${source_schema}`. Neither file contains a hard-coded catalog name.
- Open `resources/variables.yml`. `source_catalog` defaults to `${var.catalog}`: one variable built from
  another.

### 1.3 Deploy and run

```bash
databricks bundle validate
databricks bundle deploy
databricks bundle run encounters_pipeline
```

`deploy` creates the pipeline. `run` starts it and streams its progress. Wait for
`Update … is COMPLETED` (about a minute on serverless).

### 1.4 Check the results

In the workspace sidebar, open **Jobs & Pipelines** and find **`[dev <your_name>] encounters_pipeline`**.
Look at the pipeline graph: `silver_encounters` → `gold_encounters`. Then open **Catalog**, browse to
your schema, and confirm both tables are there. `gold_encounters` has about 80,000 rows.

---

## Part 2 — Add the dashboard (10 min)

### 2.1 Add a lookup variable for the warehouse

A dashboard needs a SQL warehouse. Warehouse IDs are long and differ between workspaces, so instead of
typing one, you'll **look it up by name**. Add this to the end of `resources/variables.yml`, indented to
line up with `source_schema:`:

```yaml
  warehouse_id:
    description: SQL warehouse for the dashboard and the Genie agent
    lookup:
      warehouse: Serverless Starter Warehouse
```

When you deploy, the bundle finds the warehouse with that name and uses its ID.

### 2.2 Copy in the dashboard files

```bash
cp -r ../dabs-workshop/lab/2_dashboard/. .
```

Open `resources/encounters_outcomes.dashboard.yml`:

```yaml
resources:
  dashboards:
    encounters_outcomes:
      display_name: "Encounters & Outcomes"
      file_path: ../src/encounters_outcomes.lvdash.json
      warehouse_id: ${var.warehouse_id}
      dataset_catalog: ${var.catalog}
      dataset_schema: ${var.schema}
```

The dashboard itself is `src/encounters_outcomes.lvdash.json`, the file the dashboard editor saves.
Its query is just `SELECT * FROM gold_encounters`, with no catalog or schema. `dataset_catalog` and
`dataset_schema` fill those in, so your copy of the dashboard reads **your** `gold_encounters`.

### 2.3 Deploy

```bash
databricks bundle deploy
```

The output ends with `Resources: 1 created, 0 changed, 0 deleted, 1 unchanged`. The bundle compares
what's in your files with what's already deployed, so the pipeline from Part 1 is unchanged.

Open **Dashboards** and find **`[dev <your_name>] Encounters & Outcomes`**. Try the filters.

---

## Part 3 — Add the Genie agent (10 min)

### 3.1 Copy in the Genie agent

```bash
cp -r ../dabs-workshop/lab/3_genie/. .
```

Open `resources/encounters_outcomes_genie.genie_space.yml`. Under `serialized_space` is the agent's
full definition, exactly as the Genie API exports it:

- `data_sources.tables` — the table the agent uses:
  `${var.catalog}.${var.schema}.gold_encounters`, which is your table
- `instructions.text_instructions` — how to calculate rates and format results
- `instructions.example_question_sqls` — a question paired with the SQL that answers it
- `config.sample_questions` — the questions shown when you open the agent

### 3.2 Deploy

```bash
databricks bundle deploy
```

> If you see `Table '…gold_encounters' does not exist`, the pipeline hasn't run yet. A Genie agent can
> only be created on a table that exists. Run `databricks bundle run encounters_pipeline`, then deploy
> again.

Open **Genie** and find **`[dev <your_name>] Encounters & Outcomes Genie`**. Ask:

- *Which facilities have the highest 30-day readmission rate?*
- *Which specialties have the most complications?*

Open **Show code** on an answer and compare it with the instructions in your YAML. For example, it
should only rank facilities with at least 200 encounters.

---

## Part 4 — Add a job (10 min)

### 4.1 Copy in the job

```bash
cp -r ../dabs-workshop/lab/4_job/. .
```

Open `resources/encounters_refresh.job.yml`:

```yaml
resources:
  jobs:
    encounters_refresh:
      name: encounters_refresh
      trigger:
        periodic:
          interval: 1
          unit: DAYS
      tasks:
        - task_key: refresh_pipeline
          pipeline_task:
            pipeline_id: ${resources.pipelines.encounters_pipeline.id}
```

`${resources.pipelines.encounters_pipeline.id}` is a **resource reference**. The job doesn't hard-code
the pipeline's ID; the bundle fills in the ID of the pipeline it deployed for you. The job only has a
pipeline task, so it runs on serverless with no cluster to configure.

### 4.2 Deploy and run

```bash
databricks bundle deploy
databricks bundle run encounters_refresh
```

Wait for `TERMINATED SUCCESS`. Open **Jobs & Pipelines** and find
**`[dev <your_name>] encounters_refresh`**. The daily schedule shows as **paused**, because
development mode pauses schedules.

### 4.3 See everything the bundle owns

```bash
databricks bundle summary
```

This lists your four resources with their links. That one folder now describes and deploys the
whole project.

---

## Wrap-up

You used the main bundle features:

| Feature | Where you used it |
|---|---|
| Template (`bundle init`) | Part 0 |
| Targets and development mode | `targets: dev: mode: development` |
| Custom variables and per-target values | `catalog`, `schema` in `databricks.yml` |
| Variables built from other variables | `source_catalog: ${var.catalog}` |
| Lookup variables | `warehouse_id` → `Serverless Starter Warehouse` |
| Resource references | `${resources.pipelines.encounters_pipeline.id}` |
| `validate` → `deploy` → `run` | Every part |

The finished bundle is in `dabs-workshop/solution/encounters_bundle` if you want to compare.

**Cleaning up (optional).** `databricks bundle destroy` deletes everything the bundle deployed,
**including the pipeline's tables** in your schema. Only run it if you're done with them.
