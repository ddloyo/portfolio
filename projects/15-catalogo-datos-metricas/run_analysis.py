"""
Catálogo de Datos y Definición de Métricas: cataloga el warehouse dbt REAL
(warehouse/, 87 modelos + 22 fuentes) y define en lenguaje de negocio las métricas
que consumen los 19 reportes gold.

A diferencia de los otros proyectos, no hay dataset sintético que generar: la
materia prima es el snapshot que extrae data/extract_catalog.py de los artefactos de
dbt (manifest.json, catalog.json, run_results.json). Este script solo lee ese
snapshot -no necesita dbt instalado-, lo cruza con las definiciones curadas
(data/metrics.py, data/taxonomy.py, data/translations_en.py), VALIDA que todo lo
curado siga apuntando a objetos reales del warehouse, y genera:

  data/inventario_modelos.csv      -- 1) inventario: un renglón por modelo/fuente con capa, dominio,
                                         documentación, tests, linaje y dashboards que impacta
  data/diccionario_metricas.csv    -- 2) diccionario de métricas de negocio (ES)
  data/brechas_documentacion.csv   -- 3) qué documentar primero, priorizado por dashboards impactados
  dashboard.html / dashboard.en.html  -- catálogo buscable (ES / EN), generado desde catalog_template.html

Uso:
  python3 run_analysis.py                     # regenera CSV y los dos dashboards
  python3 run_analysis.py --lock-translations # tras actualizar data/translations_en.py

assets/dashboard_preview.png es una captura manual de dashboard.html (no la genera
este script) -- igual que en los otros proyectos.
"""

import argparse
import csv
import hashlib
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "data"))

import metrics as M  # noqa: E402
import taxonomy as X  # noqa: E402
from translations_en import EN  # noqa: E402

SNAPSHOT = ROOT / "data" / "catalog_snapshot.json"
LOCK = ROOT / "data" / "translations_en.lock.json"
LANGS = ("es", "en")

# ============================================================================
# Textos de la interfaz (ES / EN)
# ============================================================================
UI = {
    "es": {
        "html_lang": "es", "locale": "es-MX", "file": "dashboard.html", "other_file": "dashboard.en.html", "other_label": "English",
        "tag": "Proyecto 15 · Portafolio de demostración",
        "title": "Catálogo de Datos y Definición de Métricas",
        "page_title": "XIA · Catálogo de Datos y Definición de Métricas",
        "tagline": "El inventario navegable de un warehouse dbt real (87 modelos, 22 fuentes, 429 tests) y el diccionario que dice, en lenguaje de negocio, qué significa cada métrica y de dónde sale.",
        "brand": "XIA Insights &times; Analytics &mdash; Portfolio Demo",
        "banner_label": "Lo que encontramos",
        "banner_h": "El warehouse está bien probado pero poco explicado: {tests} tests, y solo {pct}% de sus columnas tiene descripción.",
        "banner_sub": "Catalogamos {nm} modelos y {ns} fuentes con su linaje y el estado de sus pruebas, y definimos {nmet} métricas en lenguaje de negocio. Ojo: «ventas» son {nsales} cifras distintas según el reporte — el diccionario dice cuál es cuál.",
        "kpi_cols": "Columnas con descripción", "kpi_cols_sub": "{pct}% de las columnas de los modelos", "kpi_cols_badge": "Brecha",
        "kpi_models": "Modelos catalogados", "kpi_models_sub": "+ {ns} fuentes (bronze)",
        "kpi_tests": "Tests de dbt", "kpi_tests_sub": "{p} pasan · {w} en alerta", "kpi_tests_badge": "{w} alertas esperadas",
        "kpi_desc": "Modelos con descripción", "kpi_desc_sub": "{pct}% de los modelos", "kpi_desc_badge": "Casi completo",
        "kpi_met": "Métricas definidas", "kpi_met_sub": "{k} KPIs del scorecard + {o} de negocio",
        "kpi_gold": "Reportes gold cubiertos", "kpi_gold_sub": "cada rpt_* alimenta ≥1 métrica", "kpi_gold_badge": "Completo",
        "ch1_t": "Modelos y fuentes por capa", "ch1_s": "Cuántos objetos hay en cada capa del warehouse",
        "ch2_t": "Cobertura de documentación por capa", "ch2_s": "% con descripción escrita en dbt · lo que sabe el equipo vs. lo que está escrito",
        "ch2_l1": "Modelos/fuentes con descripción", "ch2_l2": "Columnas con descripción",
        "insights_h": "Lo que dice el dato",
        "ins_docs": "<b>{d} de {m}</b> modelos tienen descripción en dbt, pero solo <b>{cd} de {ct}</b> columnas ({pct}%). En gold, {gd} de {gt} columnas están descritas — y son justo las que ve el negocio.",
        "ins_warn": "<b>{p} tests pasan y {w} quedan en alerta a propósito</b>, todos sobre <code>{nodes}</code>: son hallazgos reales de la fuente (referencias rotas y totales que no cuadran) configurados como <i>warn</i> para darles seguimiento sin bloquear el pipeline.",
        "ins_impact": "<code>{name}</code> es el modelo más crítico: alimenta <b>{k} de {kt} dashboards</b> ({down} modelos aguas abajo). Un cambio ahí se nota en casi todo el portafolio.",
        "ins_notest": "Sin ningún test: {names}. {n_bronze} de las {ns} fuentes tampoco tienen — son las que traen la suciedad a propósito.",
        "ins_sales": "«Ventas» no es un número: hay <b>{n} cifras</b> con ese nombre (ventas por equipo, ingreso ejecutivo, ingresos mensuales, ventas de sucursal, monto facturado…), con alcances distintos. Ver el cuadro comparativo en el diccionario.",
        "ins_manual": "<b>{n} de {k} KPIs del scorecard son de captura manual</b> y su fórmula no está documentada en el warehouse: hay que confirmarla con su responsable antes de compararlos con un KPI calculado.",
        "tab_inv": "Inventario de datos", "tab_met": "Diccionario de métricas de negocio",
        "search_inv": "Buscar por nombre, palabra clave, columna o descripción…", "search_met": "Buscar métrica por nombre, definición, modelo o reporte…",
        "f_layer": "Capa", "f_domain": "Dominio", "f_area": "Área", "f_computed": "Se calcula en", "all": "Todas",
        "only_warn": "Solo con tests en alerta", "only_nodesc": "Solo sin descripción", "only_notest": "Solo sin tests",
        "showing": "Mostrando {n} de {total} objetos", "showing_m": "Mostrando {n} de {total} métricas",
        "no_results": "Sin resultados con estos filtros. Prueba con otra palabra o quita un filtro.",
        "no_desc": "Sin descripción en dbt", "no_desc_long": "Este objeto no tiene descripción en dbt: es una brecha de documentación.",
        "no_tests": "Sin tests", "test_one": "test", "test_many": "tests", "alert_one": "alerta", "alert_many": "alertas",
        "contract": "Contrato",
        "h_desc": "Descripción", "h_dash": "Dashboards que dependen de él", "h_systems": "Sistemas fuente de origen", "h_metrics": "Métricas que lo usan",
        "h_up": "Aguas arriba (de qué depende)", "h_down": "Aguas abajo (quién lo usa)", "h_cols": "Columnas", "h_tests": "Tests",
        "none_up": "Nada: es una fuente cruda.", "none_down": "Nadie: es un reporte final o un modelo sin consumidores.",
        "documented": "documentadas", "c_name": "Columna", "c_type": "Tipo", "c_desc": "Descripción",
        "t_status": "Estado", "t_kind": "Tipo", "t_detail": "Qué valida", "t_sev": "Severidad", "t_fail": "Filas con hallazgo",
        "st_pass": "Pasa", "st_warn": "Alerta", "st_fail": "Falla", "yes": "Sí", "no": "No",
        "f_relation": "Relación", "f_path": "Archivo", "f_mat": "Materialización", "f_contract": "Contrato enforced", "f_domain_l": "Dominio",
        "m_calc": "Cómo se calcula", "m_caveat": "Ojo:", "m_models": "Modelos del warehouse", "m_reports": "Reportes gold", "m_columns": "Columnas del reporte",
        "m_dash": "Lo consume", "m_owner": "Responsable", "m_area": "Área", "m_target": "Meta vigente", "m_origin": "Origen",
        "dir_up": "Más es mejor", "dir_down": "Menos es mejor",
        "scope_title": "¿Por qué «ventas» no es un solo número?",
        "scope_intro": "{n} cifras del portafolio se leen como «ventas» o «ingreso», y ninguna coincide con otra. Cada una responde una pregunta distinta; el problema empieza cuando se comparan sin decir cuál es cuál.",
        "scope_headers": ["Cifra", "Pedidos (canales)", "Sucursales", "Facturas ERP", "Periodo del reporte"],
        "scope_outro": "Regla práctica: al citar una cifra de ventas, decir siempre su nombre de este diccionario. «Importe neto» es la unidad común; lo que cambia es el alcance.",
        "layer_blurb": {
            "bronze": "Tablas crudas tal como llegan de cada sistema fuente: todo texto, sin interpretar.",
            "staging": "Una vista por fuente: tipa y limpia lo mínimo, sin reglas de negocio.",
            "intermediate": "Depuración y reglas de negocio compartidas por varios modelos.",
            "marts": "Silver: dimensiones y hechos por dominio, la capa que el negocio consulta.",
            "meta": "Motor de calidad de datos: reglas, resultados por corrida, scorecard y plan de remediación.",
            "gold": "Un reporte por dashboard, con contrato enforced: mismas columnas y tipos que su CSV.",
        },
        "mat": {"source": "Tabla cruda", "table": "Tabla", "view": "Vista", "incremental": "Incremental"},
        "computed": {"warehouse": "Warehouse", "dashboard": "Dashboard", "both": "Warehouse + dashboard", "manual": "Captura manual", "plan": "Planeación"},
        "computed_long": {"warehouse": "Se calcula en el warehouse (SQL de dbt)", "dashboard": "Se calcula en el código del dashboard",
                          "both": "Existe en el warehouse y el dashboard lo recalcula", "manual": "Lo captura una persona; la fórmula la define su responsable",
                          "plan": "Insumo de planeación: alguien lo fija, no se calcula"},
        "origin": {"derivado": "Derivado en el warehouse", "captura manual": "Captura manual"},
        "footer": "Catálogo generado desde un warehouse dbt + DuckDB que corre de verdad; los datos de negocio que respalda son 100% sintéticos, generados para fines demostrativos. Servicio real: Data Storytelling Express / Micro Data Office &middot;",
        "prov": "Snapshot: dbt {v} · manifest del {d} · tests corridos el {t}.",
    },
    "en": {
        "html_lang": "en", "locale": "en-US", "file": "dashboard.en.html", "other_file": "dashboard.html", "other_label": "Español",
        "tag": "Project 15 · Portfolio Demonstration",
        "title": "Data Catalog & Metric Definitions",
        "page_title": "XIA · Data Catalog & Metric Definitions",
        "tagline": "A browsable inventory of a real dbt warehouse (87 models, 22 sources, 429 tests) and the dictionary that says, in business language, what each metric means and where it comes from.",
        "brand": "XIA Insights &times; Analytics &mdash; Portfolio Demo",
        "banner_label": "What we found",
        "banner_h": "The warehouse is well tested but thinly explained: {tests} tests, yet only {pct}% of its columns have a description.",
        "banner_sub": "We catalogued {nm} models and {ns} sources with their lineage and test status, and defined {nmet} metrics in business language. Watch out: “sales” is {nsales} different figures depending on the report — the dictionary says which is which.",
        "kpi_cols": "Columns with a description", "kpi_cols_sub": "{pct}% of the models' columns", "kpi_cols_badge": "Gap",
        "kpi_models": "Models catalogued", "kpi_models_sub": "+ {ns} sources (bronze)",
        "kpi_tests": "dbt tests", "kpi_tests_sub": "{p} pass · {w} warning", "kpi_tests_badge": "{w} expected warnings",
        "kpi_desc": "Models with a description", "kpi_desc_sub": "{pct}% of models", "kpi_desc_badge": "Nearly complete",
        "kpi_met": "Metrics defined", "kpi_met_sub": "{k} scorecard KPIs + {o} business metrics",
        "kpi_gold": "Gold reports covered", "kpi_gold_sub": "every rpt_* feeds ≥1 metric", "kpi_gold_badge": "Complete",
        "ch1_t": "Models and sources by layer", "ch1_s": "How many objects sit in each layer of the warehouse",
        "ch2_t": "Documentation coverage by layer", "ch2_s": "% with a description written in dbt · what the team knows vs. what is written down",
        "ch2_l1": "Models/sources with a description", "ch2_l2": "Columns with a description",
        "insights_h": "What the data says",
        "ins_docs": "<b>{d} of {m}</b> models have a description in dbt, but only <b>{cd} of {ct}</b> columns ({pct}%). In gold, {gd} of {gt} columns are described — and those are exactly the ones the business sees.",
        "ins_warn": "<b>{p} tests pass and {w} sit in warning on purpose</b>, all on <code>{nodes}</code>: they are real findings of the source (broken references and totals that do not add up) set to <i>warn</i> so they get followed up without blocking the pipeline.",
        "ins_impact": "<code>{name}</code> is the most critical model: it feeds <b>{k} of {kt} dashboards</b> ({down} downstream models). A change there shows up across almost the whole portfolio.",
        "ins_notest": "With no tests at all: {names}. {n_bronze} of the {ns} sources have none either — they are the ones that carry the mess on purpose.",
        "ins_sales": "“Sales” is not one number: there are <b>{n} figures</b> with that name (sales by team, executive revenue, monthly revenue, branch sales, invoiced amount…), each with a different scope. See the comparison table in the dictionary.",
        "ins_manual": "<b>{n} of {k} scorecard KPIs are manually captured</b> and their formula is not documented in the warehouse: confirm it with their owner before comparing them with a computed KPI.",
        "tab_inv": "Data inventory", "tab_met": "Business metric dictionary",
        "search_inv": "Search by name, keyword, column or description…", "search_met": "Search a metric by name, definition, model or report…",
        "f_layer": "Layer", "f_domain": "Domain", "f_area": "Area", "f_computed": "Computed in", "all": "All",
        "only_warn": "Only with tests in warning", "only_nodesc": "Only without a description", "only_notest": "Only without tests",
        "showing": "Showing {n} of {total} objects", "showing_m": "Showing {n} of {total} metrics",
        "no_results": "No results with these filters. Try another word or remove a filter.",
        "no_desc": "No description in dbt", "no_desc_long": "This object has no description in dbt: a documentation gap.",
        "no_tests": "No tests", "test_one": "test", "test_many": "tests", "alert_one": "warning", "alert_many": "warnings",
        "contract": "Contract",
        "h_desc": "Description", "h_dash": "Dashboards that depend on it", "h_systems": "Source systems of origin", "h_metrics": "Metrics that use it",
        "h_up": "Upstream (what it depends on)", "h_down": "Downstream (who uses it)", "h_cols": "Columns", "h_tests": "Tests",
        "none_up": "Nothing: it is a raw source.", "none_down": "No one: it is a final report or a model with no consumers.",
        "documented": "documented", "c_name": "Column", "c_type": "Type", "c_desc": "Description",
        "t_status": "Status", "t_kind": "Type", "t_detail": "What it checks", "t_sev": "Severity", "t_fail": "Rows with a finding",
        "st_pass": "Pass", "st_warn": "Warning", "st_fail": "Fail", "yes": "Yes", "no": "No",
        "f_relation": "Relation", "f_path": "File", "f_mat": "Materialization", "f_contract": "Enforced contract", "f_domain_l": "Domain",
        "m_calc": "How it is calculated", "m_caveat": "Watch out:", "m_models": "Warehouse models", "m_reports": "Gold reports", "m_columns": "Report columns",
        "m_dash": "Consumed by", "m_owner": "Owner", "m_area": "Area", "m_target": "Current target", "m_origin": "Origin",
        "dir_up": "Higher is better", "dir_down": "Lower is better",
        "scope_title": "Why isn't “sales” a single number?",
        "scope_intro": "{n} figures in the portfolio read as “sales” or “revenue”, and none matches another. Each answers a different question; the trouble starts when they are compared without saying which is which.",
        "scope_headers": ["Figure", "Orders (channels)", "Branches", "ERP invoices", "Report period"],
        "scope_outro": "Rule of thumb: when quoting a sales figure, always use its name from this dictionary. “Net sales amount” is the common unit; what changes is the scope.",
        "layer_blurb": {
            "bronze": "Raw tables as they arrive from each source system: all text, uninterpreted.",
            "staging": "One view per source: minimal typing and cleaning, no business rules.",
            "intermediate": "Cleaning and business rules shared by several models.",
            "marts": "Silver: dimensions and facts by domain, the layer the business queries.",
            "meta": "Data quality engine: rules, per-run results, scorecard and remediation plan.",
            "gold": "One report per dashboard, with an enforced contract: same columns and types as its CSV.",
        },
        "mat": {"source": "Raw table", "table": "Table", "view": "View", "incremental": "Incremental"},
        "computed": {"warehouse": "Warehouse", "dashboard": "Dashboard", "both": "Warehouse + dashboard", "manual": "Manual capture", "plan": "Planning"},
        "computed_long": {"warehouse": "Computed in the warehouse (dbt SQL)", "dashboard": "Computed in the dashboard's code",
                          "both": "Exists in the warehouse and the dashboard recomputes it", "manual": "Captured by a person; the formula is defined by its owner",
                          "plan": "Planning input: someone sets it, it is not calculated"},
        "origin": {"derivado": "Derived in the warehouse", "captura manual": "Manual capture"},
        "footer": "Catalog generated from a dbt + DuckDB warehouse that really runs; the business data behind it is 100% synthetic, generated for demonstration purposes. Actual service: Data Storytelling Express / Micro Data Office &middot;",
        "prov": "Snapshot: dbt {v} · manifest from {d} · tests run on {t}.",
    },
}


def die(msg):
    sys.exit(f"ERROR: {msg}")


def norm_text(s):
    return " ".join(s.split())


def sha(s):
    return hashlib.sha1(norm_text(s).encode("utf-8")).hexdigest()[:10]


# ============================================================================
# Carga y validación
# ============================================================================
if not SNAPSHOT.exists():
    die("falta data/catalog_snapshot.json. Corre: python3 data/extract_catalog.py (ver README).")
snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
nodes = snap["nodes"]
by_id = {n["id"]: n for n in nodes}
prov = snap["provenance"]

# ---- dominio de cada objeto -------------------------------------------------
def domain_of(n):
    layer = n["layer"]
    if layer == "marts":
        dom = n["group"]
    elif layer == "staging":
        dom = X.STAGING_DOMAIN.get(n["id"])
    elif layer == "intermediate":
        dom = X.INTERMEDIATE_DOMAIN.get(n["id"])
    elif layer == "gold":
        dom = X.GOLD_DOMAIN.get(n["group"])
    elif layer == "meta":
        dom = "calidad"
    else:  # bronze: el dominio de la primera vista de staging que la lee
        dom = next((domain_of(by_id[d]) for d in n["downstream"] if by_id[d]["layer"] == "staging"), None)
    if dom not in X.DOMAINS:
        die(f"'{n['id']}' ({layer}) no tiene dominio en data/taxonomy.py: agrégalo (o revisa la carpeta '{n['group']}').")
    return dom


for n in nodes:
    n["domain"] = domain_of(n)

# ---- linaje transitivo: dashboards que dependen de un objeto y sistemas que lo originan -------
def closure(start, edge):
    seen, stack = set(), list(by_id[start][edge])
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(by_id[cur][edge])
    return seen


for n in nodes:
    down, up = closure(n["id"], "downstream"), closure(n["id"], "upstream")
    gold_down = [by_id[d] for d in down if by_id[d]["layer"] == "gold"] + ([n] if n["layer"] == "gold" else [])
    n["dashboards"] = sorted({X.dashboard_of_gold_folder(g["group"]) for g in gold_down})
    n["systems"] = sorted({by_id[u]["group"] for u in up if by_id[u]["layer"] == "bronze"})
    n["n_down_total"] = len(down)

for num in {d for n in nodes for d in n["dashboards"]}:
    if num not in X.DASHBOARDS:
        die(f"el dashboard {num:02d} no está en taxonomy.DASHBOARDS.")
for num, (slug, _, _) in X.DASHBOARDS.items():
    if not (REPO_ROOT / "projects" / slug).is_dir():
        die(f"taxonomy.DASHBOARDS[{num}] apunta a projects/{slug}, que no existe.")

# ---- traducciones: cobertura exacta + lock de hashes ---------------------------------------------
def desc_keys():
    keys = {}
    for n in nodes:
        if n["description"]:
            keys[n["id"]] = n["description"]
        for c in n["columns"]:
            if c["description"]:
                keys[f"{n['id']}.{c['name']}"] = c["description"]
    return keys


es_texts = desc_keys()
missing = sorted(set(es_texts) - set(EN))
extra = sorted(set(EN) - set(es_texts))
if missing:
    die("faltan traducciones EN en data/translations_en.py para: " + ", ".join(missing))
if extra:
    die("traducciones EN sin descripción en dbt (¿ya se borró o se renombró?): " + ", ".join(extra))

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--lock-translations", action="store_true", help="registra el hash del español traducido y sale")
args = ap.parse_args()
if args.lock_translations:
    LOCK.write_text(json.dumps({k: sha(v) for k, v in sorted(es_texts.items())}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK -> {LOCK.relative_to(ROOT)}: {len(es_texts)} descripciones registradas")
    sys.exit(0)
if LOCK.exists():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    stale = sorted(k for k, v in es_texts.items() if lock.get(k) != sha(v))
    if stale:
        print(f"AVISO: {len(stale)} descripciones cambiaron en dbt desde su traducción: {', '.join(stale[:8])}{' …' if len(stale) > 8 else ''}. "
              "Revisa data/translations_en.py y corre --lock-translations.")
else:
    print("AVISO: no hay data/translations_en.lock.json; corre python3 run_analysis.py --lock-translations.")

# ---- métricas: todo lo curado debe apuntar a algo real ---------------------------------------
gold_ids = sorted(n["id"] for n in nodes if n["layer"] == "gold")
cols_of = {n["id"]: {c["name"] for c in n["columns"]} for n in nodes}
kpi_snapshot = {k["kpi"]: k for k in snap["kpis"]}
if set(M.KPI_DEFINITIONS) != set(kpi_snapshot):
    die("KPI_DEFINITIONS no coincide con dim_kpi. Sin definición: "
        f"{sorted(set(kpi_snapshot) - set(M.KPI_DEFINITIONS))}; definidos pero ya no están en dim_kpi: {sorted(set(M.KPI_DEFINITIONS) - set(kpi_snapshot))}")

entries = []  # métricas unificadas: KPIs de dim_kpi + las de negocio de METRICS
for kpi_name in sorted(kpi_snapshot):
    kd, k = M.KPI_DEFINITIONS[kpi_name], kpi_snapshot[kpi_name]
    entries.append({
        "id": "kpi:" + kpi_name, "area": "scorecard", "computed_in": kd["computed_in"], "unit": k["unidad"],
        "direction": "down" if k["menor_es_mejor"] else "up",
        "name": M.t(kpi_name, kd["name_en"]), "definition": kd["definition"], "calc": kd["calc"],
        "models": ["dim_kpi"] + kd["models"], "reports": kd["reports"], "columns": [], "caveat": kd.get("caveat"),
        "kpi": k,
    })
entries += [dict(m, kpi=None) for m in M.METRICS]

seen_ids = set()
for m in entries:
    if m["id"] in seen_ids:
        die(f"métrica duplicada: {m['id']}")
    seen_ids.add(m["id"])
    if m["area"] not in X.DOMAINS:
        die(f"métrica {m['id']}: área '{m['area']}' no es un dominio de taxonomy.DOMAINS.")
    if m["computed_in"] not in UI["es"]["computed"]:
        die(f"métrica {m['id']}: computed_in '{m['computed_in']}' inválido.")
    for mod in m["models"]:
        if mod not in by_id or by_id[mod]["kind"] != "model":
            die(f"métrica {m['id']}: el modelo '{mod}' no existe en el warehouse.")
    for rpt in m["reports"]:
        if rpt not in by_id or by_id[rpt]["layer"] != "gold":
            die(f"métrica {m['id']}: '{rpt}' no es un reporte gold.")
    for model, col in m["columns"]:
        if col not in cols_of.get(model, ()):
            die(f"métrica {m['id']}: la columna {model}.{col} no existe.")
    m["dashboards"] = sorted({X.dashboard_of_gold_folder(by_id[r]["group"]) for r in m["reports"]})

uncovered = [g for g in gold_ids if not any(g in m["reports"] for m in entries)]
if uncovered:
    die("reportes gold sin ninguna métrica que los defina: " + ", ".join(uncovered))

entry_by_id = {m["id"]: m for m in entries}
for row in M.SALES_SCOPES:
    if row["id"] not in entry_by_id:
        die(f"SALES_SCOPES apunta a una métrica inexistente: {row['id']}")

# ============================================================================
# Estadísticas
# ============================================================================
models = [n for n in nodes if n["kind"] == "model"]
sources = [n for n in nodes if n["kind"] == "source"]
n_tests = prov["tests_total"]
tstat = prov["test_status"]
n_pass, n_warn = tstat.get("pass", 0), tstat.get("warn", 0)
if set(tstat) - {"pass", "warn"}:
    print(f"AVISO: hay tests fallando o con error en el snapshot: {tstat}")

def cols_stats(group):
    total = sum(len(n["columns"]) for n in group)
    doc = sum(1 for n in group for c in n["columns"] if c["description"])
    return doc, total


m_doc, m_total = cols_stats(models)
g_doc, g_total = cols_stats([n for n in models if n["layer"] == "gold"])
desc_models = sum(1 for n in models if n["description"])
pct = lambda a, b: round(100 * a / b) if b else 0
n_biz = len(M.METRICS)
n_kpi = len(kpi_snapshot)
n_manual = sum(1 for m in entries if m["computed_in"] == "manual")
no_test_models = [n["id"] for n in models if not n["tests"]]
no_test_sources = [n for n in sources if not n["tests"]]
warn_nodes = sorted({n["id"] for n in nodes for t in n["tests"] if t["status"] == "warn"})
n_scope = len(M.SALES_SCOPES)
top = max((n for n in models if n["layer"] != "gold"), key=lambda n: (len(n["dashboards"]), n["n_down_total"], n["id"]))

layer_stats = []
for layer in X.LAYERS:
    group = [n for n in nodes if n["layer"] == layer]
    d, t_ = cols_stats(group)
    layer_stats.append({"key": layer, "n": len(group), "with_desc": sum(1 for n in group if n["description"]),
                        "cols_doc": d, "cols_total": t_})

# ============================================================================
# CSV
# ============================================================================
def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_counts(n):
    c = defaultdict(int)
    for t in n["tests"]:
        c[t["status"]] += 1
    return c


inv_rows = []
for n in nodes:
    tc = test_counts(n)
    d, t_ = cols_stats([n])
    inv_rows.append([
        n["id"], n["kind"], n["layer"], n["domain"], n["group"] or "", n["materialized"], n["relation"],
        "sí" if n["contract"] else "no", "sí" if n["description"] else "no", t_, d, len(n["tests"]),
        tc.get("pass", 0), tc.get("warn", 0), tc.get("fail", 0) + tc.get("error", 0),
        len(n["upstream"]), len(n["downstream"]), n["n_down_total"], " ".join(f"{x:02d}" for x in n["dashboards"]),
        " ".join(n["systems"]), " ".join(n["upstream"]), " ".join(n["downstream"]), n["path"],
    ])
write_csv(ROOT / "data" / "inventario_modelos.csv",
          ["objeto", "tipo", "capa", "dominio", "grupo", "materializacion", "relacion", "contrato_enforced", "tiene_descripcion",
           "columnas", "columnas_con_descripcion", "tests", "tests_pass", "tests_warn", "tests_fail", "n_upstream", "n_downstream",
           "n_downstream_transitivo", "dashboards_impactados", "sistemas_origen", "upstream", "downstream", "archivo"], inv_rows)

met_rows = []
for m in entries:
    met_rows.append([
        m["id"], m["area"], m["name"]["es"], m["definition"]["es"], m["calc"]["es"], m["unit"], m["computed_in"],
        "|".join(m["models"]), "|".join(m["reports"]), " ".join(f"{d:02d}" for d in m["dashboards"]),
        (m.get("caveat") or {}).get("es", ""),
    ])
write_csv(ROOT / "data" / "diccionario_metricas.csv",
          ["id", "area", "nombre", "definicion", "como_se_calcula", "unidad", "donde_se_calcula", "modelos", "reportes_gold",
           "dashboards", "advertencia"], met_rows)

gaps = []
for n in nodes:
    d, t_ = cols_stats([n])
    flags = []
    if not n["description"]:
        flags.append(("sin_descripcion", "El objeto no tiene descripción en dbt"))
    if not n["tests"]:
        flags.append(("sin_tests", "Ningún test lo cubre"))
    if t_ and d < t_:
        flags.append(("columnas_sin_descripcion", f"{t_ - d} de {t_} columnas sin descripción"))
    for tipo, detalle in flags:
        gaps.append([n["id"], n["layer"], n["domain"], tipo, detalle, len(n["dashboards"]), " ".join(f"{x:02d}" for x in n["dashboards"])])
prio = {"sin_descripcion": 0, "sin_tests": 1, "columnas_sin_descripcion": 2}
gaps.sort(key=lambda g: (-g[5], prio[g[3]], g[0]))
write_csv(ROOT / "data" / "brechas_documentacion.csv",
          ["objeto", "capa", "dominio", "tipo_brecha", "detalle", "n_dashboards_impactados", "dashboards_impactados"], gaps)

# ============================================================================
# HTML
# ============================================================================
def esc(s):
    return html.escape(str(s), quote=True)


def build(lang):
    ui = UI[lang]
    short = lambda num: X.DASHBOARDS[num][1 if lang == "es" else 2]
    dash_file = "dashboard.html" if lang == "es" else "dashboard.en.html"
    dashboards = {num: {"num": num, "title": short(num), "short": short(num),
                        "href": f"../{slug}/{dash_file}"} for num, (slug, _, _) in X.DASHBOARDS.items()}
    for d in dashboards.values():  # etiqueta corta de chip: recorta títulos largos
        d["short"] = d["title"].split(":")[0] if len(d["title"]) > 34 else d["title"]

    def desc_of(key, es_text):
        return es_text if lang == "es" else EN[key]

    js_nodes = []
    for n in nodes:
        js_nodes.append({
            "id": n["id"], "kind": n["kind"], "name": n["name"], "layer": n["layer"], "layerLabel": X.LAYERS[n["layer"]][lang],
            "domain": n["domain"], "domainLabel": X.DOMAINS[n["domain"]][lang], "group": n["group"],
            "matLabel": ui["mat"][n["materialized"]], "relation": n["relation"], "path": n["path"], "contract": n["contract"],
            "desc": desc_of(n["id"], n["description"]) if n["description"] else "",
            "cols": [[c["name"], c["type"], desc_of(f"{n['id']}.{c['name']}", c["description"]) if c["description"] else ""] for c in n["columns"]],
            "tests": [{"kind": t["kind"], "detail": t["detail"], "status": t["status"], "severity": t["severity"], "failures": t["failures"]} for t in n["tests"]],
            "up": n["upstream"], "down": n["downstream"], "dashboards": n["dashboards"], "systems": n["systems"],
        })

    js_metrics = []
    for m in entries:
        unit = m["unit"] if lang == "es" else M.UNIT_EN.get(m["unit"], m["unit"])
        k = m["kpi"]
        js_metrics.append({
            "id": m["id"], "area": m["area"], "areaLabel": X.DOMAINS[m["area"]][lang], "name": m["name"][lang],
            "definition": m["definition"][lang], "calc": m["calc"][lang], "unit": unit,
            "direction": {"up": ui["dir_up"], "down": ui["dir_down"]}.get(m["direction"]),
            "computed": m["computed_in"], "computedLabel": ui["computed"][m["computed_in"]], "computedLong": ui["computed_long"][m["computed_in"]],
            "models": m["models"], "reports": m["reports"], "columns": [f"{a}.{b}" for a, b in m["columns"]],
            "dashboards": m["dashboards"], "caveat": (m.get("caveat") or {}).get(lang),
            "kpi": None if not k else {
                "owner": k["responsable"], "area": k["area"], "origin": ui["origin"][k["origen"]],
                "target": f"{k['meta']:g}%" if k["unidad"] == "%" else f"{k['meta']:,.0f} {unit}"},
        })

    scope = {"title": ui["scope_title"], "intro": ui["scope_intro"].format(n=n_scope), "outro": ui["scope_outro"], "headers": ui["scope_headers"],
             "rows": [{"id": r["id"], "name": entry_by_id[r["id"]]["name"][lang],
                       "cells": [r["orders"][lang], r["branches"][lang], r["invoices"][lang], r["period"][lang]]} for r in M.SALES_SCOPES]}

    T = {k: v for k, v in ui.items() if isinstance(v, str)}
    T["f_domain"] = ui["f_domain"]
    data = {
        "T": T, "locale": ui["locale"], "nodes": js_nodes, "metrics": js_metrics, "dashboards": dashboards, "scope": scope,
        "layers": [{"key": k, "label": v[lang], "blurb": ui["layer_blurb"][k]} for k, v in X.LAYERS.items()],
        "domains": [{"key": k, "label": v[lang]} for k, v in X.DOMAINS.items()],
        "computedKinds": [{"key": k, "label": v} for k, v in ui["computed"].items()],
    }
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    # ---- parte estática: cabecera, banner, KPIs, gráficos, insights ------------------------
    fmt = lambda tpl, **kw: tpl.format(**kw)
    banner_h = fmt(ui["banner_h"], tests=n_tests, pct=pct(m_doc, m_total))
    banner_sub = fmt(ui["banner_sub"], nm=len(models), ns=len(sources), nmet=len(entries), nsales=n_scope)
    kpis = [
        ("kpi-card kpi-hero", ui["kpi_cols"], f"{m_doc} / {m_total}", fmt(ui["kpi_cols_sub"], pct=pct(m_doc, m_total)), "b-crit", ui["kpi_cols_badge"]),
        ("kpi-card", ui["kpi_models"], str(len(models)), fmt(ui["kpi_models_sub"], ns=len(sources)), None, None),
        ("kpi-card", ui["kpi_tests"], str(n_tests), fmt(ui["kpi_tests_sub"], p=n_pass, w=n_warn), "b-warn" if n_warn else "b-good",
         fmt(ui["kpi_tests_badge"], w=n_warn) if n_warn else ui["st_pass"]),
        ("kpi-card", ui["kpi_desc"], f"{desc_models} / {len(models)}", fmt(ui["kpi_desc_sub"], pct=pct(desc_models, len(models))), "b-good", ui["kpi_desc_badge"]),
        ("kpi-card", ui["kpi_met"], str(len(entries)), fmt(ui["kpi_met_sub"], k=n_kpi, o=n_biz), None, None),
        ("kpi-card", ui["kpi_gold"], f"{len(gold_ids)} / {len(gold_ids)}", ui["kpi_gold_sub"], "b-good", ui["kpi_gold_badge"]),
    ]
    kpi_html = "\n".join(
        f'<div class="{cls}"><div class="kpi-label">{esc(lab)}</div><div class="kpi-value">{esc(val)}</div>'
        f'<div class="kpi-sub">{esc(sub)}</div>' + (f'<span class="kpi-badge {bc}">{esc(bt)}</span>' if bc else "") + "</div>"
        for cls, lab, val, sub, bc, bt in kpis)

    max_n = max(s["n"] for s in layer_stats)
    bars1 = "\n".join(
        f'<div class="bar-row"><span class="lbl">{esc(X.LAYERS[s["key"]][lang])}</span><div class="bar-line">'
        f'<div class="bar-track" role="img" aria-label="{esc(X.LAYERS[s["key"]][lang])}: {s["n"]}"><div class="bar-fill" style="width:{100 * s["n"] / max_n:.1f}%"></div></div>'
        f'<span class="bar-val">{s["n"]}</span></div></div>' for s in layer_stats)
    bars2 = "\n".join(
        f'<div class="bar-row"><span class="lbl">{esc(X.LAYERS[s["key"]][lang])}</span><div class="bar-pair">'
        f'<div class="bar-line"><div class="bar-track" role="img" aria-label="{esc(ui["ch2_l1"])}: {pct(s["with_desc"], s["n"])}%"><div class="bar-fill" style="width:{pct(s["with_desc"], s["n"])}%"></div></div><span class="bar-val">{pct(s["with_desc"], s["n"])}%</span></div>'
        f'<div class="bar-line"><div class="bar-track" role="img" aria-label="{esc(ui["ch2_l2"])}: {pct(s["cols_doc"], s["cols_total"])}%"><div class="bar-fill s2" style="width:{max(pct(s["cols_doc"], s["cols_total"]), 0.6)}%"></div></div><span class="bar-val">{pct(s["cols_doc"], s["cols_total"])}%</span></div>'
        f'</div></div>' for s in layer_stats)

    names_notest = ", ".join(f"<code>{esc(x)}</code>" for x in no_test_models) or "—"
    insights = [
        fmt(ui["ins_docs"], d=desc_models, m=len(models), cd=m_doc, ct=m_total, pct=pct(m_doc, m_total), gd=g_doc, gt=g_total),
        fmt(ui["ins_warn"], p=n_pass, w=n_warn, nodes=", ".join(warn_nodes)) if n_warn else None,
        fmt(ui["ins_impact"], name=esc(top["id"]), k=len(top["dashboards"]), kt=len(X.DASHBOARDS), down=top["n_down_total"]),
        fmt(ui["ins_notest"], names=names_notest, n_bronze=len(no_test_sources), ns=len(sources)),
        fmt(ui["ins_sales"], n=n_scope),
        fmt(ui["ins_manual"], n=n_manual, k=n_kpi),
    ]
    insights_html = "\n".join(f"<li>{i}</li>" for i in insights if i)

    top_html = f"""
  <div class="brand"><div class="mark">X</div><span>{ui['brand']}</span><a class="lang" href="{ui['other_file']}">{ui['other_label']}</a></div>
  <header class="page-head">
    <div class="tag">{esc(ui['tag'])}</div>
    <h1>{esc(ui['title'])}</h1>
    <p class="tagline">{esc(ui['tagline'])}</p>
  </header>

  <div class="minto-banner">
    <p class="minto-label">{esc(ui['banner_label'])}</p>
    <h2>{esc(banner_h)}</h2>
    <p class="minto-sub">{esc(banner_sub)}</p>
  </div>

  <div class="kpi-row">
{kpi_html}
  </div>

  <div class="charts-grid">
    <div class="chart-card"><div class="chart-head"><h3>{esc(ui['ch1_t'])}</h3><p>{esc(ui['ch1_s'])}</p></div><div class="bars">
{bars1}
    </div></div>
    <div class="chart-card"><div class="chart-head"><h3>{esc(ui['ch2_t'])}</h3><p>{esc(ui['ch2_s'])}</p></div>
      <div class="legend"><span><i style="background:var(--series-1)"></i>{esc(ui['ch2_l1'])}</span><span><i style="background:var(--series-2)"></i>{esc(ui['ch2_l2'])}</span></div>
      <div class="bars">
{bars2}
    </div></div>
  </div>

  <div class="insights-card">
    <h3>{esc(ui['insights_h'])}</h3>
    <ul class="insights">
{insights_html}
    </ul>
  </div>"""

    footer_html = f"""  <footer>
    {ui['footer']}
    <a href="mailto:xianalytics20@gmail.com">xianalytics20@gmail.com</a> &middot; WhatsApp +52 55 3566 6166
    <br>{esc(fmt(ui['prov'], v=prov['dbt_version'], d=prov['manifest_generated_at'][:10], t=prov['run_results_generated_at'][:10]))}
  </footer>"""

    page = (ROOT / "catalog_template.html").read_text(encoding="utf-8")
    for key, val in (("{{LANG}}", ui["html_lang"]), ("{{PAGE_TITLE}}", esc(ui["page_title"])), ("{{TOP}}", top_html),
                     ("{{FOOTER}}", footer_html), ("{{DATA_JSON}}", data_json)):
        page = page.replace(key, val)
    (ROOT / ui["file"]).write_text(page, encoding="utf-8")
    return ui["file"], len(page)


for lang in LANGS:
    fname, size = build(lang)
    print(f"OK -> {fname} ({size / 1024:.0f} KB)")

print(f"Catálogo: {len(models)} modelos + {len(sources)} fuentes | tests {n_tests} {tstat} | métricas {len(entries)} ({n_kpi} KPIs + {n_biz}) | "
      f"reportes gold cubiertos {len(gold_ids)}/{len(gold_ids)}")
print(f"Documentación: {desc_models}/{len(models)} modelos con descripción, {m_doc}/{m_total} columnas ({pct(m_doc, m_total)}%), gold {g_doc}/{g_total}")
print("OK -> data/inventario_modelos.csv, data/diccionario_metricas.csv, data/brechas_documentacion.csv")
