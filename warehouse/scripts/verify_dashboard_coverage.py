"""Verifica que cada dashboard de projects/ tenga un reporte gold que replique su dataset.

Nivel 1 (siempre): por cada CSV de dashboard, el modelo gold existe, tiene las mismas
columnas en el mismo orden y la misma familia de tipo que el CSV, trae filas y su
contrato está forzado (manifest de dbt).

Nivel 2 (--e2e): exporta cada modelo gold a CSV en una copia temporal del repo,
sustituye el CSV del proyecto y ejecuta su run_analysis.py. Prueba que el dashboard
se construye con datos que salen del warehouse. Nunca toca projects/. Requiere
pandas, numpy, matplotlib y scikit-learn en el intérprete de --python
(por defecto el mismo que corre este script).

Uso (desde warehouse/, con `dbt run` y `dbt parse` ya ejecutados):
    python scripts/verify_dashboard_coverage.py [--db xia_warehouse.duckdb] [--e2e [--python /ruta/a/python]]
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

WAREHOUSE = Path(__file__).resolve().parents[1]
REPO = WAREHOUSE.parent
PROJECTS = REPO / "projects"

# proyecto -> [(csv que consume o produce el dashboard, modelo gold)]
COBERTURA = {
    "01-sales-performance-dashboard": [("ventas_diarias.csv", "rpt_ventas_diarias"), ("metas_mensuales.csv", "rpt_metas_mensuales")],
    "02-funnel-fuga-ventas": [("funnel_semanal.csv", "rpt_funnel_semanal")],
    "03-scorecard-metas-vs-resultados": [("kpi_historico.csv", "rpt_kpi_historico"), ("scorecard.csv", "rpt_scorecard")],
    "04-prediccion-churn": [("clientes.csv", "rpt_clientes_churn")],
    "05-segmentacion-rfm": [("transacciones.csv", "rpt_transacciones")],
    "06-elasticidad-precios": [("precio_demanda.csv", "rpt_precio_demanda")],
    "07-forecast-demanda-inventario": [("demanda_diaria.csv", "rpt_demanda_diaria"), ("inventario_actual.csv", "rpt_inventario_actual")],
    "08-flujo-caja-cartera": [("facturas.csv", "rpt_facturas")],
    "09-roi-marketing-canal": [("marketing_canales.csv", "rpt_marketing_canales")],
    "10-reporte-ejecutivo-mensual": [("transacciones.csv", "rpt_transacciones_ejecutivo")],
    "11-consolidacion-fuente-verdad": [("fuente_unica.csv", "rpt_fuente_unica"), ("revision_manual_monto_faltante.csv", "rpt_revision_manual_monto_faltante")],
    "12-nps-causa-raiz": [("encuestas_nps.csv", "rpt_encuestas_nps")],
    "13-data-health-check": [
        ("scorecard_calidad_tablas.csv", "rpt_scorecard_calidad_tablas"),
        ("reglas_validacion.csv", "rpt_reglas_validacion"),
        ("plan_remediacion.csv", "rpt_plan_remediacion"),
    ],
}

# En 11 y 13 el CSV es la SALIDA del análisis (su entrada son exports crudos), así que no hay
# dashboard que alimentar desde gold: solo se compara la forma.
SOLO_FORMA = {"11-consolidacion-fuente-verdad", "13-data-health-check"}

# (csv, columna) -> tipo del warehouse cuando el tipo que deduce DuckDB del CSV es un artefacto
TIPO_ESPERADO = {
    ("revision_manual_monto_faltante.csv", "monto_mxn"): "DOUBLE",  # columna 100% vacía en el CSV: se deduce VARCHAR
    ("marketing_canales.csv", "ticket_promedio_mxn"): "DOUBLE",     # en el CSV vienen enteros; es un promedio
    ("marketing_canales.csv", "meses_retencion_prom"): "DOUBLE",    # idem
}

# Dashboards cuyo run_analysis.py trae supuestos fijos del dataset autónomo del proyecto y por eso
# no se construyen (todavía) con los datos del warehouse. No son fallas del reporte gold: cumple
# el contrato de columnas y tipos. Si uno empieza a pasar, el script avisa que se quite de aquí.
LIMITACIONES_CONOCIDAS = {
    "07-forecast-demanda-inventario": "paleta de color para exactamente 5 categorías; el catálogo del warehouse tiene 8",
    "08-flujo-caja-cartera": "TODAY fijo en 2026-08-31 y narrativa de 8 clientes; las facturas del warehouse terminan en 2025-12",
    "10-reporte-ejecutivo-mensual": "CATEGORIA_ORDEN fija (Línea Premium/Estándar/Económica/Servicios postventa); el warehouse usa otro catálogo",
}


def nivel_1(con, manifest):
    fallas = []
    for proyecto, pares in COBERTURA.items():
        for csv, modelo in pares:
            etiqueta = f"{proyecto[:2]} {csv:38s} <- gold.{modelo}"
            problemas = []
            existe = con.execute("select count(*) from information_schema.tables where table_schema='gold' and table_name=?", [modelo]).fetchone()[0]
            if not existe:
                fallas.append(etiqueta + "  NO EXISTE")
                print("FAIL", etiqueta, "no existe")
                continue
            esperado = con.execute(f"describe select * from read_csv_auto('{PROJECTS / proyecto / 'data' / csv}')").fetchall()
            real = con.execute(f"describe select * from gold.{modelo}").fetchall()
            if [c[0] for c in esperado] != [c[0] for c in real]:
                problemas.append(f"columnas {[c[0] for c in real]} != {[c[0] for c in esperado]}")
            else:
                for (nombre, t_csv, *_), (_, t_gold, *_) in zip(esperado, real):
                    t_csv = TIPO_ESPERADO.get((csv, nombre), t_csv)
                    if t_csv != t_gold:
                        problemas.append(f"{nombre}: {t_gold} != {t_csv}")
            filas = con.execute(f"select count(*) from gold.{modelo}").fetchone()[0]
            if filas == 0:
                problemas.append("0 filas")
            nodo = manifest["nodes"].get(f"model.xia_warehouse.{modelo}", {})
            if not nodo.get("contract", {}).get("enforced"):
                problemas.append("contrato no forzado en dbt")
            estado = "FAIL" if problemas else "ok  "
            print(estado, etiqueta, f"({filas} filas)", "; ".join(problemas))
            if problemas:
                fallas.append(etiqueta + "  " + "; ".join(problemas))
    return fallas


def nivel_2(con, python):
    fallas = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(REPO / "_lib", tmp / "_lib")
        for proyecto, pares in COBERTURA.items():
            if proyecto in SOLO_FORMA:
                print("skip", proyecto[:2], "(el CSV es salida del análisis, no entrada)")
                continue
            destino = tmp / "projects" / proyecto
            shutil.copytree(PROJECTS / proyecto, destino)
            for csv, modelo in pares:
                con.execute(f"copy (select * from gold.{modelo}) to '{destino / 'data' / csv}' (header, delimiter ',')")
            r = subprocess.run([python, "run_analysis.py"], cwd=destino, capture_output=True, text=True)
            ok = r.returncode == 0 and (destino / "dashboard.html").stat().st_mtime > (PROJECTS / proyecto / "dashboard.html").stat().st_mtime - 1
            conocida = LIMITACIONES_CONOCIDAS.get(proyecto)
            if ok and conocida:
                print("ok  ", proyecto[:2], "ya se construye: quitarlo de LIMITACIONES_CONOCIDAS")
                fallas.append(f"{proyecto}: limitación conocida resuelta, actualizar la lista")
            elif ok:
                print("ok  ", proyecto[:2], "run_analysis.py sobre datos de gold")
            elif conocida:
                print("known", proyecto[:2], "no se construye con datos de gold:", conocida)
            else:
                detalle = " | ".join((r.stderr or r.stdout).strip().splitlines()[-3:])
                print("FAIL", proyecto[:2], detalle)
                fallas.append(f"{proyecto}: {detalle}")
    return fallas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WAREHOUSE / "xia_warehouse.duckdb"))
    ap.add_argument("--e2e", action="store_true")
    ap.add_argument("--python", default=sys.executable, help="intérprete con pandas/sklearn para --e2e")
    args = ap.parse_args()

    manifest = json.loads((WAREHOUSE / "target" / "manifest.json").read_text())
    con = duckdb.connect(args.db, read_only=True)

    print("== Nivel 1: forma del reporte gold vs CSV del dashboard")
    fallas = nivel_1(con, manifest)
    if args.e2e:
        print("\n== Nivel 2: los dashboards se construyen con datos de gold")
        fallas += nivel_2(con, args.python)

    total = sum(len(p) for p in COBERTURA.values())
    print(f"\n{len(COBERTURA)} dashboards, {total} datasets -> {len(fallas)} fallas")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
