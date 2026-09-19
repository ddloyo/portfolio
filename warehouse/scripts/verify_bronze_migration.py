"""Verifica que la migración de database/schema/01_bronze.sql a seeds de dbt
sea 1:1. Es una herramienta TEMPORAL: se borra junto con los archivos legacy
cuando termine la migración (ver database/LEGACY_TABLES.md).

Para cada tabla `bronze.<t>` del DDL legacy comprueba:
  1. existe un seed seeds/**/<t>.csv
  2. sus columnas == columnas del DDL (menos linaje y exclusiones documentadas)
  3. está declarada como source de dbt con meta.legacy_table = bronze.<t>
  4. cargó en DuckDB (schema raw) con las mismas columnas y el mismo n° de filas
  5. fidelidad de datos (solo las que vienen de projects/):
       IDENTICA  -> el CSV es byte a byte el original
       AUMENTADA -> conserva todas las columnas/filas originales, mismos valores
  6. aparece en database/LEGACY_TABLES.md
Además, todo seed sin tabla legacy debe estar en EXTRAS_PERMITIDOS.

Uso (desde warehouse/, después de `dbt seed`):
    python3 scripts/verify_bronze_migration.py [ruta_a_la_base.duckdb]
"""
import csv
import hashlib
import re
import sys
from pathlib import Path

import duckdb
import yaml

WAREHOUSE = Path(__file__).resolve().parent.parent
REPO = WAREHOUSE.parent
LEGACY_SQL = REPO / "database" / "schema" / "01_bronze.sql"
LEGACY_DOC = REPO / "database" / "LEGACY_TABLES.md"
SEEDS = WAREHOUSE / "seeds"
DB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WAREHOUSE / "xia_warehouse.duckdb"
P11 = REPO / "projects" / "11-consolidacion-fuente-verdad" / "data"
P13 = REPO / "projects" / "13-data-health-check" / "data"

# Columnas del DDL que NO se migran, con el motivo. Espejo de LEGACY_TABLES.md.
EXCLUSIONES = {
    "pedido_linea": {"sucursal"},
}
# tabla -> (archivo original, modo)
FIDELIDAD = {
    "calendario": (P13 / "calendario.csv", "IDENTICA"),
    "pedido_sucursal_cdmx": (P11 / "raw_export_cdmx.csv", "IDENTICA"),
    "pedido_sucursal_guadalajara": (P11 / "raw_export_guadalajara.csv", "IDENTICA"),
    "pedido_sucursal_monterrey": (P11 / "raw_export_monterrey.csv", "IDENTICA"),
    "crm_cliente": (P13 / "clientes.csv", "AUMENTADA"),
    "producto": (P13 / "productos.csv", "AUMENTADA"),
    "factura_linea": (P13 / "facturas.csv", "AUMENTADA"),
}
EXTRAS_PERMITIDOS = {"kpi_meta"}  # seed de dbt sin tabla legacy (ver LEGACY_TABLES.md)


def tablas_legacy():
    sql = LEGACY_SQL.read_text(encoding="utf-8")
    tablas = {}
    for m in re.finditer(r"CREATE TABLE bronze\.(\w+) \((.*?)\n\);", sql, re.DOTALL):
        cols = []
        for line in m.group(2).splitlines():
            c = re.match(r'^\s*"?([A-Za-z_][A-Za-z0-9_]*)"?\s+(?:TEXT|UUID|TIMESTAMPTZ)\b', line)
            if c and not c.group(1).startswith("_"):
                cols.append(c.group(1))
        tablas[m.group(1)] = cols
    return tablas


def leer_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r)
        return header, list(r)


def sources_declarados():
    declarados = {}
    for p in (WAREHOUSE / "models").rglob("*.yml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for s in doc.get("sources", []):
            for t in s.get("tables", []):
                declarados[t["name"]] = (t.get("meta") or {}).get("legacy_table")
    return declarados


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not DB.exists():
        sys.exit(f"No existe {DB.name}: corre `dbt seed` primero.")
    legacy = tablas_legacy()
    seeds = {p.stem: p for p in SEEDS.rglob("*.csv")}
    declarados = sources_declarados()
    doc = LEGACY_DOC.read_text(encoding="utf-8") if LEGACY_DOC.exists() else ""
    con = duckdb.connect(str(DB), read_only=True)

    fallas = fallas_legacy = 0
    print(f"{'tabla legacy':<32} {'seed':<5} {'cols':<5} {'src':<5} {'db':<5} {'fidel':<7} {'doc':<4} filas")
    print("-" * 82)
    for t, cols_ddl in legacy.items():
        esperadas = [c for c in cols_ddl if c not in EXCLUSIONES.get(t, set())]
        r = {"seed": False, "cols": False, "src": False, "db": False, "fid": "n/a", "doc": False}
        detalle, filas = [], "-"

        if t in seeds:
            r["seed"] = True
            header, rows = leer_csv(seeds[t])
            filas = len(rows)
            falta, sobra = set(esperadas) - set(header), set(header) - set(esperadas)
            r["cols"] = not falta and not sobra
            if falta:
                detalle.append(f"faltan columnas {sorted(falta)}")
            if sobra:
                detalle.append(f"columnas de más {sorted(sobra)}")
            if not rows:
                r["cols"] = False
                detalle.append("seed vacío")

            r["src"] = declarados.get(t) == f"bronze.{t}"
            if not r["src"]:
                detalle.append("no declarada como source con meta.legacy_table")

            db_cols = [x[0] for x in con.execute(
                "select column_name from information_schema.columns where table_schema='raw' and table_name=? order by ordinal_position",
                [t]).fetchall()]
            if db_cols:
                n_db = con.execute(f'select count(*) from raw."{t}"').fetchone()[0]
                r["db"] = db_cols == header and n_db == len(rows)
                if not r["db"]:
                    detalle.append(f"DuckDB: {n_db} filas / cols {db_cols} vs CSV {len(rows)} / {header}")
            else:
                detalle.append("no está en DuckDB (schema raw)")

            if t in FIDELIDAD:
                orig, modo = FIDELIDAD[t]
                if modo == "IDENTICA":
                    ok = sha(orig) == sha(seeds[t])
                else:
                    h0, r0 = leer_csv(orig)
                    idx = [header.index(c) for c in h0] if set(h0) <= set(header) else None
                    ok = idx is not None and len(r0) == len(rows) and all(
                        [row[i] for i in idx] == o for row, o in zip(rows, r0))
                r["fid"] = ("ok-" if ok else "MAL-") + modo[0]
                if not ok:
                    detalle.append(f"datos distintos al original ({modo}) {orig.relative_to(REPO)}")
        else:
            detalle.append("no existe seed")

        r["doc"] = f"bronze.{t}" in doc
        if not r["doc"]:
            detalle.append("no aparece en LEGACY_TABLES.md")

        ok_all = r["seed"] and r["cols"] and r["src"] and r["db"] and r["doc"] and r["fid"] in ("n/a", "ok-I", "ok-A")
        fallas += not ok_all
        fallas_legacy += not ok_all
        m = lambda b: "ok" if b else "FALLA"
        print(f"{t:<32} {m(r['seed']):<5} {m(r['cols']):<5} {m(r['src']):<5} {m(r['db']):<5} {r['fid']:<7} {m(r['doc']):<4} {filas}"
              + (f"   <- {'; '.join(detalle)}" if detalle else ""))

    extras = set(seeds) - set(legacy)
    print("-" * 82)
    for e in sorted(extras):
        permitido = e in EXTRAS_PERMITIDOS
        fallas += not permitido
        print(f"seed sin tabla legacy: {e:<24} {'(permitido, documentado)' if permitido else 'FALLA: no documentado'}")

    print(f"\n{len(legacy)} tablas legacy revisadas · {len(legacy) - fallas_legacy} migradas correctamente")
    if fallas:
        print(f"FALLARON {fallas} verificaciones")
        sys.exit(1)
    print("Migración de bronze verificada 1:1.")


if __name__ == "__main__":
    main()
