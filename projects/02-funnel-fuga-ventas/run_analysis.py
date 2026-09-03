"""
Detecta fuga de conversión en el funnel comercial y genera dashboard.html
(dashboard interactivo con alerta activa, funnel real y tendencia).

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
import dashboard as dash

df = pd.read_csv(ROOT / "data" / "funnel_semanal.csv")
df["tasa_calif_a_propuesta"] = (df["propuestas"] / df["calificados"] * 100).round(1)
df["tasa_conversion_total"] = (df["cierres"] / df["leads"] * 100).round(1)

ALERT_THRESHOLD = 40.0  # % mínimo aceptable en la transición calificados -> propuesta
current = df.iloc[-1]
baseline = df[df["semana"] < 10]["tasa_calif_a_propuesta"].mean()
in_alert = current["tasa_calif_a_propuesta"] < ALERT_THRESHOLD
weeks_in_alert = int((df["tasa_calif_a_propuesta"] < ALERT_THRESHOLD).sum())
leak_start_week = 10

stages = ["Leads", "Contactados", "Calificados", "Propuestas", "Cierres"]
stage_cols = ["leads", "contactados", "calificados", "propuestas", "cierres"]
current_funnel = [int(current[c]) for c in stage_cols]

# Impacto acumulado: propuestas que se habrían generado al ritmo histórico
# (baseline pre-fuga) vs. las que realmente se generaron desde que arrancó
# la caída — cuantifica la fuga en prospectos perdidos, no solo en %.
expected_propuestas = (df["calificados"] * (baseline / 100)).round()
shortfall = (expected_propuestas - df["propuestas"]).clip(lower=0)
lost_since_leak = int(shortfall[df["semana"] >= leak_start_week].sum())

# ---- interactive dashboard ----------------------------------------------
kpis = [
    {"label": "Leads esta semana", "value": f"{int(current['leads']):,}"},
    {"label": "Tasa Calif. → Propuesta", "value": f"{current['tasa_calif_a_propuesta']}%",
     "status": "critical" if in_alert else "good",
     "status_label": "fuga activa" if in_alert else "saludable",
     "delta": f"vs. {baseline:.1f}% histórico", "delta_direction": "down" if in_alert else "up"},
    {"label": "Semanas en alerta", "value": str(weeks_in_alert)},
    {"label": "Conversión total del funnel", "value": f"{current['tasa_conversion_total']}%"},
    {"label": "Propuestas perdidas desde S10", "value": f"{lost_since_leak:,}", "hero": True,
     "status": "critical" if lost_since_leak > 0 else "good",
     "status_label": "fuga activa" if lost_since_leak > 0 else "sin impacto",
     "delta": "prospectos calificados vs. ritmo histórico", "delta_direction": "down"},
]

charts = [
    {
        "id": "chart_funnel", "type": "funnel",
        "title": f"Funnel — semana {int(current['semana'])}",
        "subtitle": f"De {current_funnel[0]:,} leads a {current_funnel[-1]:,} cierres · ⚠ marca la transición con mayor fuga",
        "labels": stages,
        "datasets": [{"label": "Prospectos", "data": current_funnel}],
    },
    {
        "id": "chart_leak", "type": "line",
        "title": f"Calificados → Propuesta: {baseline:.0f}% → {current['tasa_calif_a_propuesta']}%",
        "subtitle": f"Umbral de alerta: {ALERT_THRESHOLD}% · fuga activa desde la semana {leak_start_week}",
        "labels": [f"S{w}" for w in df["semana"]],
        "datasets": [
            {"label": "Tasa real", "data": list(df["tasa_calif_a_propuesta"])},
            {"label": "Umbral de alerta", "data": [ALERT_THRESHOLD] * len(df)},
        ],
        "y_label": "%",
        "marker": {"index": int(df.index[df["semana"] == leak_start_week][0]), "label": f"Inicio de fuga (S{leak_start_week})"},
    },
]

insights = [
    f"Desde que arrancó la fuga en la semana {leak_start_week}, se perdieron <b>{lost_since_leak:,} propuestas</b> frente al ritmo histórico — esas son conversaciones de cierre que nunca se iniciaron.",
    f"La conversión Calificados → Propuesta cayó de ~{baseline:.0f}% a <b>{current['tasa_calif_a_propuesta']}%</b>, {weeks_in_alert} semanas por debajo del umbral de {ALERT_THRESHOLD}%.",
    "La fuga está aislada en la etapa de propuesta: el volumen de leads y la tasa de calificación se mantienen estables, así que no es un problema de generación de demanda.",
    f"Un reporte mensual detecta esto 4-6 semanas tarde; con la alerta activa desde la semana {leak_start_week}, ya van {weeks_in_alert} semanas de ventana para corregir antes del cierre de trimestre.",
    f"Acción sugerida: auditar el proceso de armado de propuestas y el tiempo de respuesta a prospectos calificados de las últimas {weeks_in_alert} semanas.",
]

table = {
    "headers": ["Semana", "Leads", "Contactados", "Calificados", "Propuestas", "Cierres", "% Calif.→Prop."],
    "rows": [
        [int(r.semana), int(r.leads), int(r.contactados), int(r.calificados), int(r.propuestas), int(r.cierres), f"{r.tasa_calif_a_propuesta}%"]
        for r in df.itertuples()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=2,
    title="Funnel de Ventas con Alertas de Fuga",
    tagline="Te enteras de la fuga en el funnel cuando todavía puedes corregirla, no cuando ya se perdió el trimestre.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
)

print(f"Alerta activa: {in_alert} | Tasa actual: {current['tasa_calif_a_propuesta']}% | Semanas en alerta: {weeks_in_alert}")
print("OK -> dashboard.html")
