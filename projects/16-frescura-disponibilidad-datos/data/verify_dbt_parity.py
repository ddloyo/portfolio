"""
Prueba de paridad: la clasificación pass/warn/error de la simulación coincide con
la de `dbt source freshness`. Es lo que conecta este proyecto con la config real de
dbt y evita que el dashboard sea "un chart inventado".

Cuatro comprobaciones (todas deben pasar; el script sale con código 1 si alguna falla):

  A. Config      Los umbrales de los `_*__sources.yml` (fuente de verdad) == data/sla_thresholds.csv
                 (lo que usa la simulación) == el `criteria` que dbt escribió en sources.json.
  B. Foto real   Para cada tabla del sources.json versionado: el `status` que reportó dbt ==
                 classify(age de dbt, umbrales del YAML).
  C. Fronteras   Corre `dbt source freshness` EN VIVO (sobre una copia desechable de la base) en 6
                 escenarios que ponen la edad de cada tabla justo debajo y justo arriba de su warn y
                 de su error (0.5x, 0.98x, 1.02x del warn; 0.98x, 1.02x y 3x del error) y compara el
                 status de dbt con el de la simulación: 6 escenarios x 22 tablas.
  D. Igualdad    Contra la clase de dbt-core (`FreshnessThreshold.status`), con la edad EXACTAMENTE en
                 el umbral, un segundo debajo y un segundo arriba: la comparación es estricta (>), un
                 age igual al umbral sigue siendo `pass`/`warn`, no el siguiente estado.

Escribe data/parity_report.csv con cada comparación de B y C.

Corre con el Python del venv del warehouse (necesita dbt, duckdb y PyYAML) y con los seeds ya
cargados (`dbt seed`):

  cd warehouse && source .venv/bin/activate && export DBT_PROFILES_DIR=profiles
  python ../projects/16-frescura-disponibilidad-datos/data/verify_dbt_parity.py
"""

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from freshness_rules import (DATA_DIR, WAREHOUSE, classify, load_dbt_snapshot, load_thresholds,
                             load_yaml_thresholds, parse_ts, to_seconds)

REPORT = DATA_DIR / "parity_report.csv"
# (nombre, umbral de referencia, factor sobre el umbral, status esperado por construcción)
SCENARIOS = [
    ("0.50x warn", "warn", 0.50, "pass"),
    ("0.98x warn", "warn", 0.98, "pass"),
    ("1.02x warn", "warn", 1.02, "warn"),
    ("0.98x error", "error", 0.98, "warn"),
    ("1.02x error", "error", 1.02, "error"),
    ("3.00x error", "error", 3.00, "error"),
]

failures = []


def check(ok, label):
    print(("  ok    " if ok else "  FALLA ") + label)
    if not ok:
        failures.append(label)


def fmt(count, period):
    return f"{count} {period}"


def part_a(yaml_cfg, csv_cfg, snap):
    print("A. Config: YAML == sla_thresholds.csv == criteria de sources.json")
    check(set(yaml_cfg) == set(csv_cfg) == set(snap),
          f"las tres fuentes describen las mismas {len(yaml_cfg)} tablas")
    for key, y in sorted(yaml_cfg.items()):
        c, r = csv_cfg[key], snap[key]["criteria"]
        yw, ye = to_seconds(*y["warn"]), to_seconds(*y["error"])
        same_csv = (c["warn_s"], c["error_s"]) == (yw, ye)
        same_dbt = (to_seconds(r["warn_after"]["count"], r["warn_after"]["period"]),
                    to_seconds(r["error_after"]["count"], r["error_after"]["period"])) == (yw, ye)
        if not (same_csv and same_dbt):
            check(False, f"{key[0]}.{key[1]}: YAML {y['warn']}/{y['error']} vs csv {same_csv} vs dbt {same_dbt}")
    if not failures:
        check(True, "umbrales idénticos en las 22 tablas (YAML = CSV = dbt)")


def part_b(yaml_cfg, snap):
    print("B. Foto real: status de dbt vs classify() sobre el sources.json versionado")
    rows, bad = [], 0
    for (source, table), r in sorted(snap.items()):
        y = yaml_cfg[(source, table)]
        age = r["max_loaded_at_time_ago_in_s"]
        recomputed = (parse_ts(r["snapshotted_at"]) - parse_ts(r["max_loaded_at"])).total_seconds()
        sim = classify(age, to_seconds(*y["warn"]), to_seconds(*y["error"]))
        ok = sim == r["status"] and abs(recomputed - age) < 0.01
        bad += not ok
        rows.append(["foto_real", source, table, "", round(age / 3600, 3), fmt(*y["warn"]), fmt(*y["error"]),
                     r["status"], sim, "", ok])
    check(bad == 0, f"{len(rows) - bad}/{len(rows)} tablas: dbt == simulación (y age recomputado == age de dbt)")
    return rows


def dbt_bin():
    cand = Path(sys.executable).parent / "dbt"
    return str(cand) if cand.exists() else (shutil.which("dbt") or sys.exit("No encuentro el ejecutable dbt"))


def part_c(yaml_cfg):
    print("C. Fronteras: `dbt source freshness` en vivo vs classify(), 6 escenarios x 22 tablas")
    import duckdb  # solo en el venv del warehouse

    src_db = WAREHOUSE / "xia_warehouse.duckdb"
    if not src_db.exists():
        sys.exit("Falta warehouse/xia_warehouse.duckdb: corre `dbt seed` primero")
    rows, bad, total = [], 0, 0
    with tempfile.TemporaryDirectory(prefix="xia_parity_") as tmp:
        tmp = Path(tmp)
        db = tmp / "parity.duckdb"
        shutil.copyfile(src_db, db)  # copia desechable: no se toca el warehouse real
        (tmp / "profiles.yml").write_text(
            f"xia_warehouse:\n  target: parity\n  outputs:\n    parity:\n      type: duckdb\n"
            f"      path: '{db}'\n      threads: 4\n", encoding="utf-8")
        for name, ref, factor, expected in SCENARIOS:
            targets = {}
            con = duckdb.connect(str(db))
            for (source, table), y in yaml_cfg.items():
                secs = to_seconds(*y[ref]) * factor
                targets[(source, table)] = secs
                con.execute(f'update raw."{table}" set _loaded_at = now() - to_milliseconds({int(secs * 1000)})')
            con.close()
            out = tmp / "sources.json"
            subprocess.run([dbt_bin(), "source", "freshness", "--project-dir", str(WAREHOUSE),
                            "--profiles-dir", str(tmp), "--target-path", str(tmp / "target"),
                            "--log-path", str(tmp / "logs"), "-o", str(out)],
                           capture_output=True, text=True, cwd=WAREHOUSE)  # sale != 0 si hay `error`: esperado
            results = json.loads(out.read_text(encoding="utf-8"))["results"]
            for r in results:
                _, _, source, table = r["unique_id"].split(".", 3)
                y = yaml_cfg[(source, table)]
                age = r["max_loaded_at_time_ago_in_s"]
                sim = classify(age, to_seconds(*y["warn"]), to_seconds(*y["error"]))
                ok = sim == r["status"] == expected
                bad += not ok
                total += 1
                rows.append([name, source, table, round(targets[(source, table)] / 3600, 3), round(age / 3600, 3),
                             fmt(*y["warn"]), fmt(*y["error"]), r["status"], sim, expected, ok])
            n_ok = sum(1 for x in rows if x[0] == name and x[-1])
            print(f"    escenario {name:<12} dbt == simulación == esperado en {n_ok}/{len(yaml_cfg)} tablas")
    check(bad == 0, f"{total - bad}/{total} comparaciones coinciden (dbt en vivo == simulación == esperado)")
    return rows


def part_d(yaml_cfg):
    print("D. Igualdad exacta contra dbt-core (FreshnessThreshold.status), edad = umbral -1s / 0 / +1s")
    from dbt.artifacts.resources.types import TimePeriod
    from dbt.artifacts.resources.v1.components import FreshnessThreshold, Time

    bad = total = 0
    for (source, table), y in sorted(yaml_cfg.items()):
        th = FreshnessThreshold(warn_after=Time(count=y["warn"][0], period=TimePeriod(y["warn"][1])),
                                error_after=Time(count=y["error"][0], period=TimePeriod(y["error"][1])))
        ws, es = to_seconds(*y["warn"]), to_seconds(*y["error"])
        for age in (ws - 1, ws, ws + 1, es - 1, es, es + 1):
            total += 1
            bad += th.status(age).value != classify(age, ws, es)
    check(bad == 0, f"{total - bad}/{total} edades en la frontera: dbt-core == classify()")


if __name__ == "__main__":
    yaml_cfg = load_yaml_thresholds()
    csv_cfg = load_thresholds()
    snap, _ = load_dbt_snapshot()
    part_a(yaml_cfg, csv_cfg, snap)
    rows = part_b(yaml_cfg, snap)
    rows += part_c(yaml_cfg)
    part_d(yaml_cfg)

    with open(REPORT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["escenario", "source", "table", "age_objetivo_h", "age_dbt_h", "warn_after", "error_after",
                    "status_dbt", "status_simulacion", "status_esperado", "coincide"])
        w.writerows(rows)
    print(f"\nOK -> {REPORT.relative_to(DATA_DIR.parents[2])} ({len(rows)} comparaciones)")
    if failures:
        print(f"\n{len(failures)} comprobación(es) fallaron:\n  - " + "\n  - ".join(failures))
        sys.exit(1)
    print("Paridad completa: la simulación clasifica igual que dbt.")
