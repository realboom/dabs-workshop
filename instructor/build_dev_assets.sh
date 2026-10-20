#!/usr/bin/env bash
# Build the four "dev" assets that students import into their bundles.
#
# Creates them the way a developer would have built them in the UI, including the dev
# hard-coding the lab teaches students to remove: the catalog written into the SQL, the
# pipeline writing to your schema, the dashboard and Genie agent reading your table, and
# the job paused.
#
# Run it from a serverless notebook's web terminal, from your Git folder of this repo:
#
#   bash instructor/build_dev_assets.sh <catalog> <your_schema> [source_schema]
#
#   <catalog>        workshop catalog, for example dev-training
#   <your_schema>    your own schema, not one a student will use
#   [source_schema]  schema with the shared encounters data (default: analyst101_shared)
#
# Optional environment variables:
#   WAREHOUSE_NAME   SQL warehouse for the dashboard and Genie agent (default: Serverless Starter Warehouse)
#   WORKSPACE_URL    printed in front of the links at the end, for example https://adb-123.4.azuredatabricks.net
set -euo pipefail

CATALOG="${1:?usage: build_dev_assets.sh <catalog> <your_schema> [source_schema]}"
SCHEMA="${2:?usage: build_dev_assets.sh <catalog> <your_schema> [source_schema]}"
SOURCE_SCHEMA="${3:-analyst101_shared}"
WAREHOUSE_NAME="${WAREHOUSE_NAME:-Serverless Starter Warehouse}"
URL="${WORKSPACE_URL:-<workspace-url>}"

HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
ME="$(databricks current-user me -o json | jq -r .userName)"
HOME_PATH="/Users/$ME"

fill() {
  sed -e "s|<catalog>|$CATALOG|g" -e "s|<schema>|$SCHEMA|g" -e "s|<source_schema>|$SOURCE_SCHEMA|g" "$1"
}

WAREHOUSE_ID="$(databricks warehouses list -o json | jq -r --arg n "$WAREHOUSE_NAME" '[.[] | select(.name == $n)][0].id // empty')"
[ -n "$WAREHOUSE_ID" ] || { echo "No SQL warehouse named '$WAREHOUSE_NAME'. Set WAREHOUSE_NAME and re-run."; exit 1; }

echo "==> Building dev assets in $CATALOG.$SCHEMA (source: $CATALOG.$SOURCE_SCHEMA) as $ME"

# 1. Pipeline: SQL files in your home folder, writing to your schema.
PIPE_DIR="$HOME_PATH/encounters_pipeline"
databricks workspace mkdirs "$PIPE_DIR/transformations"
for f in silver_encounters gold_encounters; do
  fill "$HERE/pipeline/$f.sql" > "$TMP/$f.sql"
  databricks workspace import "$PIPE_DIR/transformations/$f.sql" --file "$TMP/$f.sql" --format RAW --overwrite
done
jq -n --arg c "$CATALOG" --arg s "$SCHEMA" --arg d "$PIPE_DIR" \
  '{name: "encounters_pipeline", catalog: $c, schema: $s, serverless: true, root_path: $d,
    libraries: [{glob: {include: ($d + "/transformations/**")}}]}' > "$TMP/pipeline.json"
PIPELINE_ID="$(databricks pipelines create --json @"$TMP/pipeline.json" -o json | jq -r .pipeline_id)"
echo "    pipeline  $PIPELINE_ID — running it once so gold_encounters exists..."
UPDATE_ID="$(databricks pipelines start-update "$PIPELINE_ID" -o json | jq -r .update_id)"
while :; do
  STATE="$(databricks pipelines get-update "$PIPELINE_ID" "$UPDATE_ID" -o json | jq -r .update.state)"
  case "$STATE" in COMPLETED) break ;; FAILED|CANCELED) echo "Pipeline update $STATE. Open the pipeline to see why."; exit 1 ;; esac
  sleep 10
done

# 2. Dashboard: one dataset on your gold_encounters.
fill "$HERE/encounters_outcomes.lvdash.json" > "$TMP/dashboard.lvdash.json"
jq -n --rawfile d "$TMP/dashboard.lvdash.json" --arg w "$WAREHOUSE_ID" --arg p "$HOME_PATH" \
  '{display_name: "Encounters & Outcomes", warehouse_id: $w, parent_path: $p, serialized_dashboard: $d}' > "$TMP/dashboard.json"
DASHBOARD_ID="$(databricks lakeview create --json @"$TMP/dashboard.json" -o json | jq -r .dashboard_id)"
echo "    dashboard $DASHBOARD_ID"

# 3. Genie agent on your gold_encounters.
fill "$HERE/encounters_outcomes_genie.json" > "$TMP/space.json"
jq -n --rawfile s "$TMP/space.json" --arg w "$WAREHOUSE_ID" --arg p "$HOME_PATH" \
  '{title: "Encounters & Outcomes Genie", description: "Ask questions about encounters, readmissions, and charges.",
    warehouse_id: $w, parent_path: $p, serialized_space: $s}' > "$TMP/genie.json"
GENIE_ID="$(databricks genie create-space --json @"$TMP/genie.json" -o json | jq -r .space_id)"
echo "    genie     $GENIE_ID"

# 4. Job: refreshes the pipeline daily, paused.
sed "s|<pipeline_id>|$PIPELINE_ID|" "$HERE/encounters_refresh.job.json" > "$TMP/job.json"
JOB_ID="$(databricks jobs create --json @"$TMP/job.json" -o json | jq -r .job_id)"
echo "    job       $JOB_ID"

cat <<EOF

==> Done. Share these links with students (and grant them Can view on each):
  Pipeline     $URL/pipelines/$PIPELINE_ID
  Dashboard    $URL/dashboardsv3/$DASHBOARD_ID
  Genie agent  $URL/genie/rooms/$GENIE_ID
  Job          $URL/jobs/$JOB_ID
Pipeline source folder (grant Can read): $PIPE_DIR
EOF
