"""
Consolida el scorecard ejecutivo cross-funcional y genera dashboard.html:
widget de score consolidado + tendencia, tiles por indicador, tendencia
por área, dispersión y drill-down por indicador.

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) — se usa como vista previa del dashboard completo en el
README. Para regenerarla tras un cambio visual: abre dashboard.html en el
navegador y toma un screenshot de la página completa.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import pandas as pd
import dashboard as dash

df = pd.read_csv(ROOT / "data" / "scorecard.csv")
hist = pd.read_csv(ROOT / "data" / "kpi_historico.csv")


def cumplimiento(resultado, meta, menor_es_mejor):
    if menor_es_mejor:
        return round(meta / resultado * 100, 1)
    return round(resultado / meta * 100, 1)


df["cumplimiento_pct"] = df.apply(lambda r: cumplimiento(r["resultado"], r["meta"], r["menor_es_mejor"]), axis=1)


def status_of(pct):
    if pct >= 100:
        return "good", "en meta"
    if pct >= 90:
        return "warning", "cerca de meta"
    return "critical", "en riesgo"


df[["status", "status_label"]] = df["cumplimiento_pct"].apply(lambda p: pd.Series(status_of(p)))


def fmt_value(value, unidad):
    if unidad == "MXN":
        return f"${value:,.0f} MXN"
    if unidad == "%":
        return f"{value:.1f}%"
    if unidad == "/5":
        return f"{value:.2f}/5"
    return f"{value:,.0f} {unidad}"


# ---- histórico normalizado a % de cumplimiento ----------------------------
hist = hist.merge(df[["kpi", "meta", "menor_es_mejor", "unidad"]], on="kpi", how="left")
hist["cumplimiento_pct"] = hist.apply(
    lambda r: cumplimiento(r["resultado"], r["meta"], r["menor_es_mejor"]), axis=1
)
months = sorted(hist["mes"].unique())

score_trend = hist.groupby("mes")["cumplimiento_pct"].mean().reindex(months).round(1)
area_trend = (
    hist.groupby(["mes", "area"])["cumplimiento_pct"].mean().unstack("area").reindex(months).round(1)
)
volatility = hist.groupby("kpi")["cumplimiento_pct"].std().round(1)

prev_cump = hist[hist["mes"] == months[-2]].set_index("kpi")["cumplimiento_pct"]
df["delta_pts"] = (df["cumplimiento_pct"] - df["kpi"].map(prev_cump)).round(1)

overall = round(df["cumplimiento_pct"].mean(), 1)
en_meta = int((df["status"] == "good").sum())
en_riesgo = int((df["status"] == "critical").sum())
worst = df.loc[df["cumplimiento_pct"].idxmin()]
most_volatile_kpi = volatility.idxmax()
most_volatile_val = volatility.max()

area_change = (area_trend.iloc[-1] - area_trend.iloc[0]).round(1)
area_most_improved = area_change.idxmax()
area_most_declined = area_change.idxmin()

# ---- interactive dashboard ------------------------------------------------
overall_status, overall_label = status_of(overall)
hero_kpi = {
    "label": "Score consolidado", "value": f"{overall}%",
    "status": overall_status, "status_label": overall_label,
}
hero_chart = {
    "id": "chart_score_trend", "type": "line",
    "title": "Score consolidado — tendencia",
    "subtitle": f"Promedio de cumplimiento, {len(months)} meses",
    "labels": months,
    "datasets": [{"label": "Score promedio", "data": list(score_trend.values), "fill": True}],
}

kpis = []
for r in df.itertuples():
    delta = 0.0 if pd.isna(r.delta_pts) else r.delta_pts
    kpis.append({
        "label": r.kpi,
        "value": fmt_value(r.resultado, r.unidad),
        "delta": f"{delta:+.1f} pts",
        "delta_direction": "up" if delta >= 0 else "down",
        "status": r.status,
        "status_label": r.status_label,
    })

scatter_points = [
    {"x": r.cumplimiento_pct, "y": volatility.get(r.kpi, 0.0), "label": r.kpi, "status": r.status}
    for r in df.itertuples()
]

charts = [
    {
        "id": "chart_area_trend", "type": "line",
        "title": "Cumplimiento por área — tendencia",
        "subtitle": f"Promedio mensual de cumplimiento por área, {len(months)} meses",
        "labels": months,
        "datasets": [{"label": area, "data": list(area_trend[area])} for area in area_trend.columns],
        "y_label": "%",
    },
    {
        "id": "chart_dispersion", "type": "scatter",
        "title": "Cumplimiento vs. volatilidad",
        "subtitle": "Cada punto es un indicador — arriba a la izquierda es el mayor riesgo",
        "points": scatter_points,
        "x_label": "% cumplimiento actual", "y_label": "Volatilidad histórica (desv. estándar, pts)",
        "x_unit": "%", "y_unit": " pts",
    },
]

# Mismo índice de color que su área usa en "Cumplimiento por área — tendencia",
# para que la línea del drill-down haga match visual con esa gráfica.
area_color_index = {area: i for i, area in enumerate(area_trend.columns)}
df_by_area = df.sort_values(by="area", key=lambda s: s.map(area_color_index), kind="stable")

drilldown_charts = [
    {
        "id": f"chart_drill_{i}", "type": "line",
        "title": f"{r.kpi} ({r.area})",
        "subtitle": f"Resultado vs. meta ({r.unidad}), {len(months)} meses",
        "labels": list(hist.loc[hist["kpi"] == r.kpi].sort_values("mes")["mes"]),
        "datasets": [{
            "label": "Resultado",
            "data": list(hist.loc[hist["kpi"] == r.kpi].sort_values("mes")["resultado"]),
            "color_index": area_color_index[r.area],
        }],
        "reference_line": {"value": r.meta, "label": "Meta"},
    }
    for i, r in enumerate(df_by_area.itertuples())
]

insights = [
    f"El score consolidado de la organización es <b>{overall}%</b>: {en_meta} de {len(df)} indicadores están en meta, {en_riesgo} en riesgo.",
    f"<b>{worst['kpi']}</b> ({worst['area']}, responsable: {worst['responsable']}) es el que más arrastra el consolidado, en {worst['cumplimiento_pct']}%.",
    f"<b>{most_volatile_kpi}</b> es el indicador más volátil de los últimos {len(months)} meses (desv. estándar de {most_volatile_val:.1f} pts) — antes de mover la meta, vale la pena revisar el proceso.",
    f"<b>{area_most_improved}</b> es el área que más mejoró en el periodo ({area_change[area_most_improved]:+.1f} pts vs. el primer mes), mientras <b>{area_most_declined}</b> es la que más retrocedió ({area_change[area_most_declined]:+.1f} pts).",
]

table = {
    "headers": ["Indicador", "Área", "Responsable", "Meta", "Resultado", "% Cumplimiento", "Estatus"],
    "rows": [
        [r.kpi, r.area, r.responsable, fmt_value(r.meta, r.unidad), fmt_value(r.resultado, r.unidad), f"{r.cumplimiento_pct}%", r.status_label]
        for r in df.itertuples()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=3,
    title="Scorecard Ejecutivo: Metas vs. Resultados",
    tagline="El estatus, la tendencia y el detalle de los 10 indicadores que le importan a dirección — en una sola pantalla.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    hero_kpi=hero_kpi,
    hero_chart=hero_chart,
    drilldown_charts=drilldown_charts,
    drilldown_title="Detalle por indicador — tendencia vs. meta",
)

print(f"Score consolidado: {overall}% | En meta: {en_meta}/{len(df)} | En riesgo: {en_riesgo}")
print("OK -> dashboard.html")
