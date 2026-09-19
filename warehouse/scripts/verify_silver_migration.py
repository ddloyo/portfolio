"""Verifica que la migración de database/schema/02_silver.sql a modelos de dbt
sea 1:1. Es una herramienta TEMPORAL: se borra junto con los archivos legacy
cuando termine la migración (ver database/LEGACY_TABLES.md).

Para cada tabla `silver.<t>` del DDL legacy comprueba:
  1. existe el modelo dbt que le corresponde y está materializado en DuckDB
  2. tiene todas las columnas del DDL (con los renombres documentados) y filas
  3. su PRIMARY KEY tiene test de dbt (unique / unique_combination + not_null)
     Y es única en los datos (se cuenta directo en DuckDB, no se confía en el test)
  4. cada FOREIGN KEY tiene su test `relationships` hacia el modelo correcto
     Y no hay huérfanos en los datos (también directo en DuckDB)
  5. aparece en database/LEGACY_TABLES.md

Correspondencia de nombres: dim_X -> dim_X, fact_X -> fct_X (más las excepciones
de MODELO_EXCEPCIONES). Las columnas extra que el modelo agrega sobre el DDL
están permitidas (denormalizaciones y llaves naturales); solo faltar falla.

Uso (desde warehouse/, después de `dbt test`, que genera target/manifest.json):
    python3 scripts/verify_silver_migration.py [ruta_a_la_base.duckdb]
"""
import json
import re
import sys
from pathlib import Path

import duckdb

WAREHOUSE = Path(__file__).resolve().parent.parent
REPO = WAREHOUSE.parent
LEGACY_SQL = REPO / "database" / "schema" / "02_silver.sql"
LEGACY_DOC = REPO / "database" / "LEGACY_TABLES.md"
MANIFEST = WAREHOUSE / "target" / "manifest.json"
DB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WAREHOUSE / "xia_warehouse.duckdb"

MODELO_EXCEPCIONES = {"venta_sucursal_pendiente_revision": "fct_venta_sucursal_pendiente_revision"}
# (tabla legacy, columna legacy) -> columna en el modelo. Motivo: el sufijo _origen venía
# del diseño multi-sistema; con un solo sistema fuente es ruido.
RENOMBRES = {
    ("dim_cliente", "cliente_id_origen"): "cliente_id",
    ("fact_factura", "factura_id_origen"): "factura_id",
    ("fact_encuesta_nps", "respuesta_id_origen"): "respuesta_id",
}


def modelo(t):
    if t in MODELO_EXCEPCIONES:
        return MODELO_EXCEPCIONES[t]
    return "fct_" + t[len("fact_"):] if t.startswith("fact_") else t


def col(t, c):
    return RENOMBRES.get((t, c), c)


def tablas_legacy():
    sql = LEGACY_SQL.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"CREATE TABLE silver\.(\w+) \((.*?)\n\);", sql, re.DOTALL):
        cols, pks, fks = [], [], []
        for line in m.group(2).splitlines():
            line = line.split("--")[0].rstrip().rstrip(",")
            if not line.strip():
                continue
            mm = re.match(r"^\s*PRIMARY KEY\s*\(([^)]*)\)", line)
            if mm:
                pks += [c.strip() for c in mm.group(1).split(",")]
                continue
            if re.match(r"^\s*UNIQUE\s*\(", line):
                continue
            c = re.match(r'^\s*"?([A-Za-z_]\w*)"?\s+\w+', line)
            if not c:
                continue
            cols.append(c.group(1))
            if "PRIMARY KEY" in line:
                pks.append(c.group(1))
            r = re.search(r"REFERENCES silver\.(\w+)\((\w+)\)", line)
            if r:
                fks.append((c.group(1), r.group(1), r.group(2)))
        out[m.group(1)] = {"cols": cols, "pks": pks, "fks": fks}
    return out


def tests_por_modelo():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    res = {}
    for n in m["nodes"].values():
        if n["resource_type"] != "test" or "test_metadata" not in n:
            continue
        tm, model = n["test_metadata"], (n.get("attached_node") or "").split(".")[-1]
        k = tm.get("kwargs", {})
        r = res.setdefault(model, {"unique": set(), "not_null": set(), "combo": set(), "rel": set()})
        if tm["name"] == "unique":
            r["unique"].add(k["column_name"])
        elif tm["name"] == "not_null":
            r["not_null"].add(k["column_name"])
        elif tm["name"] == "unique_combination_of_columns":
            r["combo"].add(frozenset(k["combination_of_columns"]))
        elif tm["name"] == "relationships":
            destino = re.search(r"ref\('(\w+)'\)", k["to"])  # las que apuntan a un source() no cuentan
            if destino:
                r["rel"].add((k["column_name"], destino.group(1), k["field"]))
    return res


def main():
    if not DB.exists() or not MANIFEST.exists():
        sys.exit("Falta la base DuckDB o target/manifest.json: corre `dbt seed`, `dbt run` y `dbt test` primero.")
    legacy = tablas_legacy()
    tests = tests_por_modelo()
    doc = LEGACY_DOC.read_text(encoding="utf-8") if LEGACY_DOC.exists() else ""
    con = duckdb.connect(str(DB), read_only=True)

    print(f"{'tabla legacy':<36} {'modelo dbt':<40} cols  filas  pk    fk    doc")
    print("-" * 112)
    fallas = 0
    for t, d in legacy.items():
        mdl, detalle = modelo(t), []
        db_cols = [x[0] for x in con.execute(
            "select column_name from information_schema.columns where table_schema in ('marts','intermediate') and table_name=?", [mdl]).fetchall()]
        esquema = con.execute("select table_schema from information_schema.tables where table_name=? and table_schema in ('marts','intermediate')", [mdl]).fetchone()
        if not db_cols or not esquema:
            print(f"{t:<36} {mdl:<40} FALLA (no existe el modelo en DuckDB)")
            fallas += 1
            continue
        ref = f'{esquema[0]}."{mdl}"'
        n = con.execute(f"select count(*) from {ref}").fetchone()[0]
        falta = [col(t, c) for c in d["cols"] if col(t, c) not in db_cols]
        ok_cols = not falta and n > 0
        if falta:
            detalle.append(f"faltan columnas {falta}")
        if n == 0:
            detalle.append("tabla vacía")

        # PK: test + datos
        pks = [col(t, c) for c in d["pks"]]
        t_mdl = tests.get(mdl, {"unique": set(), "not_null": set(), "combo": set(), "rel": set()})
        pk_test = all(c in t_mdl["not_null"] for c in pks) and (
            (len(pks) == 1 and pks[0] in t_mdl["unique"]) or (len(pks) > 1 and frozenset(pks) in t_mdl["combo"]))
        dup = con.execute(f"select count(*) - count(distinct ({', '.join(pks)})) from {ref}").fetchone()[0] if ok_cols else -1
        ok_pk = pk_test and dup == 0
        if not pk_test:
            detalle.append(f"PK {pks} sin test unique/not_null")
        if dup != 0:
            detalle.append(f"PK con {dup} duplicados")

        # FK: test + datos
        ok_fk, n_fk = True, 0
        for c, destino, campo in d["fks"]:
            c2, dest_mdl, campo2 = col(t, c), modelo(destino), col(destino, campo)
            n_fk += 1
            if (c2, dest_mdl, campo2) not in t_mdl["rel"]:
                ok_fk = False
                detalle.append(f"FK {c2}->{dest_mdl}.{campo2} sin test relationships")
                continue
            dest_schema = con.execute("select table_schema from information_schema.tables where table_name=? and table_schema in ('marts','intermediate')", [dest_mdl]).fetchone()
            huerf = con.execute(
                f'select count(*) from {ref} c where c."{c2}" is not null and not exists '
                f'(select 1 from {dest_schema[0]}."{dest_mdl}" d where d."{campo2}" = c."{c2}")').fetchone()[0]
            if huerf:
                ok_fk = False
                detalle.append(f"FK {c2}: {huerf} huérfanos")

        ok_doc = f"silver.{t}" in doc
        if not ok_doc:
            detalle.append("no aparece en LEGACY_TABLES.md")

        todo = ok_cols and ok_pk and ok_fk and ok_doc
        fallas += not todo
        m = lambda b: "ok" if b else "FALLA"
        print(f"{t:<36} {mdl:<40} {m(ok_cols):<5} {n:<6} {m(ok_pk):<5} {(m(ok_fk) + f'({n_fk})'):<8} {m(ok_doc)}"
              + (f"   <- {'; '.join(detalle)}" if detalle else ""))

    print("-" * 112)
    print(f"{len(legacy)} tablas legacy revisadas · {len(legacy) - fallas} migradas correctamente")
    if fallas:
        print(f"FALLARON {fallas} tablas")
        sys.exit(1)
    print("Migración de silver verificada 1:1.")


if __name__ == "__main__":
    main()
