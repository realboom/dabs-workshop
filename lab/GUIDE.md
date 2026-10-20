# DABs Hands-On Lab — Productionize What You Built in Dev with Declarative Automation Bundles

**Time:** about 1 hour  ·  **Compute:** serverless only  ·  **Data:** synthetic hospital encounters (no PHI)

A data team has built four assets in the **dev** workspace using the UI:

1. A **Lakeflow pipeline** that builds `silver_encounters` and `gold_encounters`
2. An **AI/BI dashboard** on `gold_encounters`
3. A **Genie agent** that answers questions about `gold_encounters`
4. A **job** that refreshes the pipeline every day

They work, but they only exist in dev, and nothing describes them in source control. In this lab
you take those assets and put them into a **Declarative Automation Bundle (DAB)**, the form a CI/CD
pipeline can promote to production:

- **Import** each asset into a bundle with `databricks bundle generate`
- **Remove the dev hard-coding** so the same files work in any environment
- **Define production** and check exactly what a production deployment would create
- **Deploy your own dev copy** to prove the bundle works

You won't deploy to production yourself. That's the job of CI/CD, which the last part walks through.

Everything runs from a **web terminal** inside the workspace. You don't need anything installed on
your laptop.

## Before you start

You need:

- **Your dev catalog and schema.** Your instructor will give you these: the workshop catalog and a
  schema named after you, such as `jane_doe`.
- **The shared data.** `<your_catalog>.analyst101_shared` holds the encounters tables
  (`fact_encounters`, `dim_provider`, `dim_facility`, `dim_diagnosis`, …). You read from it; you never
  write to it.
- **Links to the four dev assets.** Your instructor will share a link to each one: the pipeline, the
  dashboard, the Genie agent, and the job.
- **This repo in your workspace.** In the workspace sidebar, open your home folder, select
  **Workspace → Create → Git folder**, and paste `https://github.com/realboom/dabs-workshop`. It appears as
  `dabs-workshop` in your home folder. You'll use one helper script from it, and it holds the finished
  bundle if you want to compare.

Throughout the lab, you'll use two browser tabs:

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
| Use a personal schema for each user working on this project | `no, I will customize the schema configuration later in databricks.yml` |

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

2. **Catalog and schema.** Under `targets: → dev: → variables:`, `catalog` is the catalog you typed
   during `bundle init`. `schema` is a placeholder, `dev`. Replace it with the name of your schema:

   ```yaml
       variables:
         catalog: <your_catalog>      # the catalog you typed
         schema: <your_schema>        # was: dev
   ```

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

## Part 1 — Import what was built in dev (15 min)

`databricks bundle generate` reads an asset that already exists in the workspace and writes its
definition into your bundle as YAML, plus any files it uses (SQL, dashboard layout, Genie
definition). Nothing in the workspace changes.

### 1.1 Get the four asset IDs

Open each link your instructor shared. The asset's ID is in the address bar:

| Asset | The address looks like | The ID is |
|---|---|---|
| Pipeline | `…/pipelines/09665761-efcc-4a8b-…` | the value after `/pipelines/` |
| Dashboard | `…/dashboardsv3/01f1cc35b86c15e2…/published` | the value after `/dashboardsv3/` |
| Genie agent | `…/genie/rooms/01f1cc35b00e1cb8…` | the value after `/rooms/` |
| Job | `…/jobs/551104569476387` | the number after `/jobs/` |

Ignore anything after `?` in the address.

### 1.2 Generate the bundle definitions

In **Tab 1**, from your `encounters_bundle` folder, run one command per asset with its ID:

```bash
databricks bundle generate pipeline --existing-pipeline-id <pipeline_id>
databricks bundle generate dashboard --existing-id <dashboard_id>
databricks bundle generate genie-space --existing-id <genie_agent_id>
databricks bundle generate job --existing-job-id <job_id>
```

Your bundle now has:

| File | What it is |
|---|---|
| `resources/encounters_pipeline.pipeline.yml` | The pipeline definition |
| `src/transformations/silver_encounters.sql`, `gold_encounters.sql` | The pipeline's SQL, downloaded from the original |
| `resources/encounters_outcomes.dashboard.yml` | The dashboard definition |
| `src/encounters_outcomes.lvdash.json` | The dashboard's layout and queries |
| `resources/encounters_outcomes_genie.genie_space.yml` | The Genie agent definition |
| `src/encounters_outcomes_genie.geniespace.json` | The agent's tables, instructions, and example questions |
| `resources/encounters_refresh.job.yml` | The job definition |

The name in front of each `.yml` (for example `encounters_pipeline`) is the **resource key**.
Commands such as `bundle run` use it.

### 1.3 Look at what you got

Open `resources/encounters_pipeline.pipeline.yml` in **Tab 2**:

```yaml
resources:
  pipelines:
    encounters_pipeline:
      name: encounters_pipeline
      libraries:
        - glob:
            include: ../src/transformations/**
      catalog: dev-training
      root_path: ../src
      schema: instructor_demo
      serverless: true
```

This is a faithful copy of the dev pipeline, **including where it writes**: `catalog` and `schema`
are hard-coded to the schema it was built in. Deploy it as-is and your copy would write into that
same schema, and so would production. Part 2 fixes that.

> **`generate` copies; `bind` adopts.** Deploying a generated definition creates a **new** asset
> owned by your bundle; the original is left alone. That's what you want here. If you were bringing
> **your own** asset under a bundle, you'd follow `generate` with
> `databricks bundle deployment bind <resource_key> <id>`, so the bundle takes over the original
> instead of creating a second one. Don't bind to a shared asset: every student's bundle would then
> try to control the same one.

---

## Part 2 — Remove the dev hard-coding (15 min)

Every value that ties an asset to the dev environment becomes a **variable** (set per target) or a
**reference** (resolved by the bundle). Here's the whole list; the steps below walk through each one.

| File | Hard-coded dev value | Change it to |
|---|---|---|
| `resources/variables.yml` (new) | — | one place that declares every variable |
| `encounters_pipeline.pipeline.yml` | `catalog:` and `schema:` | `${var.catalog}` and `${var.schema}` |
| `silver_encounters.sql`, `gold_encounters.sql` | the dev source catalog and schema | `${source_catalog}` and `${source_schema}` |
| `encounters_outcomes.dashboard.yml` | `warehouse_id:` | `${var.warehouse_id}`, plus `dataset_catalog` / `dataset_schema` |
| `encounters_outcomes.lvdash.json` | the full table name in the query | the bare table name, `gold_encounters` |
| `encounters_outcomes_genie.genie_space.yml` | `warehouse_id:`, `parent_path:`, and the table inside the JSON | `${var.warehouse_id}`, no `parent_path`, and a table built from variables |
| `encounters_refresh.job.yml` | `pipeline_id:` and `pause_status: PAUSED` | a reference to your pipeline, and no `pause_status` |

### 2.1 Declare your variables in one file

Create a new file, `resources/variables.yml`. Every `.yml` file in `resources/` is included in the
bundle automatically.

```yaml
# Variable declarations. Each target in databricks.yml sets their values.
variables:
  catalog:
    description: Catalog the pipeline writes to
  schema:
    description: Schema the pipeline writes to
  source_catalog:
    description: Catalog that holds the source data the pipeline reads
  source_schema:
    description: Schema that holds the source data the pipeline reads
  warehouse_id:
    description: SQL warehouse for the dashboard and the Genie agent
    lookup:
      warehouse: Serverless Starter Warehouse
```

`warehouse_id` is a **lookup** variable. Warehouse IDs are long and differ between workspaces, so
the bundle finds the warehouse by name when you deploy.

Then open `databricks.yml`:

1. Delete the template's top-level `variables:` block (the `catalog:` and `schema:` declarations). They
   now live in `variables.yml`, and a variable can only be declared once.
2. Under `targets: → dev: → variables:`, add the dev source values below `catalog` and `schema`:

   ```yaml
       variables:
         catalog: <your_catalog>
         schema: <your_schema>
         source_catalog: <your_catalog>
         source_schema: analyst101_shared
   ```

### 2.2 Pipeline: where it writes and what it reads

In `resources/encounters_pipeline.pipeline.yml`, change `catalog:` and `schema:`, and add a
`configuration:` block at the end, lined up with `serverless:`:

```yaml
      catalog: ${var.catalog}
      schema: ${var.schema}
      ...
      configuration:
        source_catalog: ${var.source_catalog}
        source_schema: ${var.source_schema}
```

`configuration` passes values into the pipeline's SQL. Now use them. Open
`src/transformations/silver_encounters.sql` and `gold_encounters.sql`. Each refers to the source data
with the dev catalog and schema written out, for example

```sql
FROM `<your_catalog>`.analyst101_shared.fact_encounters
```

Replace that prefix everywhere it appears (once in silver, three times in gold) with:

```sql
FROM `${source_catalog}`.`${source_schema}`.fact_encounters
```

This one matters most. With the dev catalog written into the SQL, a production deployment would
quietly keep reading dev data.

### 2.3 Dashboard

In `resources/encounters_outcomes.dashboard.yml`, replace the `warehouse_id:` line with these three:

```yaml
      warehouse_id: ${var.warehouse_id}
      dataset_catalog: ${var.catalog}
      dataset_schema: ${var.schema}
```

Then open `src/encounters_outcomes.lvdash.json`, find the query near the top (it ends with
`.gold_encounters"`), and change it to the bare table name:

```json
        "SELECT * FROM gold_encounters"
```

`dataset_catalog` and `dataset_schema` fill in the catalog and schema for any table name in the
dashboard that doesn't have them.

### 2.4 Genie agent

In `resources/encounters_outcomes_genie.genie_space.yml`:

1. Change `warehouse_id:` to `${var.warehouse_id}`.
2. Delete the `parent_path:` line. It points at the folder of whoever built the agent; without it,
   the bundle uses its own folder.

The agent's table is inside `src/encounters_outcomes_genie.geniespace.json`, and bundle variables
aren't substituted inside that file. So move the definition into the YAML, where they are. In
**Tab 1** run:

```bash
python ../dabs-workshop/tools/inline_genie.py
```

It copies the JSON into the YAML as `serialized_space`, replaces the table with
`${var.catalog}.${var.schema}.gold_encounters`, and removes the JSON file. Open the YAML again to see
the result.

### 2.5 Job

In `resources/encounters_refresh.job.yml`:

1. Change `pipeline_id: <the dev pipeline's ID>` to

   ```yaml
               pipeline_id: ${resources.pipelines.encounters_pipeline.id}
   ```

   That's a **resource reference**: the job refreshes whichever pipeline this bundle deployed to the
   same target. In dev that's your pipeline; in production, the production pipeline.
2. Delete the line `pause_status: PAUSED`. The dev job was paused, and `generate` copied that over.
   Left in, the production job would never run. Development mode pauses schedules in dev for you.

### 2.6 Validate

```bash
databricks bundle validate
```

Fix anything it reports, then search your `resources/` and `src/` files for the dev catalog and schema
names. Outside `databricks.yml`, they shouldn't appear anywhere.

---

## Part 3 — Define production (10 min)

### 3.1 Set the production values

`bundle init` already created a `prod` target in `databricks.yml`:

```yaml
  prod:
    mode: production
    workspace:
      host: https://<your-workspace-url>
      root_path: /Workspace/Users/<you>/.bundle/${bundle.name}/${bundle.target}
    variables:
      catalog: <your_catalog>
      schema: prod
      source_catalog: <your_catalog>
      source_schema: analyst101_shared
    permissions:
      - user_name: <you>
        level: CAN_MANAGE
```

Under `prod: → variables:`, set `catalog` and `schema` to the production values your instructor gives
you, and add `source_catalog` and `source_schema` for the production source data. For the workshop,
use the same source values as dev. In a
real project, `host` would usually be the **production workspace**, and `root_path`, `permissions`,
and a `run_as` service principal would be set for the CI/CD identity. You'll see those in Part 5.

`mode: production` tells the bundle this is a real deployment: no `[dev …]` name prefix, schedules
run, and it checks that the deployment is going somewhere deliberate.

### 3.2 Compare dev and production without deploying

`validate -t <target>` shows the fully resolved bundle for any target. Compare what each one would
create:

```bash
databricks bundle validate -t dev  -o json | jq '.resources.pipelines.encounters_pipeline | {name, catalog, schema}'
databricks bundle validate -t prod -o json | jq '.resources.pipelines.encounters_pipeline | {name, catalog, schema, configuration}'
databricks bundle validate -t prod -o json | jq '.resources.genie_spaces[].serialized_space | fromjson | .data_sources.tables[].identifier'
databricks bundle validate -t prod -o json | jq '.resources.jobs.encounters_refresh.trigger'
```

| | dev | prod |
|---|---|---|
| Pipeline name | `[dev <your_name>] encounters_pipeline` | `encounters_pipeline` |
| Writes to | your schema | the production schema |
| Genie agent reads | your `gold_encounters` | production `gold_encounters` |
| Job schedule | paused | runs daily |

Same files, different environment. That's the point of the bundle.

---

## Part 4 — Deploy your dev copy (10 min)

### 4.1 First deploy

```bash
databricks bundle deploy
```

The pipeline, dashboard, and job deploy. The Genie agent fails with
`Table '…gold_encounters' does not exist`. That's expected: a Genie agent can only be created on a
table that exists, and your pipeline hasn't run yet.

> **Source-linked deployment.** `deploy` also prints `Source-linked deployment is enabled` and
> `Files: 0 uploaded`. Because you're deploying from inside the workspace in development mode, the
> bundle doesn't copy your files anywhere; the pipeline runs the SQL in your `encounters_bundle/src`
> folder directly. So an edit to a `.sql` file is picked up the next time the pipeline runs, while
> changes to YAML files still need `databricks bundle deploy`. Don't move or delete the
> `encounters_bundle` folder while the pipeline is deployed. Deployments from a laptop, from CI/CD,
> or to a production target upload their own copy of the files instead.

### 4.2 Run the job

```bash
databricks bundle run encounters_refresh
```

The job runs your pipeline. Wait for `TERMINATED SUCCESS` (a minute or two on serverless).

### 4.3 Deploy again

```bash
databricks bundle deploy
```

This time the Genie agent is created, because `gold_encounters` now exists in your schema.

### 4.4 Check your copy

```bash
databricks bundle summary
```

This lists everything the bundle deployed, with links. Open each one:

- **Pipeline** — `silver_encounters` → `gold_encounters`, in your schema. In **Jobs & Pipelines**, if
  it isn't listed, check the filter at the top of the list: it may be set to **Jobs**. Switch it to
  **All**, or search for `encounters`.
- **Dashboard** — `[dev <your_name>] Encounters & Outcomes`, showing your data
- **Genie agent** — ask *Which facilities have the highest 30-day readmission rate?*
- **Job** — `[dev <your_name>] encounters_refresh`, with its schedule paused

The first deploy failing on the Genie agent is a real-world lesson too: when CI/CD deploys to a
brand-new environment for the first time, the pipeline has to run before the Genie agent can be
created.

---

## Part 5 — How it gets to production (5 min)

You've built a bundle that deploys correctly to dev and resolves correctly for production. Promoting
it is a CI/CD job, not something a developer runs from a terminal:

1. The bundle goes into a Git repository.
2. On every pull request, CI runs `databricks bundle validate -t prod`, so a broken bundle never
   merges.
3. When the change merges to `main`, CI runs `databricks bundle deploy -t prod` as a **service
   principal**, not as a person. The production target sets `run_as` to that service principal, so
   the pipeline and job run under it too.

`dabs-workshop/cicd/deploy-prod.yml` is an example GitHub Actions workflow that does steps 2 and 3.
Your instructor will walk through it.

---

## Wrap-up

| Bundle feature | Where you used it |
|---|---|
| Templates (`bundle init`) | Part 0 |
| Importing existing assets (`bundle generate`) | Part 1 |
| Variables declared in their own file, set per target | `resources/variables.yml` |
| Variables passed into pipeline SQL | `${source_catalog}`, `${source_schema}` |
| Lookup variables | `warehouse_id` → `Serverless Starter Warehouse` |
| Resource references | `${resources.pipelines.encounters_pipeline.id}` |
| Targets and deployment modes | `dev` (development) and `prod` (production) |
| `validate` → `deploy` → `run` | Parts 2–4 |

The finished bundle is in `dabs-workshop/solution/encounters_bundle` if you want to compare.

**Cleaning up (optional).** `databricks bundle destroy` deletes everything the bundle deployed to dev.
It can leave the pipeline's tables behind in your schema; if you deploy into the same schema again
later, drop `silver_encounters` and `gold_encounters` first.
