"""Move a generated Genie space definition inline so it can use bundle variables.

`databricks bundle generate genie-space` writes the agent's definition to
src/<name>.geniespace.json and points the YAML at it with `file_path:`. Bundle
variables aren't substituted inside that file, so the agent's table stays
hard-coded to the schema it was built in.

This script copies the JSON into the YAML as `serialized_space`, replaces the
hard-coded table name with ${var.catalog}.${var.schema}.<table> so it follows the
target you deploy to, and removes the JSON file.

Run it from your bundle folder:

    python ../dabs-workshop/tools/inline_genie.py
"""
import glob
import json
import os
import re
import sys

yml_paths = glob.glob("resources/*.genie_space.yml")
if len(yml_paths) != 1:
    sys.exit(f"Expected one resources/*.genie_space.yml, found {len(yml_paths)}. Run this from your bundle folder.")
yml_path = yml_paths[0]
yml = open(yml_path).read()

m = re.search(r"^(\s*)file_path:\s*(\S+)\s*$", yml, re.M)
if not m:
    sys.exit(f"{yml_path} has no file_path: line. Has it already been converted?")
indent, rel = m.group(1), m.group(2)
json_path = os.path.normpath(os.path.join(os.path.dirname(yml_path), rel))
space = json.load(open(json_path))

# The agent's tables are its data sources; point each one at your catalog and schema.
tables = [t["identifier"] for t in space.get("data_sources", {}).get("tables", [])]
body = json.dumps(space, indent=2)
for ident in tables:
    catalog, schema, table = ident.split(".")
    # Example SQL may quote the names (needed for catalogs with hyphens); replace both forms.
    body = body.replace(f"`{catalog}`.`{schema}`.{table}", "`${var.catalog}`.`${var.schema}`." + table)
    body = body.replace(ident, "${var.catalog}.${var.schema}." + table)

block = indent + "serialized_space: |\n" + "\n".join(indent + "  " + line for line in body.splitlines())
yml = yml[: m.start()] + block + yml[m.end():]
open(yml_path, "w").write(yml.rstrip("\n") + "\n")
os.remove(json_path)

print(f"Updated {yml_path}")
for ident in tables:
    print(f"  {ident}  ->  ${{var.catalog}}.${{var.schema}}.{ident.split('.')[-1]}")
print(f"Removed {json_path}")
