"""
Reglas de frescura compartidas: la MISMA clasificación pass/warn/error que usa
`dbt source freshness`, para que la simulación (generate_data.py), el dashboard
(run_analysis.py) y la prueba de paridad (verify_dbt_parity.py) no puedan
divergir entre sí ni de dbt.

Réplica de dbt-core 1.10 (`FreshnessThreshold.status` / `Time.exceeded`, en
dbt/artifacts/resources/v1/components.py):
  - error se evalúa primero; luego warn; si no, pass.
  - la comparación es estricta: un age exactamente igual al umbral NO lo excede.
  - un umbral ausente (None) no se evalúa.

Los umbrales NO se escriben aquí: salen de los `_*__sources.yml` del warehouse
(bloque `freshness`), vía `sync_from_dbt.py` -> data/sla_thresholds.csv.
Este módulo solo usa la librería estándar (PyYAML se importa a demanda, y solo
`sync_from_dbt.py` lo necesita).
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATA_DIR.parents[2]
WAREHOUSE = REPO_ROOT / "warehouse"
THRESHOLDS_CSV = DATA_DIR / "sla_thresholds.csv"
DBT_SNAPSHOT_JSON = DATA_DIR / "dbt_sources_freshness.json"

PERIOD_SECONDS = {"minute": 60, "hour": 3600, "day": 86400}


def to_seconds(count, period):
    """{count: 6, period: hour} -> 21600 (segundos). None si no hay umbral."""
    if count in (None, "") or period in (None, ""):
        return None
    return int(float(count)) * PERIOD_SECONDS[period]


def classify(age_s, warn_s, error_s):
    """pass / warn / error igual que dbt-core: error primero, comparación estricta (>)."""
    if error_s is not None and age_s > error_s:
        return "error"
    if warn_s is not None and age_s > warn_s:
        return "warn"
    return "pass"


def parse_ts(value):
    """ISO-8601 (con o sin 'Z' / offset) -> datetime con tz UTC."""
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_thresholds(path=THRESHOLDS_CSV):
    """data/sla_thresholds.csv -> {(source, table): {warn_s, error_s, ...}} en el orden del archivo."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[(r["source"], r["table"])] = {
                "loaded_at_field": r["loaded_at_field"],
                "warn_count": r["warn_after_count"], "warn_period": r["warn_after_period"],
                "error_count": r["error_after_count"], "error_period": r["error_after_period"],
                "warn_s": to_seconds(r["warn_after_count"], r["warn_after_period"]),
                "error_s": to_seconds(r["error_after_count"], r["error_after_period"]),
            }
    return out


def load_dbt_snapshot(path=DBT_SNAPSHOT_JSON):
    """target/sources.json de dbt (copia versionada) -> {(source, table): resultado}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for r in data["results"]:
        # unique_id: source.<proyecto>.<source>.<tabla>
        _, _, source, table = r["unique_id"].split(".", 3)
        out[(source, table)] = r
    return out, data["metadata"]


def load_yaml_thresholds(sources_glob="models/staging/*/_*__sources.yml"):
    """Lee los umbrales DIRECTO de los YAML de dbt (requiere PyYAML). Devuelve
    {(source, table): {loaded_at_field, warn: (count, period), error: (count, period)}}.
    El `freshness` de una tabla sustituye al del source, igual que en dbt."""
    import yaml  # solo lo necesitan sync_from_dbt.py y verify_dbt_parity.py

    out = {}
    for f in sorted(WAREHOUSE.glob(sources_glob)):
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        for src in doc.get("sources", []):
            s_cfg = src.get("config", {}) or {}
            for tbl in src.get("tables", []):
                t_cfg = tbl.get("config", {}) or {}
                fr = t_cfg.get("freshness", s_cfg.get("freshness"))
                if not fr:
                    continue
                field = t_cfg.get("loaded_at_field", s_cfg.get("loaded_at_field"))
                w, e = fr.get("warn_after"), fr.get("error_after")
                out[(src["name"], tbl["name"])] = {
                    "loaded_at_field": field,
                    "warn": (w["count"], w["period"]) if w else (None, None),
                    "error": (e["count"], e["period"]) if e else (None, None),
                }
    return out
