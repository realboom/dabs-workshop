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

# Run a databricks CLI command with JSON output. The CLI can print notices before the JSON
# (for example about updates or optional add-ons), so drop anything before the first { or [.
# Errors go to stderr: dbx_json is usually piped into jq, which would otherwise swallow them.
dbx_json() {
  local out
  out="$(databricks "$@" -o json 2>"$TMP/stderr")" || { echo "ERROR: databricks $* failed:" >&2; cat "$TMP/stderr" >&2; exit 1; }
  # Keep only the JSON document: from the first line that starts with { or [ to the line that closes it.
  out="$(printf '%s\n' "$out" | sed -n '/^[[{]/,/^[]}]/p')"
  [ -n "$out" ] || { echo "ERROR: databricks $* returned no JSON:" >&2; cat "$TMP/stderr" >&2; exit 1; }
  printf '%s\n' "$out"
}

HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
ME="$(dbx_json current-user me | jq -r .userName)"
HOME_PATH="/Users/$ME"

fill() {
  sed -e "s|<catalog>|$CATALOG|g" -e "s|<schema>|$SCHEMA|g" -e "s|<source_schema>|$SOURCE_SCHEMA|g" "$1"
}

WAREHOUSE_ID="$(dbx_json warehouses list | jq -r --arg n "$WAREHOUSE_NAME" '[.[] | select(.name == $n)][0].id // empty')"
[ -n "$WAREHOUSE_ID" ] || { echo "No SQL warehouse named '$WAREHOUSE_NAME'. Set WAREHOUSE_NAME and re-run."; exit 1; }

echo "==> Building dev assets in $CATALOG.$SCHEMA (source: $CATALOG.$SOURCE_SCHEMA) as $ME"

# 0. Your schema (created if it doesn't exist yet).
if ! databricks schemas get "$CATALOG.$SCHEMA" > /dev/null 2>&1; then
  dbx_json schemas create "$SCHEMA" "$CATALOG" > /dev/null
  echo "    created schema $CATALOG.$SCHEMA"
fi

# 1. Pipeline: SQL files in your home folder, writing to your schema.
# Pipeline names are unique in a workspace, so stop if an earlier run already created one.
EXISTING="$(dbx_json pipelines list-pipelines --filter "name LIKE 'encounters_pipeline'" | jq -r '[.[]? | .pipeline_id] | join(" ")')"
if [ -n "$EXISTING" ]; then
  echo "ERROR: a pipeline named encounters_pipeline already exists ($EXISTING)." >&2
  echo "Delete it (and the dashboard, Genie agent, and job from the earlier run) before re-running:" >&2
  echo "  databricks pipelines delete $EXISTING" >&2
  exit 1
fi
PIPE_DIR="$HOME_PATH/encounters_pipeline"
databricks workspace mkdirs "$PIPE_DIR/transformations"
for f in silver_encounters gold_encounters; do
  fill "$HERE/pipeline/$f.sql" > "$TMP/$f.sql"
  databricks workspace import "$PIPE_DIR/transformations/$f.sql" --file "$TMP/$f.sql" --format RAW --overwrite
done
jq -n --arg c "$CATALOG" --arg s "$SCHEMA" --arg d "$PIPE_DIR" \
  '{name: "encounters_pipeline", catalog: $c, schema: $s, serverless: true, root_path: $d,
    libraries: [{glob: {include: ($d + "/transformations/**")}}]}' > "$TMP/pipeline.json"
PIPELINE_ID="$(dbx_json pipelines create --json @"$TMP/pipeline.json" | jq -r .pipeline_id)"
echo "    pipeline  $PIPELINE_ID — running it once so gold_encounters exists..."
UPDATE_ID="$(dbx_json pipelines start-update "$PIPELINE_ID" | jq -r .update_id)"
while :; do
  STATE="$(dbx_json pipelines get-update "$PIPELINE_ID" "$UPDATE_ID" | jq -r .update.state)"
  case "$STATE" in COMPLETED) break ;; FAILED|CANCELED) echo "Pipeline update $STATE. Open the pipeline to see why."; exit 1 ;; esac
  sleep 10
done

# 2. Dashboard: one dataset on your gold_encounters.
fill "$HERE/encounters_outcomes.lvdash.json" > "$TMP/dashboard.lvdash.json"
jq -n --rawfile d "$TMP/dashboard.lvdash.json" --arg w "$WAREHOUSE_ID" --arg p "$HOME_PATH" \
  '{display_name: "Encounters & Outcomes", warehouse_id: $w, parent_path: $p, serialized_dashboard: $d}' > "$TMP/dashboard.json"
DASHBOARD_ID="$(dbx_json lakeview create --json @"$TMP/dashboard.json" | jq -r .dashboard_id)"
echo "    dashboard $DASHBOARD_ID"

# 3. Genie agent on your gold_encounters.
fill "$HERE/encounters_outcomes_genie.json" > "$TMP/space.json"
jq -n --rawfile s "$TMP/space.json" --arg w "$WAREHOUSE_ID" --arg p "$HOME_PATH" \
  '{title: "Encounters & Outcomes Genie", description: "Ask questions about encounters, readmissions, and charges.",
    warehouse_id: $w, parent_path: $p, serialized_space: $s}' > "$TMP/genie.json"
GENIE_ID="$(dbx_json genie create-space --json @"$TMP/genie.json" | jq -r .space_id)"
echo "    genie     $GENIE_ID"

# 4. Job: refreshes the pipeline daily, paused.
sed "s|<pipeline_id>|$PIPELINE_ID|" "$HERE/encounters_refresh.job.json" > "$TMP/job.json"
JOB_ID="$(dbx_json jobs create --json @"$TMP/job.json" | jq -r .job_id)"
echo "    job       $JOB_ID"

cat <<EOF

==> Done. Share these links with students (and grant them Can view on each):
  Pipeline     $URL/pipelines/$PIPELINE_ID
  Dashboard    $URL/dashboardsv3/$DASHBOARD_ID
  Genie agent  $URL/genie/rooms/$GENIE_ID
  Job          $URL/jobs/$JOB_ID
Pipeline source folder (grant Can read): $PIPE_DIR
EOF
