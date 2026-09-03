"""
Analiza las ventas diarias, calcula cumplimiento de meta por equipo y genera
dashboard.html (dashboard interactivo, Micro Data Office).

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) — se usa como vista previa del dashboard completo en el
README. Para regenerarla tras un cambio visual: abre dashboard.html en el
navegador y toma un screenshot de la página completa.

Uso:
    python data/generate_data.py
    python run_analysis.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import pandas as pd
from xia_style import STATUS
import dashboard as dash

df = pd.read_csv(ROOT / "data" / "ventas_diarias.csv", parse_dates=["fecha"])
goals = pd.read_csv(ROOT / "data" / "metas_mensuales.csv").set_index("equipo")["meta_mensual_mxn"]

df["mes"] = df["fecha"].dt.to_period("M").astype(str)
last_month = df["mes"].max()

by_team_month = df.groupby(["equipo", "mes"])["monto_mxn"].sum().unstack(fill_value=0)
months = sorted(by_team_month.columns)
current = by_team_month[last_month]
attainment = (current / goals * 100).round(1)


def status_of(pct):
    return "good" if pct >= 95 else ("warning" if pct >= 80 else "critical")


total_current = current.sum()
total_goal = goals.sum()
total_attainment = round(total_current / total_goal * 100, 1)
leading_team = attainment.idxmax()
lagging_team = attainment.idxmin()

# ---- trend break analysis for the lagging team (time-series read) --------
lagging_series = by_team_month.loc[lagging_team, months]
peak_month = lagging_series.idxmax()
peak_value = lagging_series[peak_month]
peak_idx = months.index(peak_month)
last_value = lagging_series[last_month]
drop_pct = round((1 - last_value / peak_value) * 100, 1) if peak_month != last_month else 0
months_since_peak = len(months) - 1 - peak_idx

# ---- interactive dashboard --------------------------------------------------
# Chart 1 — comparison message: % of goal reached, sorted worst-to-best so the
# risk lands first, colored by status, direct value labels, one reference line
# at 100% instead of a second "goal" bar the reader has to subtract mentally.
sorted_teams = attainment.sort_values(ascending=True).index.tolist()
def _trend_dataset(team):
    ds = {
        "label": team,
        "data": [round(by_team_month.loc[team, m], 0) for m in months],
        "muted": team != lagging_team,
        "emphasis": team == lagging_team,
    }
    if team == lagging_team:
        ds["colors"] = STATUS["critical"]
    return ds


trend_datasets = [_trend_dataset(team) for team in goals.index]

kpis = [
    {"label": f"Ventas totales ({last_month})", "value": f"${total_current:,.0f}"},
    {"label": "Cumplimiento vs. meta", "value": f"{total_attainment}%",
     "status": "good" if total_attainment >= 95 else ("warning" if total_attainment >= 80 else "critical"),
     "status_label": "en meta" if total_attainment >= 95 else ("cerca de meta" if total_attainment >= 80 else "en riesgo")},
    {"label": "Equipo líder", "value": leading_team, "delta": f"{attainment[leading_team]}% de meta", "delta_direction": "up"},
    {"label": "Equipo en riesgo", "value": lagging_team, "delta": f"{attainment[lagging_team]}% de meta", "delta_direction": "down"},
]

charts = [
    {
        "id": "chart_current", "type": "bar", "horizontal": True,
        "title": f"{lagging_team} va en {attainment[lagging_team]:.0f}% de meta — el único equipo en riesgo",
        "subtitle": "Verde = en meta (≥95%) · Amarillo = cerca (80–94%) · Rojo = en riesgo (<80%). Ordenado de menor a mayor cumplimiento.",
        "labels": sorted_teams,
        "datasets": [{
            "label": "% de meta",
            "data": [attainment[t] for t in sorted_teams],
            "colors": [STATUS[status_of(attainment[t])] for t in sorted_teams],
            "value_labels": [f"{attainment[t]:.0f}%" for t in sorted_teams],
        }],
        "value_format": "percent",
        "value_labels": True,
        "value_max": 120,
        "reference_line": {"value": 100, "label": "Meta (100%)"},
    },
    {
        "id": "chart_trend", "type": "line",
        "title": f"{lagging_team} cae {drop_pct:.0f}% en {months_since_peak} meses tras tocar su punto más alto en {peak_month}",
        "subtitle": f"Tendencia mensual por equipo · {lagging_team} resaltado en rojo, el resto en gris para no distraer.",
        "labels": months,
        "datasets": trend_datasets,
        "y_label": "MXN",
        "value_format": "currency",
        "marker": {"index": peak_idx, "label": f"Pico: {peak_month}"},
    },
]

insights = [
    f"<b>{lagging_team}</b> cayó {drop_pct:.0f}% en {months_since_peak} meses (de ${peak_value:,.0f} en {peak_month} a ${last_value:,.0f} en {last_month}) — no es ruido, es una caída sostenida.",
    f"El quiebre ya era visible en la tendencia mensual desde {peak_month}, semanas antes de que el reporte de cierre lo hubiera mostrado.",
    f"<b>{leading_team}</b> compensa parte del boquete (va en {attainment[leading_team]}% de su meta), pero no alcanza: el cumplimiento consolidado de la organización es <b>{total_attainment}%</b> (${total_current:,.0f} de ${total_goal:,.0f} MXN).",
    f"Acción esta semana: revisar con el gerente de <b>{lagging_team}</b> qué cambió — antes de que sea un problema de cierre de trimestre, no después.",
]

table = {
    "headers": ["Equipo", f"Ventas {last_month} (MXN)", "Meta mensual (MXN)", "% Cumplimiento"],
    "rows": [
        [team, f"${current[team]:,.0f}", f"${goals[team]:,.0f}", f"{attainment[team]}%"]
        for team in sorted_teams[::-1]
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=1,
    title="Ventas por Equipo en Tiempo Real",
    tagline=f"{lagging_team} viene en {attainment[lagging_team]:.0f}% de su meta este mes — y la tendencia ya lo mostraba desde {peak_month}. Así se ve la alerta antes del cierre, no después.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
)

print(f"Cumplimiento total: {total_attainment}% | Líder: {leading_team} | Riesgo: {lagging_team}")
print("OK -> dashboard.html")
