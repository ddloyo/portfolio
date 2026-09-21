"""
Sincroniza este proyecto con el warehouse dbt real. Es el único paso que toca
`warehouse/`; el resto (generate_data.py, run_analysis.py) trabaja sobre lo que
este script deja en data/.

  1. Lee los umbrales de freshness DIRECTO de los `_*__sources.yml`
     -> data/sla_thresholds.csv
  2. Con --run: ejecuta `dbt source freshness` y copia el target/sources.json
     que produce -> data/dbt_sources_freshness.json (la foto real del instante)

Corre con el Python del venv del warehouse (necesita PyYAML y dbt):

  cd warehouse && source .venv/bin/activate && export DBT_PROFILES_DIR=profiles
  dbt seed                                # sella _loaded_at (ver macros/stamp_loaded_at.sql)
  python ../projects/16-frescura-disponibilidad-datos/data/sync_from_dbt.py --run
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys

from freshness_rules import DATA_DIR, DBT_SNAPSHOT_JSON, THRESHOLDS_CSV, WAREHOUSE, load_yaml_thresholds


def write_thresholds():
    cfg = load_yaml_thresholds()
    if not cfg:
        sys.exit("No se encontró ningún bloque `freshness` en warehouse/models/staging/*/_*__sources.yml")
    with open(THRESHOLDS_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "table", "loaded_at_field", "warn_after_count", "warn_after_period",
                    "error_after_count", "error_after_period"])
        for (source, table), c in sorted(cfg.items()):
            w.writerow([source, table, c["loaded_at_field"], *c["warn"], *c["error"]])
    print(f"OK -> {THRESHOLDS_CSV.relative_to(DATA_DIR.parents[2])} ({len(cfg)} tablas con freshness)")


def run_dbt_freshness():
    env = {**os.environ, "DBT_PROFILES_DIR": os.environ.get("DBT_PROFILES_DIR", "profiles")}
    # dbt sale con código != 0 si hay fuentes en `error`: es el resultado esperado, no una falla del comando
    proc = subprocess.run(["dbt", "source", "freshness"], cwd=WAREHOUSE, env=env, capture_output=True, text=True)
    print(proc.stdout[-1500:])
    produced = WAREHOUSE / "target" / "sources.json"
    if not produced.exists():
        sys.exit(f"dbt no produjo {produced}:\n{proc.stderr[-800:]}")
    shutil.copyfile(produced, DBT_SNAPSHOT_JSON)
    print(f"OK -> {DBT_SNAPSHOT_JSON.relative_to(DATA_DIR.parents[2])} (copia de warehouse/target/sources.json)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="además corre `dbt source freshness` y copia sources.json")
    args = ap.parse_args()
    write_thresholds()
    if args.run:
        run_dbt_freshness()
