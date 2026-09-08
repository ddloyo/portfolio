"""
Data Health Check: audita las 4 tablas del "mini-ERP" simulado (clientes,
productos, calendario, facturas) contra un catálogo de reglas de validación
documentadas -- completitud, unicidad, formato/validez, integridad
referencial y consistencia de cálculo -- sin conocer de antemano qué
inyectó data/generate_data.py. Cada regla produce un renglón auditable
(tabla, campo, tipo, severidad, filas afectadas, puntos de impacto) que
alimenta el score de calidad por tabla y el plan de remediación.

Genera:
  data/scorecard_calidad_tablas.csv -- 1) scorecard de calidad por tabla
  data/reglas_validacion.csv        -- 4) catálogo de reglas + resultado de cada una
  data/plan_remediacion.csv         -- 3) plan de remediación priorizado
  dashboard.html                    -- 2) issues priorizados + visualización por tabla

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) -- se usa como vista previa en el README. Para
regenerarla tras un cambio visual: abre dashboard.html en el navegador y
toma un screenshot de la página completa.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import numpy as np
import pandas as pd
from xia_style import STATUS
import dashboard as dash

# ============================================================================
# Carga: todo como texto crudo (dtype=str). Si se deja que pandas infiera
# tipos, silenciosamente convierte "$1,234.50" a NaN o descarta el problema
# -- exactamente lo que una auditoría de calidad no debe hacer.
# ============================================================================
clientes = pd.read_csv(ROOT / "data" / "clientes.csv", dtype=str)
productos = pd.read_csv(ROOT / "data" / "productos.csv", dtype=str)
calendario = pd.read_csv(ROOT / "data" / "calendario.csv", dtype=str)
facturas = pd.read_csv(ROOT / "data" / "facturas.csv", dtype=str)

TABLAS = {"clientes": clientes, "productos": productos, "calendario": calendario, "facturas": facturas}

CIUDADES_CANON = {"Ciudad de México", "Guadalajara", "Monterrey", "Puebla", "Tijuana",
                   "Querétaro", "León", "Mérida", "Toluca", "Cancún"}
SEGMENTOS_CANON = {"Premium", "Estándar", "Básico"}
CATEGORIAS_CANON = {"Electrónica", "Ropa", "Hogar", "Alimentos", "Juguetes", "Deportes", "Belleza", "Papelería"}
MONEDAS_CANON = {"MXN", "USD"}

SEVERITY_WEIGHT = {"critical": 65, "high": 40, "medium": 20, "low": 9, "info": 0}
SEVERITY_LABEL = {"critical": "Crítica", "high": "Alta", "medium": "Media", "low": "Baja", "info": "Informativa"}

RULE_TYPE_LABEL = {
    "completeness": "Completitud", "uniqueness": "Unicidad", "validity": "Validez/Formato",
    "integrity": "Integridad referencial", "consistency": "Consistencia de cálculo", "orphan_field": "Campo huérfano",
}

REMEDIATION_TEMPLATE = {
    "completeness": "Hacer obligatorio `{campo}` en el formulario/ETL de origen; las {n} filas ya capturadas van a una cola de revisión manual, no a imputación automática.",
    "uniqueness": "Definir `{campo}` (o la combinación de campos) como llave única en la base; deduplicar las {n} filas detectadas antes de usar la tabla en cualquier agregado.",
    "validity": "Agregar validación de formato/rango en el punto de captura para `{campo}`; poner en cuarentena o corregir las {n} filas fuera de rango.",
    "integrity": "Bloquear la inserción de filas cuyo `{campo}` no exista en el catálogo maestro; investigar el origen de las {n} referencias huérfanas (¿catálogo desactualizado o borrado sin cascada?).",
    "consistency": "Recalcular `{campo}` desde sus componentes en vez de aceptar el valor capturado manualmente; revisar las {n} filas donde no cuadra con la fórmula esperada.",
    "orphan_field": "Confirmar con el dueño del sistema si `{campo}` sigue en uso; si no, retirarlo del esquema para que ningún reporte futuro asuma que existe.",
}

rules = []  # cada rule: dict con tabla, campo, tipo, severidad, descripcion, n_filas, n_fallas, pct_fallas, impacto_pts


def add_rule(tabla, campo, tipo, severidad, descripcion, n_filas, n_fallas):
    pct = round(100 * n_fallas / n_filas, 2) if n_filas else 0.0
    impacto = round(SEVERITY_WEIGHT[severidad] * (n_fallas / n_filas), 2) if n_filas else 0.0
    rules.append({
        "tabla": tabla, "campo": campo, "tipo": tipo, "tipo_label": RULE_TYPE_LABEL[tipo],
        "severidad": severidad, "severidad_label": SEVERITY_LABEL[severidad], "descripcion": descripcion,
        "n_filas": n_filas, "n_fallas": n_fallas, "pct_fallas": pct, "impacto_pts": impacto,
    })


def is_null(series):
    return series.isna() | (series.astype(str).str.strip() == "") | (series.astype(str).str.lower() == "nan")


def parse_number(s):
    """Convierte texto de moneda ('$1,234.50') o numérico plano a float; NaN si no se puede."""
    if pd.isna(s):
        return np.nan
    s = str(s).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


def is_dirty_currency(s):
    return isinstance(s, str) and bool(re.search(r"[$,]", s))


def parse_date_any(s, formats=("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y")):
    if pd.isna(s) or str(s).strip() == "":
        return pd.NaT, None
    s = str(s).strip()
    for fmt in formats:
        try:
            return pd.to_datetime(s, format=fmt), fmt
        except ValueError:
            continue
    return pd.NaT, None


def is_case_dirty(series, canon_set):
    """True si el valor no-nulo no hace match exacto contra el catálogo
    canónico pero sí hace match una vez normalizado (mayúsculas/espacios) --
    o sea, el dato está ahí, solo mal escrito."""
    canon_norm = {c.strip().lower(): c for c in canon_set}
    out = pd.Series(False, index=series.index)
    for i, v in series.items():
        if pd.isna(v) or str(v).strip() == "":
            continue
        v_str = str(v)
        if v_str in canon_set:
            continue
        if v_str.strip().lower() in canon_norm:
            out.loc[i] = True
    return out


# ============================================================================
# CLIENTES
# ============================================================================
n = len(clientes)
nulls_email = is_null(clientes["email"])
add_rule("clientes", "email", "completeness", "high", "El email no debe estar vacío -- es el canal principal de retención/cobranza.", n, int(nulls_email.sum()))

nulls_tel = is_null(clientes["telefono"])
add_rule("clientes", "telefono", "completeness", "medium", "El teléfono no debe estar vacío.", n, int(nulls_tel.sum()))

email_ok = clientes["email"].notna() & (clientes["email"].astype(str).str.strip() != "")
email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
bad_email_fmt = email_ok & ~clientes["email"].astype(str).str.strip().str.match(email_regex)
add_rule("clientes", "email", "validity", "high", "El email debe tener formato válido (usuario@dominio.tld), sin espacios.", int(email_ok.sum()), int(bad_email_fmt.sum()))

dup_id = clientes["cliente_id"].duplicated(keep=False) & clientes["cliente_id"].notna()
add_rule("clientes", "cliente_id", "uniqueness", "critical", "cliente_id debe ser único -- llave primaria del catálogo.", n, int(dup_id.sum()))

dup_email = clientes[email_ok].duplicated(subset="email", keep=False)
add_rule("clientes", "email", "uniqueness", "high", "El mismo email no debería repetirse en dos cliente_id distintos (alta duplicada).", int(email_ok.sum()), int(dup_email.sum()))

ciudad_dirty = is_case_dirty(clientes["ciudad"], CIUDADES_CANON)
add_rule("clientes", "ciudad", "validity", "medium", "ciudad debe respetar la capitalización del catálogo maestro (evita fragmentar el mismo valor en variantes).", n, int(ciudad_dirty.sum()))

segmento_dirty = is_case_dirty(clientes["segmento"], SEGMENTOS_CANON)
add_rule("clientes", "segmento", "validity", "medium", "segmento debe ser uno de {Premium, Estándar, Básico} con capitalización exacta.", n, int(segmento_dirty.sum()))

fecha_alta_parsed = clientes["fecha_alta"].apply(lambda s: parse_date_any(s))
fecha_alta_fmt = fecha_alta_parsed.apply(lambda t: t[1])
fecha_alta_no_iso = clientes["fecha_alta"].notna() & (fecha_alta_fmt != "%Y-%m-%d")
add_rule("clientes", "fecha_alta", "validity", "high", "fecha_alta debe capturarse en formato estándar ISO (YYYY-MM-DD), no mezclado con DD/MM/YYYY o MM/DD/YYYY.", n, int(fecha_alta_no_iso.sum()))

nombre_ws = clientes["nombre_completo"].astype(str).apply(lambda s: s != s.strip() or "  " in s)
add_rule("clientes", "nombre_completo", "validity", "low", "nombre_completo no debe traer espacios al inicio/final ni dobles espacios.", n, int(nombre_ws.sum()))

legacy_null = is_null(clientes["campo_legacy_crm_id"])
add_rule("clientes", "campo_legacy_crm_id", "orphan_field", "info", "Columna heredada de un CRM anterior, 100% vacía -- nunca se migró ni se usa en ningún reporte.", n, int(legacy_null.sum()))

# ============================================================================
# PRODUCTOS
# ============================================================================
n = len(productos)
dup_sku = productos["sku"].duplicated(keep=False) & productos["sku"].notna()
add_rule("productos", "sku", "uniqueness", "critical", "sku debe ser único -- llave primaria del catálogo de productos.", n, int(dup_sku.sum()))

nulls_precio = is_null(productos["precio_unitario"])
add_rule("productos", "precio_unitario", "completeness", "high", "precio_unitario no debe estar vacío -- sin él no se puede facturar ni auditar el total.", n, int(nulls_precio.sum()))

nulls_cat = is_null(productos["categoria"])
add_rule("productos", "categoria", "completeness", "medium", "categoria no debe estar vacía -- se usa para reportes de mezcla de producto.", n, int(nulls_cat.sum()))

precio_dirty_fmt = productos["precio_unitario"].apply(is_dirty_currency)
add_rule("productos", "precio_unitario", "validity", "high", "precio_unitario debe almacenarse como número plano, no como texto de moneda ('$1,234.50').", n, int(precio_dirty_fmt.sum()))

precio_num = productos["precio_unitario"].apply(parse_number)
precio_invalido = precio_num.notna() & (precio_num <= 0)
add_rule("productos", "precio_unitario", "validity", "high", "precio_unitario debe ser mayor a cero.", int(precio_num.notna().sum()), int(precio_invalido.sum()))

cat_dirty = is_case_dirty(productos["categoria"], CATEGORIAS_CANON)
add_rule("productos", "categoria", "validity", "medium", "categoria debe respetar la capitalización del catálogo maestro (8 categorías fijas).", n, int(cat_dirty.sum()))

nombre_prod_ws = productos["nombre_producto"].astype(str).apply(lambda s: s != s.strip())
add_rule("productos", "nombre_producto", "validity", "low", "nombre_producto no debe traer espacios al inicio/final.", n, int(nombre_prod_ws.sum()))

obsoleto_null = is_null(productos["campo_obsoleto_bodega_2019"])
add_rule("productos", "campo_obsoleto_bodega_2019", "orphan_field", "info", "Columna de una bodega que ya no opera, 100% vacía -- candidata a eliminarse del esquema.", n, int(obsoleto_null.sum()))

# ============================================================================
# CALENDARIO
# ============================================================================
n = len(calendario)
dup_fecha = calendario["fecha"].duplicated(keep=False) & calendario["fecha"].notna()
add_rule("calendario", "fecha", "uniqueness", "high", "fecha debe ser única -- es la llave de la dimensión de tiempo.", n, int(dup_fecha.sum()))

fechas_unicas = pd.to_datetime(calendario["fecha"], errors="coerce").dropna().dt.normalize().unique()
rango_completo = pd.date_range(min(fechas_unicas), max(fechas_unicas), freq="D")
huecos = len(rango_completo) - len(set(fechas_unicas))
add_rule("calendario", "fecha", "validity", "medium", "El rango de fechas no debe tener huecos -- cada día del periodo debe existir exactamente una vez.", len(rango_completo), max(huecos, 0))

feriado_null = is_null(calendario["es_feriado"])
add_rule("calendario", "es_feriado", "orphan_field", "info", "Columna planeada para el calendario oficial de feriados MX, 100% vacía -- nunca se pobló.", n, int(feriado_null.sum()))

MESES_CANON = {"Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"}
DIAS_CANON = {"Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"}

mes_dirty = is_case_dirty(calendario["nombre_mes"], MESES_CANON)
add_rule("calendario", "nombre_mes", "validity", "low", "nombre_mes debe respetar la capitalización estándar (p.ej. 'Enero', no 'enero' ni ' Enero ').", n, int(mes_dirty.sum()))

dia_dirty = is_case_dirty(calendario["dia_semana"], DIAS_CANON)
add_rule("calendario", "dia_semana", "validity", "low", "dia_semana debe respetar la capitalización estándar.", n, int(dia_dirty.sum()))

# ============================================================================
# FACTURAS (hechos)
# ============================================================================
n = len(facturas)

nulls_cliente = is_null(facturas["cliente_id"])
add_rule("facturas", "cliente_id", "completeness", "high", "cliente_id no debe estar vacío -- sin él la venta no se puede atribuir a ningún cliente.", n, int(nulls_cliente.sum()))

nulls_total = is_null(facturas["total"])
add_rule("facturas", "total", "completeness", "high", "total no debe estar vacío.", n, int(nulls_total.sum()))

clientes_catalogo = set(clientes["cliente_id"].dropna())
cliente_no_null = facturas["cliente_id"].notna() & (facturas["cliente_id"].astype(str).str.strip() != "")
cliente_huerfano = cliente_no_null & ~facturas["cliente_id"].isin(clientes_catalogo)
add_rule("facturas", "cliente_id", "integrity", "critical", "cliente_id debe existir en el catálogo de clientes (integridad referencial) -- si no, la venta queda huérfana en cualquier reporte por cliente.", int(cliente_no_null.sum()), int(cliente_huerfano.sum()))

skus_catalogo = set(productos["sku"].dropna())
sku_no_null = facturas["sku"].notna() & (facturas["sku"].astype(str).str.strip() != "")
sku_huerfano = sku_no_null & ~facturas["sku"].isin(skus_catalogo)
add_rule("facturas", "sku", "integrity", "critical", "sku debe existir en el catálogo de productos (integridad referencial) -- si no, la venta queda huérfana en cualquier reporte por producto/categoría.", int(sku_no_null.sum()), int(sku_huerfano.sum()))

cantidad_num = pd.to_numeric(facturas["cantidad"], errors="coerce")
cantidad_invalida = cantidad_num.notna() & (cantidad_num <= 0)
add_rule("facturas", "cantidad", "validity", "high", "cantidad debe ser mayor a cero (una devolución/nota de crédito no debería capturarse como venta negativa).", int(cantidad_num.notna().sum()), int(cantidad_invalida.sum()))

precio_fact_dirty = facturas["precio_unitario"].apply(is_dirty_currency)
add_rule("facturas", "precio_unitario", "validity", "high", "precio_unitario debe almacenarse como número plano, no como texto de moneda.", n, int(precio_fact_dirty.sum()))

moneda_dirty = is_case_dirty(facturas["moneda"], MONEDAS_CANON)
add_rule("facturas", "moneda", "validity", "medium", "moneda debe ser 'MXN' o 'USD' con capitalización exacta.", n, int(moneda_dirty.sum()))

fecha_fact_parsed = facturas["fecha"].apply(lambda s: parse_date_any(s))
fecha_fact_fmt = fecha_fact_parsed.apply(lambda t: t[1])
fecha_fact_no_iso = facturas["fecha"].notna() & (fecha_fact_fmt != "%Y-%m-%d")
add_rule("facturas", "fecha", "validity", "high", "fecha debe capturarse en formato estándar ISO (YYYY-MM-DD), no mezclado con DD/MM/YYYY o MM/DD/YYYY.", n, int(fecha_fact_no_iso.sum()))

dup_factura = facturas.duplicated(subset=["fecha", "cliente_id", "sku", "cantidad", "precio_unitario"], keep=False)
add_rule("facturas", "factura_id", "uniqueness", "high", "No debe existir la misma línea de factura (fecha + cliente + sku + cantidad + precio) capturada más de una vez.", n, int(dup_factura.sum()))

cantidad_calc = pd.to_numeric(facturas["cantidad"], errors="coerce")
precio_calc = facturas["precio_unitario"].apply(parse_number)
total_calc = facturas["total"].apply(parse_number)
esperado = (cantidad_calc * precio_calc).round(2)
comparable = total_calc.notna() & esperado.notna()
total_inconsistente = comparable & ((total_calc - esperado).abs() > 1.0)
add_rule("facturas", "total", "consistency", "critical", "total debe ser igual a cantidad × precio_unitario (tolerancia $1) -- un valor distinto implica un override manual sin recalcular (p.ej. un descuento no reflejado).", int(comparable.sum()), int(total_inconsistente.sum()))

rules_df = pd.DataFrame(rules).sort_values(["tabla", "impacto_pts"], ascending=[True, False]).reset_index(drop=True)

# ============================================================================
# Score por tabla: 100 - suma de penalizaciones (severidad x % de filas con
# falla) de cada regla aplicable a esa tabla. Los campos huérfanos (severidad
# "info") no penalizan el score -- se documentan como hallazgo de limpieza,
# no como defecto de calidad del dato ya capturado.
# ============================================================================
def status_of(score):
    if score >= 90:
        return "good", "Sano"
    if score >= 75:
        return "warning", "Atención"
    if score >= 60:
        return "serious", "En riesgo"
    return "critical", "Crítico"


scorecard = []
for tabla, df in TABLAS.items():
    penal = rules_df.loc[rules_df["tabla"] == tabla, "impacto_pts"].sum()
    score = round(max(0, 100 - penal), 1)
    status, label = status_of(score)
    n_issues = int((rules_df["tabla"] == tabla).sum())
    n_fail_rules = int(((rules_df["tabla"] == tabla) & (rules_df["n_fallas"] > 0) & (rules_df["severidad"] != "info")).sum())
    scorecard.append({
        "tabla": tabla, "filas": len(df), "score": score, "status": status, "status_label": label,
        "reglas_evaluadas": n_issues, "reglas_con_hallazgo": n_fail_rules,
    })
scorecard_df = pd.DataFrame(scorecard)

score_global = round((scorecard_df["score"] * scorecard_df["filas"]).sum() / scorecard_df["filas"].sum(), 1)
status_global, label_global = status_of(score_global)

# ---- dimensión (tipo de regla) x tabla, para el desglose visual ----------
DIMENSIONES = ["completeness", "uniqueness", "validity", "integrity", "consistency"]
dim_scores = pd.DataFrame(index=list(TABLAS.keys()), columns=DIMENSIONES, dtype=float)
for tabla in TABLAS:
    for dim in DIMENSIONES:
        sub = rules_df[(rules_df["tabla"] == tabla) & (rules_df["tipo"] == dim)]
        if sub.empty:
            dim_scores.loc[tabla, dim] = np.nan
        else:
            dim_scores.loc[tabla, dim] = round(max(0, 100 - sub["impacto_pts"].sum()), 1)

# ============================================================================
# Plan de remediación: top issues por impacto (excluye campos huérfanos,
# que van aparte porque no son un defecto del dato sino limpieza de esquema)
# ============================================================================
issues = rules_df[(rules_df["n_fallas"] > 0) & (rules_df["severidad"] != "info")].sort_values("impacto_pts", ascending=False).reset_index(drop=True)
orphans = rules_df[rules_df["tipo"] == "orphan_field"].reset_index(drop=True)

plan = []
for rank, r in enumerate(issues.itertuples(), start=1):
    accion = REMEDIATION_TEMPLATE[r.tipo].format(campo=r.campo, n=r.n_fallas)
    plan.append({
        "prioridad": rank, "tabla": r.tabla, "campo": r.campo, "tipo": r.tipo_label, "severidad": r.severidad_label,
        "filas_afectadas": r.n_fallas, "pct_filas": r.pct_fallas, "impacto_pts": r.impacto_pts,
        "accion_recomendada": accion,
    })
for r in orphans.itertuples():
    plan.append({
        "prioridad": len(plan) + 1, "tabla": r.tabla, "campo": r.campo, "tipo": r.tipo_label, "severidad": "Limpieza de esquema",
        "filas_afectadas": r.n_fallas, "pct_filas": r.pct_fallas, "impacto_pts": 0,
        "accion_recomendada": REMEDIATION_TEMPLATE["orphan_field"].format(campo=r.campo, n=r.n_fallas),
    })
plan_df = pd.DataFrame(plan)

# ============================================================================
# Exports
# ============================================================================
scorecard_df.to_csv(ROOT / "data" / "scorecard_calidad_tablas.csv", index=False)
rules_df.to_csv(ROOT / "data" / "reglas_validacion.csv", index=False)
plan_df.to_csv(ROOT / "data" / "plan_remediacion.csv", index=False)

# ============================================================================
# Interactive dashboard
# ============================================================================
tabla_order = scorecard_df.sort_values("filas", ascending=False)["tabla"].tolist()
score_colors = [STATUS[s] for s in scorecard_df.set_index("tabla").loc[tabla_order, "status"]]
dim_labels = [RULE_TYPE_LABEL[d] for d in DIMENSIONES]

n_dup_total = int(rules_df.loc[rules_df["tipo"] == "uniqueness", "n_fallas"].sum())
n_orphan_fields = int((rules_df["tipo"] == "orphan_field").sum())
worst = scorecard_df.loc[scorecard_df["score"].idxmin()]
total_filas = int(scorecard_df["filas"].sum())

STATUS_LABEL = {"good": "Sano", "warning": "Atención", "serious": "En riesgo", "critical": "Crítico", "neutral": "Neutral"}

kpis = [
    {"label": "Score de calidad global", "value": f"{score_global}/100", "status": status_global,
     "status_label": label_global, "hero": True},
    {"label": "Filas auditadas", "value": f"{total_filas:,}"},
    {"label": "Reglas de validación evaluadas", "value": f"{len(rules_df)}"},
    {"label": "Issues con hallazgo", "value": f"{len(issues)}", "status": "warning", "status_label": STATUS_LABEL["warning"]},
    {"label": "Tabla con menor score", "value": f"{worst['tabla']} ({worst['score']})", "status": worst["status"],
     "status_label": STATUS_LABEL[worst["status"]]},
    {"label": "Filas duplicadas detectadas", "value": f"{n_dup_total:,}", "status": "warning", "status_label": STATUS_LABEL["warning"]},
]

charts = [
    {
        "id": "chart_score_tabla", "type": "progress_bars", "full_width": True,
        "title": "Score de calidad por tabla",
        "subtitle": "0-100 · umbral de riesgo en 60, aceptable desde 75",
        "labels": tabla_order,
        "values": [float(v) for v in scorecard_df.set_index("tabla").loc[tabla_order, "score"]],
        "colors": score_colors, "max": 100,
    },
    {
        "id": "chart_top_issues", "type": "bar", "horizontal": True, "full_width": True,
        "title": "Top 10 issues por impacto en el score",
        "subtitle": "Severidad x % de filas afectadas -- lo que más está bajando el score, primero",
        "labels": [f"{r.tabla} · {r.campo} ({r.tipo_label})" for r in issues.head(10).itertuples()],
        "datasets": [{"label": "Impacto (pts)", "data": [round(v, 1) for v in issues.head(10)["impacto_pts"]],
                      "colors": [STATUS[{"critical": "critical", "high": "serious", "medium": "warning", "low": "neutral"}[s]]
                                 for s in issues.head(10)["severidad"]]}],
        "y_label": "Puntos de impacto",
    },
]

# ---- score por dimensión, un mini progress-bar chart por tabla (solo con
# las dimensiones que le aplican -- calendario y catálogos no tienen reglas
# de integridad/consistencia, y mostrarlas en 0 sería engañoso) -----------
drilldown_charts = []
for tabla in tabla_order:
    dims_aplicables = [(dim_labels[j], dim_scores.loc[tabla, dim]) for j, dim in enumerate(DIMENSIONES)
                        if not np.isnan(dim_scores.loc[tabla, dim])]
    dim_colors = [STATUS[status_of(v)[0]] for _, v in dims_aplicables]
    drilldown_charts.append({
        "id": f"chart_dim_{tabla}", "type": "progress_bars",
        "title": tabla.capitalize(),
        "subtitle": f"{len(dims_aplicables)} dimensiones aplicables",
        "labels": [d for d, _ in dims_aplicables],
        "values": [round(float(v), 1) for _, v in dims_aplicables],
        "colors": dim_colors, "max": 100,
    })

top = issues.iloc[0]
insights = [
    f"El health score global de la base es <b>{score_global}/100</b> ({label_global.lower()}): <b>{worst['tabla']}</b> es la tabla que más lo arrastra, con un score de <b>{worst['score']}</b>.",
    f"El issue de mayor impacto es <b>{top.campo}</b> en <b>{top.tabla}</b> ({top.descripcion.lower()}) -- {top.n_fallas} filas ({top.pct_fallas}%) no cumplen la regla, con {top.impacto_pts} puntos de impacto en el score.",
    f"Se detectaron <b>{n_dup_total:,} filas duplicadas</b> entre las 4 tablas y <b>{int(rules_df.loc[rules_df['tipo']=='integrity','n_fallas'].sum())} referencias rotas</b> (cliente_id/sku que ya no existen en su catálogo) en facturas -- ambos inflan cualquier reporte que sume filas o cruce tablas sin deduplicar/filtrar primero.",
    f"El caso más difícil de detectar a simple vista: <b>{int(total_inconsistente.sum())} facturas</b> ({round(100*total_inconsistente.sum()/comparable.sum(),1)}%) donde <code>total</code> no cuadra con <code>cantidad × precio_unitario</code> -- un override manual sin recalcular que ningún filtro de nulos o duplicados detecta.",
    f"Se identificaron <b>{n_orphan_fields} columnas huérfanas</b> (100% vacías, sin uso) en el esquema -- no penalizan el score porque no son un defecto del dato capturado, pero son limpieza de esquema pendiente.",
]

table = {
    "headers": ["#", "Tabla", "Campo", "Tipo", "Severidad", "Filas afectadas", "% filas", "Impacto (pts)", "Qué hacer primero"],
    "rows": [
        [r.prioridad, r.tabla, r.campo, r.tipo, r.severidad, f"{r.filas_afectadas:,}", f"{r.pct_filas}%",
         r.impacto_pts, r.accion_recomendada]
        for r in plan_df.head(14).itertuples()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=13,
    title="Data Health Check: Auditoría de Calidad de Datos",
    tagline="4 tablas de un mini-ERP de ventas, 33 reglas de validación documentadas, un score de calidad por tabla y el plan de qué corregir primero -- y por qué.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="bottom",
    drilldown_charts=drilldown_charts,
    drilldown_title="Score por dimensión de calidad, por tabla",
    chart_cols=2,
)

print(f"Score global: {score_global}/100 ({label_global})")
print(scorecard_df[["tabla", "filas", "score", "status_label"]].to_string(index=False))
print(f"Reglas evaluadas: {len(rules_df)} | Issues con hallazgo: {len(issues)} | Duplicados: {n_dup_total} | Columnas huérfanas: {n_orphan_fields}")
print("OK -> data/scorecard_calidad_tablas.csv, data/reglas_validacion.csv, data/plan_remediacion.csv, dashboard.html")

