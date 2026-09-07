"""
Arma el reporte ejecutivo mensual bajo la pirámide de Minto (la respuesta
primero) y en un embudo de detalle: cifras generales de la empresa arriba,
bajando por categoría, región y subcategoría, hasta el nivel de cliente al
final. Responde seis preguntas fijas:

  1. Qué pasó este mes y qué subcategoría lo explica -- comparado contra el
     MISMO MES del año anterior (interanual), no contra el mes inmediato
     anterior: es la vara correcta para un reporte mensual que no se deje
     engañar por estacionalidad o ruido de corto plazo.
  2. Cómo va el año (YTD) contra el mismo periodo del año anterior -- se
     conserva como contraste de qué tan grave es el problema: si el mes cae
     pero el YTD sigue sano, el problema está concentrado, no generalizado.
  3. Qué subcategorías impulsan el crecimiento YTD y cuál lo frena.
  4. En qué segmento de desempeño cae cada subcategoría y qué estrategia aplica.
  5. Si la caída del mes es un evento aislado o el inicio de una tendencia.
  6. Qué clientes concretos hay que confirmar esta semana.

Estructura del dashboard (general -> detalle):
  Banner (la respuesta)
    -> Hero + KPIs: la empresa completa, mes y YTD
      -> Gráficas generales: tendencia total, YTD y variación por categoría,
         ingreso por región
        -> Detalle por subcategoría: segmentación (tendencia x volatilidad)
           y las 8 series individuales
          -> Tabla de segmentación por subcategoría (estrategia recomendada)
            -> Lista de clientes de la subcategoría causante (nivel más
               granular: a quién hay que llamar esta semana)

La fuente es transaccional: ~8,500 compras de 200 clientes (5 regiones, 4
perfiles de volumen x frecuencia) sobre 8 subcategorías. La tendencia se
generó a nivel subcategoría-cliente (data/generate_data.py); aquí se
recalcula, por regresión sobre la serie agregada de cada subcategoría, la
tendencia, volatilidad y anomalía que alimentan cada gráfica -- no se lee del
generador. La segmentación es por reglas, no k-means: ni 4 categorías ni 8
subcategorías dan masa crítica para clustering.

Genera:
  1. dashboard.html

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) -- se usa como vista previa del dashboard en el README.
Para regenerarla tras un cambio visual: abre dashboard.html en el navegador y
toma un screenshot de la página completa.

Uso:
    python3 data/generate_data.py
    python3 run_analysis.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import numpy as np
import pandas as pd
from xia_style import STATUS
import dashboard as dash

MESES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
CATEGORIA_ORDEN = ["Línea Premium", "Línea Estándar", "Línea Económica", "Servicios postventa"]
CAPACIDAD_LISTA_CLIENTES = 15

df = pd.read_csv(ROOT / "data" / "transacciones.csv")
months = sorted(df["mes"].unique())
last_month, prev_month = months[-1], months[-2]
month_dates = pd.to_datetime(months)

subcat_to_cat = df.drop_duplicates("subcategoria").set_index("subcategoria")["categoria"].to_dict()
cat_subcats = df.groupby("categoria")["subcategoria"].unique().apply(sorted).to_dict()
subcategorias = [sc for cat in CATEGORIA_ORDEN for sc in cat_subcats.get(cat, [])]
categorias = [c for c in CATEGORIA_ORDEN if c in cat_subcats]
clientes_ref = df.drop_duplicates("cliente_id").set_index("cliente_id")[["region", "perfil"]]
clientes_ref = clientes_ref.assign(perfil_corto=clientes_ref["perfil"].str.split(" (", regex=False).str[0])

pivot_cat = df.pivot_table(index="mes", columns="categoria", values="ingreso_mxn", aggfunc="sum").reindex(index=months, columns=categorias).fillna(0)
pivot_sub = df.pivot_table(index="mes", columns="subcategoria", values="ingreso_mxn", aggfunc="sum").reindex(index=months, columns=subcategorias).fillna(0)
pivot_region = df.pivot_table(index="mes", columns="region", values="ingreso_mxn", aggfunc="sum").reindex(index=months).fillna(0)

# ============================================================================
# NIVEL 1 -- LA EMPRESA: qué pasó este mes y cómo va el año
# ============================================================================
# El reporte es mensual, así que el KPI principal compara el mes actual
# contra el MISMO MES del año anterior (interanual) -- no contra el mes
# inmediato anterior, que mezcla estacionalidad/ruido de corto plazo con la
# señal real. El YTD se conserva como contraste de qué tan grave es el
# problema: si el mes cae pero el año sigue sano, el problema está
# concentrado, no generalizado.
total_by_month = pivot_cat.sum(axis=1)
total_last = total_by_month[last_month]
total_prev = total_by_month[prev_month]
var_total_pct_mom = round((total_last / total_prev - 1) * 100, 1)  # referencia de corto plazo, no el KPI principal

idx_last = months.index(last_month)
same_month_ly = months[idx_last - 12]
total_same_ly = total_by_month[same_month_ly]
var_total_pct = round((total_last / total_same_ly - 1) * 100, 1)  # KPI principal: interanual

last_dt = month_dates[-1]
current_year, current_month_num = last_dt.year, last_dt.month
prior_year = current_year - 1
ytd_current = [m for m, d in zip(months, month_dates) if d.year == current_year and d.month <= current_month_num]
ytd_prior = [m for m, d in zip(months, month_dates) if d.year == prior_year and d.month <= current_month_num]

ytd_current_total = pivot_cat.loc[ytd_current].sum().sum()
ytd_prior_total = pivot_cat.loc[ytd_prior].sum().sum()
ytd_growth_pct = round((ytd_current_total / ytd_prior_total - 1) * 100, 1)

meses_ytd_labels = [MESES_ABBR[pd.Period(m).month - 1] for m in ytd_current]
monthly_current = pivot_cat.loc[ytd_current].sum(axis=1)  # mensual, no acumulado
monthly_prior = pivot_cat.loc[ytd_prior].sum(axis=1)

# ============================================================================
# NIVEL 2 -- CATEGORÍA Y REGIÓN: los cortes generales antes de ir al producto
# ============================================================================
by_cat_last, by_cat_prev = pivot_cat.loc[last_month], pivot_cat.loc[prev_month]
cambio_abs_cat = (by_cat_last - by_cat_prev).sort_values()

ytd_by_cat_current = pivot_cat.loc[ytd_current].sum()
ytd_by_cat_prior = pivot_cat.loc[ytd_prior].sum()

ytd_by_region_current = pivot_region.loc[ytd_current].sum()
ytd_by_region_prior = pivot_region.loc[ytd_prior].sum()
region_orden = ytd_by_region_current.sort_values(ascending=False).index.tolist()

# ============================================================================
# NIVEL 3 -- SUBCATEGORÍA: quién explica el mes, quién impulsa el año, y
# segmentación por tendencia/volatilidad recalculada desde los datos
# ============================================================================
# Causante identificado en base interanual (mismo criterio que el KPI
# principal), no mes contra mes -- para que el "por qué" de arriba y el
# "cuánto" de arriba usen la misma vara de comparación.
by_sub_last, by_sub_same_ly = pivot_sub.loc[last_month], pivot_sub.loc[same_month_ly]
cambio_abs_sub_yoy = (by_sub_last - by_sub_same_ly).sort_values()
causante_sub = cambio_abs_sub_yoy.index[0]
causante_cat = subcat_to_cat[causante_sub]
cambio_causante_pct = round((by_sub_last[causante_sub] / by_sub_same_ly[causante_sub] - 1) * 100, 1)
pct_de_la_caida = round(cambio_abs_sub_yoy[causante_sub] / (total_last - total_same_ly) * 100, 0) if total_last < total_same_ly else None

ytd_by_sub_current = pivot_sub.loc[ytd_current].sum()
ytd_by_sub_prior = pivot_sub.loc[ytd_prior].sum()
ytd_delta_by_sub = ytd_by_sub_current - ytd_by_sub_prior
ytd_pct_by_sub = ((ytd_by_sub_current / ytd_by_sub_prior - 1) * 100).round(1)
motor_ytd = ytd_delta_by_sub.idxmax()   # mayor aporte en MXN al crecimiento YTD
freno_ytd = ytd_delta_by_sub.idxmin()   # mayor caída en MXN vs. el año anterior

# Tendencia, volatilidad y anomalía recalculadas por regresión sobre la serie
# agregada de cada subcategoría -- ya no son un parámetro que se lee de
# generate_data.py, sino lo que emerge de agregar ~200 clientes con su propio
# ruido y frecuencia.
x_idx = np.arange(len(months))
UMBRAL_CRECIMIENTO = 0.5    # %/mes -> "Motor de crecimiento"
UMBRAL_RIESGO = -0.05       # %/mes -> "En riesgo"
UMBRAL_ANOMALIA_Z = 2.0     # sigma -> "Alerta puntual" (gana sobre la tendencia de fondo)

ESTRATEGIAS = {
    "Alerta puntual": "Confirmar con el equipo comercial si es un cliente puntual o el inicio de una tendencia, antes de mover el forecast.",
    "Motor de crecimiento": "Proteger inventario/capacidad de esta subcategoría y replicar sus palancas de venta en las demás.",
    "En riesgo": "Revisar mezcla de precio y portafolio; definir plan de contención a 90 días.",
    "Estable / Core": "Mantener; foco en eficiencia y margen, no en crecimiento agresivo.",
}

segmentos = {}
for sc in subcategorias:
    y = pivot_sub[sc].values
    slope, _ = np.polyfit(x_idx, y, 1)
    tendencia_pct = slope / y.mean() * 100
    cambios = pivot_sub[sc].pct_change().dropna() * 100
    volatilidad_pct = cambios.std()
    hist_cambios, ultimo_cambio = cambios.iloc[:-1], cambios.iloc[-1]
    z_ultimo = (ultimo_cambio - hist_cambios.mean()) / hist_cambios.std()

    if abs(z_ultimo) > UMBRAL_ANOMALIA_Z:
        nombre, status = "Alerta puntual", "warning"
    elif tendencia_pct > UMBRAL_CRECIMIENTO:
        nombre, status = "Motor de crecimiento", "good"
    elif tendencia_pct < UMBRAL_RIESGO:
        nombre, status = "En riesgo", "critical"
    else:
        nombre, status = "Estable / Core", "neutral"

    segmentos[sc] = {
        "categoria": subcat_to_cat[sc],
        "tendencia_pct": round(tendencia_pct, 2),
        "volatilidad_pct": round(volatilidad_pct, 1),
        "z_ultimo": round(z_ultimo, 1),
        "segmento": nombre,
        "status": status,
        "estrategia": ESTRATEGIAS[nombre],
    }

subcats_atencion = [sc for sc in subcategorias if segmentos[sc]["status"] in ("warning", "critical")]

# ============================================================================
# NIVEL 4 -- CLIENTE: quién, dentro de la subcategoría causante, hay que
# confirmar esta semana (el nivel de detalle más granular del reporte)
# ============================================================================
piv_cliente_causante = (
    df[df["subcategoria"] == causante_sub]
    .pivot_table(index="cliente_id", columns="mes", values="ingreso_mxn", aggfunc="sum")
    .reindex(columns=months).fillna(0)
)
delta_cliente = piv_cliente_causante[last_month] - piv_cliente_causante[prev_month]
caida_clientes = delta_cliente[delta_cliente < 0].sort_values()
top_caida_clientes = caida_clientes.head(CAPACIDAD_LISTA_CLIENTES)
backlog_clientes = len(caida_clientes) - len(top_caida_clientes)

# ---- dashboard interactivo: banner -> empresa -> categoría/región -> ------
# ---- subcategoría -> cliente ------------------------------------------------
_contexto_causante = (
    f"y explica ~{pct_de_la_caida:.0f}% de la caída total interanual" if pct_de_la_caida is not None
    else "aunque el resto de la operación compensó esa caída"
)
banner = {
    "label": f"Respuesta ejecutiva — {last_month}",
    "headline": (
        f"El ingreso de {last_month} va {var_total_pct:+.1f}% vs. {same_month_ly} (mismo mes de {prior_year}) — "
        f"{causante_sub} ({causante_cat}) cayó {cambio_causante_pct:+.1f}% en ese mismo comparativo, {_contexto_causante}. "
        f"El YTD {current_year} confirma el panorama: {ytd_growth_pct:+.1f}% vs. {prior_year}."
    ),
    "subtext": (
        f"{len(subcats_atencion)} de {len(subcategorias)} subcategorías requieren seguimiento de dirección esta semana: "
        + ", ".join(f"{sc} ({segmentos[sc]['segmento']})" for sc in subcats_atencion)
        + f". Al final del reporte, los {len(top_caida_clientes)} clientes concretos de {causante_sub} a confirmar primero."
    ),
}

hero_kpi = {
    "label": f"Variación YTD {current_year} vs. {prior_year} (ene–{MESES_ABBR[current_month_num - 1].lower()})",
    "value": f"{ytd_growth_pct:+.1f}%",
    "status": "good" if ytd_growth_pct >= 0 else "critical",
    "status_label": "Por encima del año anterior" if ytd_growth_pct >= 0 else "Por debajo del año anterior",
}
# Mensual, no acumulado: el punto es ver el mes actual contra el mismo mes
# del año pasado sin que 7 meses buenos disimulen un mal mes reciente.
hero_chart = {
    "id": "chart_hero_ytd", "type": "line",
    "labels": meses_ytd_labels,
    "datasets": [
        {"label": f"{prior_year}", "data": [round(v, 0) for v in monthly_prior.values], "muted": True},
        {"label": f"{current_year}", "data": [round(v, 0) for v in monthly_current.values], "emphasis": True},
    ],
}

kpis = [
    {"label": f"Ingreso {last_month} (empresa)", "value": f"${total_last:,.0f} MXN"},
    {"label": f"Variación vs. {MESES_ABBR[pd.Period(same_month_ly).month - 1]} {prior_year} (interanual)", "value": f"{var_total_pct:+.1f}%",
     "status": "critical" if var_total_pct < -5 else ("warning" if var_total_pct < 0 else "good"),
     "delta_direction": "down" if var_total_pct < 0 else "up"},
    {"label": "Subcategoría causante (interanual)", "value": f"{causante_sub}", "delta": f"{cambio_causante_pct}%", "delta_direction": "down"},
    {"label": f"Ingreso YTD {current_year} (empresa)", "value": f"${ytd_current_total:,.0f} MXN"},
    {"label": "Subcategorías que requieren atención", "value": f"{len(subcats_atencion)} de {len(subcategorias)}",
     "status": "warning" if subcats_atencion else "good"},
]

# Nivel 2 (general): la empresa en el tiempo, por categoría y por región --
# antes de bajar a producto o cliente.
charts = [
    {
        "id": "chart_trend", "type": "line", "full_width": True,
        "title": "Ingreso total — 20 meses",
        "subtitle": "Consolidado, las 4 categorías y 200 clientes",
        "labels": months,
        "datasets": [{"label": "Ingreso total", "data": [round(v, 0) for v in total_by_month.values], "fill": True, "emphasis": True}],
        "y_label": "MXN",
        "marker": {"index": len(months) - 1, "label": f"{causante_sub}: {cambio_causante_pct:+.1f}%"},
    },
    {
        "id": "chart_ytd_cat", "type": "bar", "horizontal": True,
        "title": f"YTD {current_year} vs. YTD {prior_year} por categoría",
        "subtitle": f"Acumulado ene–{MESES_ABBR[current_month_num - 1].lower()} de cada año",
        "labels": categorias,
        "datasets": [
            {"label": f"YTD {prior_year}", "data": [round(v, 0) for v in ytd_by_cat_prior.values], "muted": True},
            {"label": f"YTD {current_year}", "data": [round(v, 0) for v in ytd_by_cat_current.values], "color_index": 0},
        ],
        "y_label": "MXN", "value_format": "currency",
    },
    {
        "id": "chart_cause_cat", "type": "bar", "horizontal": True,
        "title": f"Variación por categoría — {last_month} vs {prev_month}",
        "subtitle": "La vista general antes de bajar a subcategoría",
        "labels": list(cambio_abs_cat.index),
        "datasets": [{"label": "Cambio en MXN", "data": [round(v, 0) for v in cambio_abs_cat.values],
                      "colors": [STATUS["critical"] if v < 0 else STATUS["good"] for v in cambio_abs_cat.values]}],
        "y_label": "MXN",
    },
    {
        "id": "chart_region", "type": "bar", "horizontal": True,
        "title": f"YTD {current_year} vs. YTD {prior_year} por región",
        "subtitle": "Estructura comercial: dónde está concentrado el ingreso",
        "labels": region_orden,
        "datasets": [
            {"label": f"YTD {prior_year}", "data": [round(ytd_by_region_prior[r], 0) for r in region_orden], "muted": True},
            {"label": f"YTD {current_year}", "data": [round(ytd_by_region_current[r], 0) for r in region_orden], "color_index": 0},
        ],
        "y_label": "MXN", "value_format": "currency",
    },
]

# Nivel 3 (detalle de producto): segmentación de las 8 subcategorías y su
# serie mensual completa -- un paso más de detalle que las gráficas generales.
drilldown_charts = [{
    "id": "chart_segmentacion", "type": "scatter",
    "title": "Segmentación: tendencia vs. volatilidad por subcategoría",
    "subtitle": "Tendencia mensual (recalculada por regresión) vs. qué tan errático es el mes a mes",
    "points": [
        {"x": segmentos[sc]["tendencia_pct"], "y": segmentos[sc]["volatilidad_pct"],
         "label": f"{sc} ({segmentos[sc]['categoria']})", "status": segmentos[sc]["status"]}
        for sc in subcategorias
    ],
    "x_label": "Tendencia mensual (%)", "y_label": "Volatilidad mes a mes (%)",
    "x_unit": "%", "y_unit": "%",
    "point_radius": 6,
    "status_labels": {"good": "Motor de crecimiento", "neutral": "Estable / Core",
                       "warning": "Alerta puntual", "critical": "En riesgo"},
    "quadrant_lines": {"x": 0},
}]
for i, sc in enumerate(subcategorias):
    s = segmentos[sc]
    chart = {
        "id": f"chart_sub_{i}", "type": "line",
        "title": sc,
        "subtitle": f"{s['categoria']} · {s['segmento']} · tendencia {s['tendencia_pct']:+.2f}%/mes",
        "labels": months,
        "datasets": [{"label": sc, "data": [round(v, 0) for v in pivot_sub[sc].values], "color_index": i}],
        "y_label": "MXN",
    }
    if abs(s["z_ultimo"]) > UMBRAL_ANOMALIA_Z:
        chart["marker"] = {"index": len(months) - 1, "label": f"{s['z_ultimo']:+.1f}σ"}
    drilldown_charts.append(chart)

table = {
    "title": "Segmentación de subcategorías: tendencia, volatilidad y estrategia",
    "headers": ["Subcategoría", "Categoría", "Tendencia (%/mes)", "Volatilidad (%)", "Segmento", f"YTD {current_year}", "YoY YTD", "Estrategia recomendada"],
    "rows": [
        [sc, segmentos[sc]["categoria"], f"{segmentos[sc]['tendencia_pct']:+.2f}%", f"{segmentos[sc]['volatilidad_pct']:.1f}%",
         segmentos[sc]["segmento"], f"${ytd_by_sub_current[sc]:,.0f}", f"{ytd_pct_by_sub[sc]:+.1f}%",
         segmentos[sc]["estrategia"]]
        for sc in subcategorias
    ],
}

insights = [
    (f"<b>Qué pasó:</b> el ingreso de {last_month} fue ${total_last:,.0f} MXN, {var_total_pct:+.1f}% vs. {same_month_ly} (mismo mes de {prior_year}) "
     f"— la comparación que importa para medir qué tan grave es. Mes contra mes se ve peor ({var_total_pct_mom:+.1f}% vs. {prev_month}), pero es ruido de calendario: "
     f"<b>{causante_sub}</b> ({causante_cat}) es quien realmente cayó en el comparativo interanual ({cambio_causante_pct:+.1f}%)."),
    (f"<b>Así vamos en el año:</b> el YTD {current_year} acumula ${ytd_current_total:,.0f} MXN ({ytd_growth_pct:+.1f}% vs. el mismo periodo {prior_year}). "
     f"<b>{motor_ytd}</b> aporta el mayor crecimiento (${ytd_delta_by_sub[motor_ytd]:,.0f} MXN más que en {prior_year}) y "
     f"<b>{freno_ytd}</b> es la subcategoría que más retrocede en el acumulado ({ytd_pct_by_sub[freno_ytd]:+.1f}%)."),
    (f"<b>Por qué (el mes):</b> el movimiento de {causante_sub} en {last_month} es una anomalía estadística "
     f"({segmentos[causante_sub]['z_ultimo']:+.1f}&sigma; frente a su propio historial) — evidencia de evento aislado "
     f"(p. ej. un cliente grande que pausó pedidos), no de una tendencia sostenida en {causante_cat}."),
    (f"<b>Qué hacer:</b> antes de mover el forecast del trimestre, confirmar con ventas los {len(top_caida_clientes)} clientes de la lista al final "
     f"de este reporte — son los que más explican la caída en {causante_sub}. En paralelo, {freno_ytd} necesita revisión de precio/portafolio: "
     f"su rezago viene sosteniéndose desde inicios de año (tendencia {segmentos[freno_ytd]['tendencia_pct']:+.2f}%/mes), no es un mes suelto."),
    (f"{len(subcats_atencion)} de {len(subcategorias)} subcategorías están en un segmento que requiere seguimiento esta semana "
     f"({', '.join(subcats_atencion)}) — las demás sostienen el crecimiento y solo necesitan protección de capacidad, no intervención."),
]

# Nivel 4 (el más granular): los clientes concretos de la subcategoría
# causante, priorizados por el tamaño de su caída -- a quién llamar primero.
checklist = {
    "id": "clientes_causante",
    "title": f"Clientes a confirmar — {causante_sub}",
    "subtitle": (
        f"Los {len(top_caida_clientes)} clientes cuya compra en {causante_sub} más cayó entre {prev_month} y {last_month} "
        f"(de {len(caida_clientes)} con caída en total{f', quedan {backlog_clientes} más de menor tamaño' if backlog_clientes > 0 else ''}). "
        "Marca cada uno al confirmar si es un cliente puntual o el inicio de una tendencia."
    ),
    "progress_noun": "confirmados",
    "headers": ["Cliente", "Región", "Perfil", prev_month, last_month, "Cambio (MXN)"],
    "rows": [
        {
            "id": cli,
            "cells": [
                cli, clientes_ref.loc[cli, "region"], clientes_ref.loc[cli, "perfil_corto"],
                f"${piv_cliente_causante.loc[cli, prev_month]:,.0f}", f"${piv_cliente_causante.loc[cli, last_month]:,.0f}",
                f"${delta_cliente[cli]:,.0f}",
            ],
        }
        for cli in top_caida_clientes.index
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=10,
    title="Reporte Ejecutivo Mensual",
    tagline="Tu reporte, convertido en la decisión — de la cifra general de la empresa al cliente concreto que hay que llamar, listo para la reunión de dirección.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="bottom",
    chart_cols=2,
    hero_kpi=hero_kpi,
    hero_chart=hero_chart,
    drilldown_charts=drilldown_charts,
    drilldown_title="Detalle por subcategoría: segmentación y serie mensual (20 meses)",
    banner=banner,
    checklist=checklist,
)

print(f"Ingreso {last_month}: ${total_last:,.0f} ({var_total_pct}%) | Causante: {causante_sub} ({causante_cat})")
print(f"YTD {current_year} (ene-{MESES_ABBR[current_month_num-1]}): ${ytd_current_total:,.0f} ({ytd_growth_pct:+.1f}% vs YTD {prior_year}) | Motor: {motor_ytd} | Freno: {freno_ytd}")
print(f"Subcategorías que requieren atención: {subcats_atencion}")
print(f"Clientes a confirmar en {causante_sub}: {len(top_caida_clientes)} de {len(caida_clientes)} con caída")
print("OK -> dashboard.html")
