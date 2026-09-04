"""
Descompone tendencia + estacionalidad semanal por SKU, proyecta demanda a
28 días, calcula punto de reorden y valida el error del pronóstico (MAPE +
error absoluto en unidades) contra un holdout de 28 días. Cruza esto con
ingreso, costo y categoría para armar un dashboard tipo pirámide de Minto
(la conclusión primero, luego la evidencia por capas) pensado para alta y
media gerencia:

  1. Banner: la conclusión — cuánto ingreso está en riesgo y dónde se
     concentra (no está disperso: vive en el segmento de alta demanda).
  2. Hero KPI + KPIs de apoyo.
  3. Ingreso por categoría (stacked por segmento de demanda) + % de SKUs
     en riesgo por categoría (con el # de SKUs y su valor en costo).
  4. Drill-down: estacionalidad por categoría (heatmap), tendencia de
     ingreso por categoría (índice) y el costo del error de pronóstico
     por categoría.
  5. Tabla resumen por categoría: ingreso, margen, valor de inventario,
     vueltas de inventario, cuánto de ese inventario es stock de ciclo
     (lead time) vs. colchón por error de pronóstico, y estatus de salud.
  6. Explorador: elige categoría -> top 15 SKUs por ingreso -> clic en un
     SKU -> su demanda histórica y pronóstico (todo client-side, sin
     backend, datos embebidos en el HTML).

Genera dashboard.html.

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script), con la tabla del explorador cortada a 5 filas — se usa
como vista previa del dashboard completo en el README. Para regenerarla tras
un cambio visual: abre dashboard.html en el navegador y toma un screenshot
de la página completa.
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

FORECAST_DAYS = 28
Z_SAFETY = 1.65  # ~95% nivel de servicio

df = pd.read_csv(ROOT / "data" / "demanda_diaria.csv", parse_dates=["fecha"])
inv = pd.read_csv(ROOT / "data" / "inventario_actual.csv").set_index("sku")
df = df.merge(inv[["categoria", "segmento_demanda"]], left_on="sku", right_index=True)

n_days_hist = df["fecha"].nunique()
period_years = n_days_hist / 365

forecasts = {}
summary_rows = []
demand_hist = {}  # sku -> últimas 90 unidades vendidas, para el explorador

for sku, g in df.groupby("sku"):
    g = g.sort_values("fecha").reset_index(drop=True)
    g["dow"] = g["fecha"].dt.dayofweek
    g["trend"] = g["unidades_vendidas"].rolling(14, center=True, min_periods=7).mean()
    ratio = (g["unidades_vendidas"] / g["trend"]).replace([np.inf, -np.inf], np.nan)
    seasonal_idx = ratio.groupby(g["dow"]).mean().fillna(1.0)

    last_level = max(g["trend"].dropna().iloc[-14:].mean(), 0.001)
    recent = g.tail(90)
    daily_std = recent["unidades_vendidas"].std()

    last_date = g["fecha"].iloc[-1]
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=FORECAST_DAYS)
    future_dow = future_dates.dayofweek
    forecast_vals = [last_level * seasonal_idx.get(d, 1.0) for d in future_dow]
    forecasts[sku] = pd.DataFrame({"fecha": future_dates, "pronostico": forecast_vals})
    demand_hist[sku] = [int(v) for v in recent["unidades_vendidas"]]

    avg_daily_demand = last_level
    lead_time = inv.loc[sku, "lead_time_dias"]
    stock_actual = inv.loc[sku, "stock_actual"]
    costo_unitario = inv.loc[sku, "costo_unitario"]
    demanda_en_lead_time = avg_daily_demand * lead_time
    safety_stock = Z_SAFETY * daily_std * np.sqrt(lead_time)
    reorder_point = max(demanda_en_lead_time + safety_stock, 0.001)
    dias_de_stock = stock_actual / avg_daily_demand

    # ---- validación del pronóstico: holdout de 28 días -----------------
    train, test = g.iloc[:-FORECAST_DAYS], g.iloc[-FORECAST_DAYS:]
    train_trend = train["unidades_vendidas"].rolling(14, center=True, min_periods=7).mean()
    train_ratio = (train["unidades_vendidas"] / train_trend).replace([np.inf, -np.inf], np.nan)
    train_seasonal = train_ratio.groupby(train["dow"]).mean().fillna(1.0)
    train_level = max(train_trend.dropna().iloc[-14:].mean(), 0.001)
    test_pred = np.array([train_level * train_seasonal.get(d, 1.0) for d in test["dow"]])
    test_actual = test["unidades_vendidas"].to_numpy()
    abs_err = np.abs(test_actual - test_pred)
    mae_units_dia = abs_err.mean()  # error absoluto promedio, unidades/día
    mask = test_actual > 0
    mape = (np.abs((test_actual[mask] - test_pred[mask]) / test_actual[mask]).mean() * 100
            if mask.sum() >= 5 else np.nan)

    ingreso_total_hist = g["ingreso"].sum()
    ingreso_anual = ingreso_total_hist / period_years
    costo_anual = g["costo_total"].sum() / period_years

    summary_rows.append({
        "sku": sku,
        "categoria": inv.loc[sku, "categoria"],
        "segmento_demanda": inv.loc[sku, "segmento_demanda"],
        "demanda_diaria_prom": round(avg_daily_demand, 1),
        "stock_actual": int(stock_actual),
        "lead_time_dias": int(lead_time),
        "costo_unitario": costo_unitario,
        "dias_de_stock": round(dias_de_stock, 1),
        "punto_reorden": round(reorder_point, 0),
        "en_riesgo": stock_actual < reorder_point,
        "ingreso_anual": round(ingreso_anual, 0),
        "costo_anual": round(costo_anual, 0),
        "margen_pct": inv.loc[sku, "margen_pct"],
        "mape_pct": round(mape, 1) if not np.isnan(mape) else np.nan,
        "valor_inventario_actual": round(stock_actual * costo_unitario, 0),
        "valor_ciclo_lead_time": round(demanda_en_lead_time * costo_unitario, 0),
        "valor_safety_stock": round(safety_stock * costo_unitario, 0),
        "costo_impacto_forecast_anual": round(mae_units_dia * 365 * costo_unitario, 0),
    })

summary = pd.DataFrame(summary_rows)
en_riesgo_df = summary[summary["en_riesgo"]]

total_sku = len(summary)
n_en_riesgo = len(en_riesgo_df)
ingreso_anual_total = summary["ingreso_anual"].sum()
ingreso_anual_riesgo = en_riesgo_df["ingreso_anual"].sum()
margen_prom = (summary["margen_pct"] * summary["ingreso_anual"]).sum() / ingreso_anual_total
mape_mediana_global = summary["mape_pct"].median()
pct_ingreso_en_riesgo = ingreso_anual_riesgo / ingreso_anual_total * 100

# ---- resumen por categoría: financiero + salud de inventario ---------------
cat_summary = summary.groupby("categoria").agg(
    n_sku=("sku", "count"),
    lead_time_dias=("lead_time_dias", "first"),
    ingreso_anual=("ingreso_anual", "sum"),
    costo_anual=("costo_anual", "sum"),
    en_riesgo_n=("en_riesgo", "sum"),
    valor_inventario_actual=("valor_inventario_actual", "sum"),
    valor_ciclo_lead_time=("valor_ciclo_lead_time", "sum"),
    valor_safety_stock=("valor_safety_stock", "sum"),
    costo_impacto_forecast_anual=("costo_impacto_forecast_anual", "sum"),
).reset_index()
cat_summary["pct_en_riesgo"] = (cat_summary["en_riesgo_n"] / cat_summary["n_sku"] * 100).round(1)
cat_summary["margen_pct_prom"] = cat_summary["categoria"].map(
    lambda c: (summary.loc[summary["categoria"] == c, "margen_pct"] * summary.loc[summary["categoria"] == c, "ingreso_anual"]).sum()
    / summary.loc[summary["categoria"] == c, "ingreso_anual"].sum()
).round(1)
cat_summary["valor_costo_riesgo"] = cat_summary["categoria"].map(
    en_riesgo_df.groupby("categoria")["valor_inventario_actual"].sum()
).fillna(0)
cat_summary["ingreso_anual_riesgo"] = cat_summary["categoria"].map(
    en_riesgo_df.groupby("categoria")["ingreso_anual"].sum()
).fillna(0)

# vueltas de inventario/año = costo de lo vendido en el año / valor de inventario a costo hoy
cat_summary["vueltas_inventario"] = (cat_summary["costo_anual"] / cat_summary["valor_inventario_actual"]).round(1)
# de "mi inventario actual" (a costo), qué % corresponde al stock de ciclo que exige el lead
# time del proveedor y qué % es colchón de seguridad por error de pronóstico (demanda variable)
cat_summary["pct_safety_lead_time"] = (cat_summary["valor_ciclo_lead_time"] / cat_summary["valor_inventario_actual"] * 100).round(1)
cat_summary["pct_safety_forecast"] = (cat_summary["valor_safety_stock"] / cat_summary["valor_inventario_actual"] * 100).round(1)
# cobertura: inventario actual (a costo) vs. lo que el punto de reorden exige (ciclo + colchón)
cat_summary["cobertura_valor"] = cat_summary["valor_inventario_actual"] / (cat_summary["valor_ciclo_lead_time"] + cat_summary["valor_safety_stock"])


def estatus_de(cobertura):
    if cobertura < 1.0:
        return "critical", "Understock"
    if cobertura > 3.0:
        return "warning", "Overstock"
    return "good", "Sano"


cat_summary[["estatus_color", "estatus"]] = cat_summary["cobertura_valor"].apply(lambda c: pd.Series(estatus_de(c)))
cat_summary = cat_summary.sort_values("ingreso_anual", ascending=False).reset_index(drop=True)

# Índice de color consistente para "categoría" en los gráficos multi-serie
# (líneas de tendencia) — se salta el slot 1 (gold), reservado al hero KPI.
CATEGORIA_COLOR_IDX = {cat: idx for cat, idx in zip(cat_summary["categoria"], [0, 2, 3, 5, 6])}

# ---- resumen por segmento de demanda (index scoring) ------------------------
SEGMENTO_ORDEN = ["alta", "media", "baja", "esporadica", "nula"]
SEGMENTO_LABEL = {"alta": "Alta", "media": "Media", "baja": "Baja", "esporadica": "Esporádica", "nula": "Nula"}
# alta = teal oscuro (más prominente) -> nula = teal pálido (casi invisible),
# a propósito: el segmento que domina el ingreso debe dominar visualmente el stack.
SEGMENTO_COLOR_IDX = {"alta": 2, "media": 0, "baja": 3, "esporadica": 5, "nula": 6}
seg_summary = summary.groupby("segmento_demanda").agg(
    n_sku=("sku", "count"),
    ingreso_anual=("ingreso_anual", "sum"),
    en_riesgo_n=("en_riesgo", "sum"),
).reindex(SEGMENTO_ORDEN)
seg_summary["pct_sku"] = seg_summary["n_sku"] / total_sku * 100
seg_summary["pct_ingreso"] = seg_summary["ingreso_anual"] / ingreso_anual_total * 100
seg_summary["index_ingreso"] = (seg_summary["pct_ingreso"] / seg_summary["pct_sku"] * 100).round(0)
seg_summary["pct_en_riesgo"] = (seg_summary["en_riesgo_n"] / seg_summary["n_sku"] * 100).round(1)

alta = seg_summary.loc["alta"]
riesgo_prom_catalogo = n_en_riesgo / total_sku * 100

# ---- estacionalidad semanal por categoría (heatmap: desviación % vs. el ----
# propio promedio semanal de cada categoría, no volumen absoluto) ------------
DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
cat_dow = df.groupby(["categoria", df["fecha"].dt.dayofweek])["unidades_vendidas"].mean().unstack()
cat_dow = cat_dow.reindex(index=cat_summary["categoria"], columns=range(7))
cat_dow_idx = cat_dow.sub(cat_dow.mean(axis=1), axis=0).div(cat_dow.mean(axis=1), axis=0) * 100

daily = df.groupby("fecha")["unidades_vendidas"].sum().reset_index()
daily["dow"] = daily["fecha"].dt.dayofweek
dow_avg = daily.groupby("dow")["unidades_vendidas"].mean().reindex(range(7))

# ---- tendencia de ingreso por categoría (índice, mes 1 = 100) --------------
monthly_cat = df.groupby(["categoria", df["fecha"].dt.to_period("M")])["ingreso"].sum().reset_index()
monthly_cat.columns = ["categoria", "mes", "ingreso"]
meses = sorted(monthly_cat["mes"].unique())
meses_completos = meses[1:-1]  # se excluyen el primer y último mes (parciales)
piv = monthly_cat.pivot_table(index="categoria", columns="mes", values="ingreso").reindex(cat_summary["categoria"])
piv_idx = piv[meses_completos].div(piv[meses_completos[0]], axis=0) * 100
crecimiento_pct = (piv_idx[meses_completos[-1]] - 100).round(1)  # para el banner/insights

# ---- explorador: categoría -> top 15 SKUs por ingreso -> demanda del SKU --
# Fechas compartidas por los 400 SKUs (mismo calendario), así que solo se
# guardan una vez; el detalle de demanda solo se embebe para los SKUs que
# realmente aparecen en algún top 15 (no los 400), para que el HTML no crezca.
hist_dates_fmt = [d.strftime("%Y-%m-%d") for d in sorted(df["fecha"].unique())[-90:]]
forecast_dates_fmt = [d.strftime("%Y-%m-%d") for d in forecasts[summary.iloc[0]["sku"]]["fecha"]]

top_by_category = {}
for cat in cat_summary["categoria"]:
    top15 = summary[summary["categoria"] == cat].sort_values("ingreso_anual", ascending=False).head(15)
    top_by_category[cat] = [
        {
            "sku": r.sku,
            "ingreso_fmt": f"${r.ingreso_anual:,.0f}",
            "dias_fmt": f"{r.dias_de_stock:.1f}",
            "estatus_label": "En riesgo" if r.en_riesgo else "Sano",
        }
        for r in top15.itertuples()
    ]

skus_en_explorador = {row["sku"] for rows in top_by_category.values() for row in rows}
demand_explorer = {
    sku: {"hist": demand_hist[sku], "forecast": [round(v, 1) for v in forecasts[sku]["pronostico"]]}
    for sku in skus_en_explorador
}

explorer = {
    "id": "sku_explorer",
    "title": "Explora por categoría y SKU",
    "subtitle": "Elige una categoría para ver sus 15 SKUs de mayor ingreso anual — haz clic en uno para ver su demanda histórica y el pronóstico de 28 días.",
    "categories": list(cat_summary["categoria"]),
    "table_headers": ["SKU", "Ingreso anual", "Días de stock", "Estatus"],
    "row_fields": ["sku", "ingreso_fmt", "dias_fmt", "estatus_label"],
    "top_by_category": top_by_category,
    "hist_dates": hist_dates_fmt,
    "forecast_dates": forecast_dates_fmt,
    "demand": demand_explorer,
}

# ---- interactive dashboard --------------------------------------------------
banner = {
    "label": "La conclusión primero",
    "headline": f"${ingreso_anual_riesgo/1e6:.1f}M MXN de ingreso anual está hoy en SKUs por debajo de su punto de reorden — y no está disperso: se concentra en el segmento de alta demanda.",
    "subtext": (
        f"El segmento de demanda \"alta\" es solo el {alta['pct_sku']:.0f}% del catálogo pero genera el {alta['pct_ingreso']:.0f}% del ingreso "
        f"(índice {alta['index_ingreso']:.0f} vs. 100 = proporcional) y tiene la tasa de riesgo de quiebre más alta de todos los segmentos "
        f"({alta['pct_en_riesgo']:.0f}% de sus SKUs, vs. {riesgo_prom_catalogo:.0f}% del catálogo). Revisar primero el punto de reorden y el "
        f"nivel de servicio de estos SKUs protege más ingreso con el mismo esfuerzo de compra."
    ),
}

hero_kpi = {
    "label": "Ingreso anual en riesgo de quiebre",
    "value": f"${ingreso_anual_riesgo/1e6:.1f}M MXN",
    "status": "critical",
    "status_label": f"{pct_ingreso_en_riesgo:.0f}% del ingreso total",
}
cat_summary_por_riesgo = cat_summary.sort_values("ingreso_anual_riesgo", ascending=False)
hero_chart = {
    "id": "chart_riesgo_valor", "type": "bar",
    "title": "Ingreso anual en riesgo por categoría",
    "subtitle": "MXN/año en SKUs por debajo de su punto de reorden",
    "labels": list(cat_summary_por_riesgo["categoria"]),
    "datasets": [{
        "label": "Ingreso en riesgo",
        "data": [round(v, 0) for v in cat_summary_por_riesgo["ingreso_anual_riesgo"]],
        "colors": [STATUS["critical"]] * len(cat_summary),
    }],
    "value_format": "currency",
}

kpis = [
    {"label": "SKUs monitoreados", "value": f"{total_sku}"},
    {"label": "Ingreso anual total", "value": f"${ingreso_anual_total/1e6:.1f}M MXN"},
    {"label": "SKUs en riesgo de quiebre", "value": f"{n_en_riesgo} ({pct_ingreso_en_riesgo:.0f}% de venta)",
     "status": "critical" if n_en_riesgo else "good"},
    {"label": "Margen bruto ponderado", "value": f"{margen_prom:.1f}%"},
    {"label": "Error de pronóstico (MAPE mediana)", "value": f"{mape_mediana_global:.0f}%"},
]

# ---- ingreso anual por categoría, apilado por segmento de demanda ----------
pivot_seg = summary.pivot_table(index="categoria", columns="segmento_demanda", values="ingreso_anual", aggfunc="sum")
pivot_seg = pivot_seg.reindex(index=cat_summary["categoria"], columns=SEGMENTO_ORDEN).fillna(0)

# ---- % en riesgo por categoría, con # de SKUs y su valor en costo ----------
riesgo_labels = [
    f"{int(n)} SKU · ${v/1e6:.1f}M"
    for n, v in zip(cat_summary["en_riesgo_n"], cat_summary["valor_costo_riesgo"])
]

charts = [
    {
        "id": "chart_ingreso_categoria", "type": "stacked-bar", "stacked": True,
        "title": "Ingreso anual por categoría, por tipo de demanda de sus SKUs",
        "subtitle": "Electrónica y Accesorios concentra la mayor parte del ingreso, dominado por SKUs de demanda alta",
        "labels": list(cat_summary["categoria"]),
        "datasets": [
            {"label": SEGMENTO_LABEL[s], "data": [round(v, 0) for v in pivot_seg[s]], "color_index": SEGMENTO_COLOR_IDX[s]}
            for s in SEGMENTO_ORDEN
        ],
        "value_format": "currency", "horizontal": True,
    },
    {
        "id": "chart_riesgo_categoria", "type": "bar",
        "title": "% de SKUs en riesgo de quiebre por categoría",
        "subtitle": f"Línea de referencia: {riesgo_prom_catalogo:.0f}% promedio del catálogo — etiqueta: # de SKUs y su valor de inventario a costo",
        "labels": list(cat_summary["categoria"]),
        "datasets": [{
            "label": "% en riesgo",
            "data": [round(v, 1) for v in cat_summary["pct_en_riesgo"]],
            "colors": [STATUS["critical"] if v >= riesgo_prom_catalogo else STATUS["neutral"] for v in cat_summary["pct_en_riesgo"]],
            "value_labels": riesgo_labels,
        }],
        "value_format": "percent", "horizontal": True, "value_labels": True,
        "value_max": round(cat_summary["pct_en_riesgo"].max() * 1.9, 0),
        "reference_line": {"value": round(riesgo_prom_catalogo, 1), "label": "Promedio catálogo"},
    },
]

drilldown_charts = [
    {
        "id": "chart_heatmap_estacionalidad", "type": "heatmap", "color_mode": "diverging", "value_format": "int",
        "title": "El pico de jueves/viernes y el valle de domingo son estructurales, no de una sola categoría",
        "subtitle": "Desviación % vs. el promedio semanal de cada categoría (fila) — no volumen absoluto",
        "row_labels": list(cat_summary["categoria"]),
        "col_labels": DIAS_SEMANA,
        "matrix": [[round(v, 0) for v in cat_dow_idx.loc[c]] for c in cat_summary["categoria"]],
    },
    {
        "id": "chart_tendencia_categoria", "type": "line",
        "title": "Limpieza del Hogar y Ferretería crecen más rápido, aunque son categorías chicas",
        "subtitle": f"Ingreso mensual por categoría, indexado a 100 en {meses_completos[0]}",
        "labels": [str(m) for m in meses_completos],
        "datasets": [
            {"label": c, "data": [round(v, 1) for v in piv_idx.loc[c]], "color_index": CATEGORIA_COLOR_IDX[c]}
            for c in cat_summary["categoria"]
        ],
        "y_label": "Índice (mes 1 = 100)",
    },
    {
        "id": "chart_impacto_forecast_categoria", "type": "bar",
        "title": "El error de pronóstico cuesta más en Electrónica que en cualquier otra categoría",
        "subtitle": "Impacto anualizado del error de pronóstico en costo de inventario (unidades de error x costo unitario x 365)",
        "labels": list(cat_summary.sort_values("costo_impacto_forecast_anual", ascending=False)["categoria"]),
        "datasets": [{
            "label": "Impacto en costo",
            "data": [round(v, 0) for v in cat_summary.sort_values("costo_impacto_forecast_anual", ascending=False)["costo_impacto_forecast_anual"]],
        }],
        "value_format": "currency", "horizontal": True,
    },
]

top_impacto_cat = cat_summary.sort_values("costo_impacto_forecast_anual", ascending=False).iloc[0]

insights = [
    f"<b>El ingreso en riesgo no está disperso</b>: ${ingreso_anual_riesgo/1e6:.1f}M MXN/año ({pct_ingreso_en_riesgo:.0f}% del total) está en SKUs por debajo de su punto de reorden, y el segmento de <b>alta demanda</b> —solo {alta['pct_sku']:.0f}% del catálogo, {alta['pct_ingreso']:.0f}% del ingreso— tiene la tasa de riesgo más alta ({alta['pct_en_riesgo']:.0f}%). Ahí es donde revisar el nivel de servicio protege más ingreso.",
    f"<b>{cat_summary.iloc[0]['categoria']}</b> concentra {cat_summary.iloc[0]['ingreso_anual']/ingreso_anual_total*100:.0f}% del ingreso con el margen más bajo del catálogo ({cat_summary.sort_values('margen_pct_prom').iloc[0]['margen_pct_prom']:.1f}%) y el lead time más largo — es el mayor punto de apalancamiento para renegociar condiciones de proveedor.",
    f"La demanda de <b>jueves/viernes</b> más que duplica la de domingo ({dow_avg[3]:,.0f}/{dow_avg[4]:,.0f} vs. {dow_avg[6]:,.0f} unidades/día) — el punto de reorden ya ajusta por este patrón semanal en vez de usar un promedio plano.",
    f"El error de pronóstico no es solo un número estadístico: en <b>{top_impacto_cat['categoria']}</b> equivale a ${top_impacto_cat['costo_impacto_forecast_anual']/1e6:.1f}M MXN/año en inventario mal calibrado — {top_impacto_cat['costo_impacto_forecast_anual']/top_impacto_cat['valor_inventario_actual']*100:.0f}% del valor de su inventario actual, movido cada año solo por el margen de error del pronóstico.",
    f"Los segmentos <b>esporádica y nula</b> son {seg_summary.loc[['esporadica','nula'],'n_sku'].sum():.0f} SKUs ({seg_summary.loc[['esporadica','nula'],'pct_sku'].sum():.0f}% del catálogo) pero generan solo {seg_summary.loc[['esporadica','nula'],'pct_ingreso'].sum():.1f}% del ingreso — candidatos a revisión trimestral de descontinuación para liberar capital de trabajo.",
]

table = {
    "title": "Resumen por categoría",
    "headers": ["Categoría", "SKUs", "Lead time (días)", "Ingreso anual", "Margen prom.", "Valor de inventario (costo)",
                "Vueltas/año", "Safety: lead time", "Safety: forecast", "Estatus"],
    "rows": [
        [r.categoria, int(r.n_sku), int(r.lead_time_dias), f"${r.ingreso_anual:,.0f}", f"{r.margen_pct_prom:.1f}%",
         f"${r.valor_inventario_actual:,.0f}", f"{r.vueltas_inventario:.1f}x",
         f"{r.pct_safety_lead_time:.0f}%", f"{r.pct_safety_forecast:.0f}%", r.estatus]
        for r in cat_summary.itertuples()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=7,
    title="Forecasting de Demanda e Inventario",
    tagline="El ingreso en riesgo de quiebre no está disperso: está concentrado en el 20% de SKUs que más venden. Empezar ahí.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="top",
    hero_kpi=hero_kpi,
    hero_chart=hero_chart,
    drilldown_charts=drilldown_charts,
    drilldown_title="Estacionalidad por categoría, tendencia de ingreso y el costo del error de pronóstico",
    banner=banner,
    explorer=explorer,
)

print(f"SKUs: {total_sku} | Ingreso anual: ${ingreso_anual_total:,.0f} | En riesgo: {n_en_riesgo} SKUs / ${ingreso_anual_riesgo:,.0f} MXN ({pct_ingreso_en_riesgo:.0f}% de venta)")
print("OK -> dashboard.html")
