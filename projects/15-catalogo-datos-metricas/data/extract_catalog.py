"""
Extrae el catálogo del warehouse dbt REAL (warehouse/) a un snapshot JSON
versionado: data/catalog_snapshot.json.

Lee los artefactos que dbt deja en warehouse/target/:
  manifest.json     -- modelos, fuentes, descripciones, tests, depends_on (lineage)
  catalog.json      -- columnas y tipos reales tal como quedaron en DuckDB
  run_results.json  -- resultado de la última corrida de `dbt test`
y los CSV de seeds del scorecard (dim_kpi mezcla captura manual y KPIs derivables).

Por qué un snapshot en vez de leer target/ cada vez: warehouse/target/ está en
.gitignore (se reconstruye en cada máquina y en CI), y el sitio del portafolio
es estático. run_analysis.py solo lee el snapshot, así que el dashboard se
reconstruye en cualquier clon sin instalar dbt; este script es el único paso
que toca el warehouse, y --check detecta cuando el snapshot quedó viejo.

Uso (desde projects/15-catalogo-datos-metricas/):
  python3 data/extract_catalog.py           # regenera data/catalog_snapshot.json
  python3 data/extract_catalog.py --check   # exit 1 si el warehouse ya no coincide

Orden importante en dbt: `dbt docs generate` primero y `dbt test` DESPUÉS.
`docs generate` también escribe run_results.json (con un resultado "generate" por
nodo, sin tests reales) y pisaría el resultado de los tests.
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT.parents[1] / "warehouse"
TARGET = WAREHOUSE / "target"
SNAPSHOT = ROOT / "data" / "catalog_snapshot.json"

LAYER_ORDER = ["bronze", "staging", "intermediate", "marts", "meta", "gold"]


def load(name):
    path = TARGET / name
    if not path.exists():
        sys.exit(f"Falta {path}. Corre en warehouse/: dbt docs generate && dbt test (ver README del proyecto 15).")
    return json.loads(path.read_text(encoding="utf-8"))


def short_id(node):
    """Llave corta y única: modelos -> nombre; fuentes -> '<sistema>.<tabla>'."""
    if node["resource_type"] == "source":
        return f"{node['source_name']}.{node['name']}"
    return node["name"]


def tested_node(test, uid_to_id):
    """Nodo(s) que cubre un test. `attached_node` viene vacío en dbt 1.10 para los
    tests de fuentes y los singulares (50 de 429 se perderían en silencio), así que
    se resuelve por el ref()/source() del kwarg `model` y, si no hay, por depends_on."""
    if test.get("attached_node"):
        return [uid_to_id[test["attached_node"]]]
    model_kwarg = (test.get("test_metadata") or {}).get("kwargs", {}).get("model", "")
    src = re.search(r"source\('([^']+)',\s*'([^']+)'\)", model_kwarg)
    if src:
        return [f"{src.group(1)}.{src.group(2)}"]
    ref = re.search(r"ref\('([^']+)'\)", model_kwarg)
    if ref:
        return [ref.group(1)]
    # singular: toca los modelos de los que depende
    return sorted(uid_to_id[d] for d in test["depends_on"]["nodes"] if d in uid_to_id)


def describe_test(test):
    """(tipo, columna, detalle legible) de un test."""
    meta = test.get("test_metadata")
    if not meta:
        return "singular", None, test["name"]
    kind, kw = meta["name"], meta["kwargs"]
    col = kw.get("column_name")
    if kind == "relationships":
        to = re.sub(r"^(ref|source)\('([^']+)'(?:,\s*'([^']+)')?\)$",
                    lambda m: m.group(3) and f"{m.group(2)}.{m.group(3)}" or m.group(2), kw["to"])
        return kind, col, f"{col} debe existir en {to}.{kw['field']}"
    if kind == "accepted_values":
        vals = kw["values"]
        return kind, col, f"{col} ∈ {{{', '.join(map(str, vals[:6]))}{', …' if len(vals) > 6 else ''}}}"
    if kind == "accepted_range":
        lo, hi = kw.get("min_value"), kw.get("max_value")
        return kind, col, f"{col} entre {'−∞' if lo is None else lo} y {'∞' if hi is None else hi}"
    if kind == "unique_combination_of_columns":
        return kind, None, "combinación única de " + ", ".join(kw["combination_of_columns"])
    if kind == "not_null":
        return kind, col, f"{col} no nulo"
    if kind == "unique":
        return kind, col, f"{col} único"
    return kind, col, f"{kind}" + (f" · {col}" if col else "")


def parse_kpis(manifest):
    """dim_kpi = KPIs de captura manual (seed) + KPIs derivables (VALUES en el SQL).
    Se reconstruye desde las mismas dos fuentes que usa el modelo, más la meta vigente."""
    seeds = {v["name"]: v for v in manifest["nodes"].values() if v["resource_type"] == "seed"}

    def seed_rows(name):
        with open(WAREHOUSE / seeds[name]["original_file_path"], encoding="utf-8") as f:
            return list(csv.DictReader(f))

    kpis = {}
    for r in seed_rows("kpi_captura_manual"):
        kpis[r["kpi"]] = {"kpi": r["kpi"], "area": r["area"], "responsable": r["responsable"], "unidad": r["unidad"],
                          "menor_es_mejor": r["menor_es_mejor"].strip().lower() == "true", "origen": "captura manual"}
    code = manifest["nodes"]["model.xia_warehouse.dim_kpi"]["raw_code"]
    derived = re.findall(r"\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*(true|false)\)", code)
    if len(derived) != 3:
        sys.exit(f"dim_kpi.sql cambió: esperaba 3 KPIs derivables en el VALUES y encontré {len(derived)}.")
    for nombre, area, resp, unidad, menor in derived:
        kpis[nombre] = {"kpi": nombre, "area": area, "responsable": resp, "unidad": unidad,
                        "menor_es_mejor": menor == "true", "origen": "derivado"}
    for r in seed_rows("kpi_meta"):
        kpis[r["kpi"]]["meta"] = float(r["meta"])
    return sorted(kpis.values(), key=lambda k: k["kpi"])


def build():
    manifest, catalog, results = load("manifest.json"), load("catalog.json"), load("run_results.json")

    which = results["args"].get("which")
    if which not in ("test", "build"):
        sys.exit(f"run_results.json viene de `dbt {which}`, no de `dbt test`: no trae el resultado de los tests. "
                 "Corre `dbt docs generate` y luego `dbt test` (en ese orden).")
    status_by_uid = {r["unique_id"]: r for r in results["results"]}

    nodes = {uid: n for uid, n in manifest["nodes"].items() if n["resource_type"] == "model"}
    nodes.update(manifest["sources"])
    uid_to_id = {uid: short_id(n) for uid, n in nodes.items()}
    cat = {**catalog["nodes"], **catalog["sources"]}

    tests_by_node = defaultdict(list)
    for uid, t in manifest["nodes"].items():
        if t["resource_type"] != "test":
            continue
        run = status_by_uid.get(uid)
        if run is None:
            sys.exit(f"El test {t['name']} no aparece en run_results.json: corre `dbt test` de nuevo.")
        kind, column, detail = describe_test(t)
        entry = {"kind": kind, "column": column, "detail": detail, "severity": t["config"].get("severity", "ERROR").lower(),
                 "status": run["status"], "failures": run.get("failures") or 0}
        for target in tested_node(t, uid_to_id):
            tests_by_node[target].append(entry)

    def neighbours(uid, mapping):
        return sorted(uid_to_id[x] for x in mapping.get(uid, []) if x in uid_to_id)

    items = []
    for uid, n in nodes.items():
        sid = uid_to_id[uid]
        is_source = n["resource_type"] == "source"
        cols = {}
        for name, c in (cat.get(uid, {}).get("columns", {})).items():
            cols[name] = {"name": name, "type": c["type"].lower(), "description": ""}
        for name, c in n["columns"].items():
            cols.setdefault(name, {"name": name, "type": (c.get("data_type") or ""), "description": ""})
            cols[name]["description"] = c["description"].strip()
        cmeta = cat.get(uid, {}).get("metadata", {})
        layer = "bronze" if is_source else n["fqn"][1]
        items.append({
            "id": sid,
            "kind": "source" if is_source else "model",
            "name": n["name"],
            "layer": layer,
            "group": n["source_name"] if is_source else (n["fqn"][2] if len(n["fqn"]) > 3 else None),
            "materialized": "source" if is_source else n["config"]["materialized"],
            "relation": f"{cmeta.get('schema', n['schema'])}.{n['name']}",
            "path": n.get("original_file_path") or "",
            "description": (n["description"] or "").strip(),
            "has_doc_block": bool(n.get("doc_blocks")),
            "contract": False if is_source else bool(n["contract"]["enforced"]),
            "columns": list(cols.values()),
            "tests": sorted(tests_by_node.get(sid, []), key=lambda t: (t["kind"], t["column"] or "", t["detail"])),
            "upstream": neighbours(uid, manifest["parent_map"]),
            "downstream": neighbours(uid, manifest["child_map"]),
            "meta": n.get("meta") or {},
        })
    items.sort(key=lambda i: (LAYER_ORDER.index(i["layer"]), i["group"] or "", i["id"]))

    n_tests = sum(1 for n in manifest["nodes"].values() if n["resource_type"] == "test")
    n_covered = sum(len(v) for v in tests_by_node.values())
    statuses = defaultdict(int)
    for r in results["results"]:
        if r["unique_id"].startswith("test."):
            statuses[r["status"]] += 1

    return {
        "provenance": {
            "dbt_version": manifest["metadata"]["dbt_version"],
            "manifest_generated_at": manifest["metadata"]["generated_at"],
            "run_results_command": which,
            "run_results_generated_at": results["metadata"]["generated_at"],
            "tests_total": n_tests,
            "test_status": dict(sorted(statuses.items())),
            "test_attachments": n_covered,
        },
        "nodes": items,
        "kpis": parse_kpis(manifest),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="no escribe: sale con 1 si el snapshot difiere del warehouse")
    args = ap.parse_args()

    snap = build()
    text = json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    n_models = sum(1 for n in snap["nodes"] if n["kind"] == "model")
    n_sources = len(snap["nodes"]) - n_models
    summary = f"{n_models} modelos, {n_sources} fuentes, {snap['provenance']['tests_total']} tests {snap['provenance']['test_status']}"

    if args.check:
        old = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else None
        strip = lambda d: {k: v for k, v in d.items() if k != "provenance"} if d else d
        if strip(old) != strip(snap):
            print(f"DIFIERE: {SNAPSHOT.relative_to(ROOT)} ya no coincide con el warehouse ({summary}). Regenera con extract_catalog.py.")
            sys.exit(1)
        print(f"OK: el snapshot coincide con el warehouse ({summary}).")
        return

    SNAPSHOT.write_text(text, encoding="utf-8")
    print(f"OK -> {SNAPSHOT.relative_to(ROOT)}: {summary}")


if __name__ == "__main__":
    main()
