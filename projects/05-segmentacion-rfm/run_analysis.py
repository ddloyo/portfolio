"""
Calcula Recencia, Frecuencia y Valor histórico por cliente y cruza los ejes
en una matriz de 4 cuadrantes de acción (en vez de una tabla de 6 segmentos
RFM). Genera dashboard.html: resumen por cuadrante arriba (pirámide de
Minto), matriz recencia x valor, scatters R x F y F x valor, y el plan de
llamadas de la semana para "En riesgo" al final.

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script), con la tabla de llamadas cortada a 5 filas — se usa
como vista previa del dashboard completo en el README. Para regenerarla tras
un cambio visual: abre dashboard.html en el navegador y toma un screenshot
de la página completa.

Uso:
    python data/generate_data.py
    python run_analysis.py
"""

import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import pandas as pd
from xia_style import STATUS
import dashboard as dash

TODAY = date(2026, 8, 31)
df = pd.read_csv(ROOT / "data" / "transacciones.csv", parse_dates=["fecha"])

agg = df.groupby("cliente_id").agg(
    ultima_compra=("fecha", "max"),
    frecuencia=("fecha", "count"),
    monto_total=("monto_mxn", "sum"),
).reset_index()
agg["recencia_dias"] = (pd.Timestamp(TODAY) - agg["ultima_compra"]).dt.days

# ---- matriz recencia x valor: 4 cuadrantes de acción -----------------------
# Split por mediana en ambos ejes: los 4 cuadrantes quedan balanceados en
# tamaño y la matriz es legible como scatter, en vez de una tabla de 6
# segmentos RFM que exige leer 3 scores por cliente para entender qué hacer.
#
# El monto histórico tiene cola larga (pocos clientes acumulan mucho en 12
# meses), así que graficarlo en MXN crudo aplasta a la mayoría contra el
# piso del eje. Se usa el percentil de valor dentro de la cartera (0-100,
# uniforme por construcción) para el eje y el corte de cuadrante, mientras
# el tooltip y la tabla siguen mostrando el monto real.
median_recencia = agg["recencia_dias"].median()
agg["valor_percentil"] = agg["monto_total"].rank(pct=True) * 100

QUADRANTS = {
    (True, True): ("good", "Campeones"),
    (False, True): ("critical", "En riesgo"),
    (True, False): ("neutral", "Nuevos / Prometedores"),
    (False, False): ("serious", "Hibernando"),
}


def quadrant_of(row):
    key = (row["recencia_dias"] <= median_recencia, row["valor_percentil"] >= 50.0)
    return QUADRANTS[key]


agg[["cuadrante_status", "cuadrante"]] = agg.apply(quadrant_of, axis=1, result_type="expand")

ACCIONES = {
    "Campeones": "Programa VIP / referidos — proteger y convertir en embajadores.",
    "En riesgo": "Contacto proactivo esta semana — compraban bien y se están yendo.",
    "Nuevos / Prometedores": "Onboarding y segunda compra — el momento crítico de retención.",
    "Hibernando": "Campaña de reactivación de bajo costo o descontinuar inversión de marketing.",
}
agg["accion_recomendada"] = agg["cuadrante"].map(ACCIONES)

quadrant_order = ["Campeones", "En riesgo", "Nuevos / Prometedores", "Hibernando"]
STATUS_OF_QUADRANT = {q: s for (s, q) in QUADRANTS.values()}

seg_summary = agg.groupby("cuadrante").agg(
    clientes=("cliente_id", "count"),
    valor_promedio=("monto_total", "mean"),
    valor_total=("monto_total", "sum"),
    frecuencia_promedio=("frecuencia", "mean"),
).reindex(quadrant_order).fillna(0)

total_clientes = len(agg)
total_valor = agg["monto_total"].sum()
campeones = seg_summary.loc["Campeones"]
en_riesgo = seg_summary.loc["En riesgo"]

# ---- plan operativo de la semana -------------------------------------------
# "En riesgo" agrupa a todo el que compraba bien y dejó de comprar -- más de
# lo que un equipo puede llamar en una semana. Se define una capacidad
# explícita y se prioriza por valor histórico dentro del cuadrante, para
# proteger primero el cliente más valioso con el mismo esfuerzo de llamada.
CAPACIDAD_POR_DIA = 8
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
CAPACIDAD_SEMANA = CAPACIDAD_POR_DIA * len(DIAS)

cola_riesgo = agg[agg["cuadrante"] == "En riesgo"].sort_values("monto_total", ascending=False).reset_index(drop=True)
esta_semana = cola_riesgo.iloc[:CAPACIDAD_SEMANA].copy()
backlog = cola_riesgo.iloc[CAPACIDAD_SEMANA:]
esta_semana["dia"] = [DIAS[i // CAPACIDAD_POR_DIA] for i in range(len(esta_semana))]

valor_semana = esta_semana["monto_total"].sum()
valor_backlog = backlog["monto_total"].sum()

# ---- interactive dashboard --------------------------------------------------
banner = {
    "label": "Esta semana",
    "headline": f"{len(esta_semana)} llamadas de reactivación prioritaria — ${valor_semana:,.0f} MXN en valor histórico en juego",
    "subtext": (
        f"Ordenadas por valor histórico, {CAPACIDAD_POR_DIA} por día de lunes a viernes: empieza el lunes por el cliente que más ha gastado. "
        f"Quedan {len(backlog)} clientes en cola (${valor_backlog:,.0f} MXN adicionales) para la próxima semana."
    ),
}

kpis = [
    {"label": "Clientes analizados", "value": f"{total_clientes:,}"},
    {"label": "Valor histórico total", "value": f"${total_valor:,.0f} MXN"},
    {"label": "Campeones", "value": f"{int(campeones.clientes)} clientes", "status": "good"},
    {"label": "Valor en riesgo de fuga", "value": f"${en_riesgo.valor_total:,.0f} MXN", "status": "critical"},
]

checklist = {
    "id": "riesgo_semana",
    "title": "Plan de llamadas de esta semana",
    "subtitle": f"{len(esta_semana)} clientes de \"En riesgo\" repartidos en {len(DIAS)} días ({CAPACIDAD_POR_DIA}/día). Marca cada uno al contactarlo — el progreso se guarda en este navegador.",
    "progress_noun": "contactados",
    "headers": ["Día", "Cliente", "Valor histórico", "Compras", "Última compra hace"],
    "rows": [
        {
            "id": r.cliente_id,
            "cells": [r.dia, r.cliente_id, f"${r.monto_total:,.0f}", int(r.frecuencia), f"{int(r.recencia_dias)} días"],
        }
        for r in esta_semana.itertuples()
    ],
}

scatter_points = [
    {
        "x": int(r.recencia_dias), "y": round(r.valor_percentil, 1),
        "label": f"{r.cliente_id} · ${r.monto_total:,.0f} MXN · {int(r.frecuencia)} compras",
        "status": r.cuadrante_status,
    }
    for r in agg.itertuples()
]

charts = [
    {
        "id": "chart_matriz", "type": "scatter", "full_width": True,
        "title": "Matriz recencia x valor: qué acción corresponde a cada cliente",
        "subtitle": f"{total_clientes:,} clientes — días desde última compra vs. percentil de valor histórico, divididos en la mediana de cada eje",
        "points": scatter_points,
        "x_label": "Días desde última compra (recencia)", "y_label": "Valor histórico (percentil de la cartera)",
        "x_unit": " días", "y_unit": " pct",
        "point_radius": 4, "point_alpha": 0.6,
        "status_labels": {
            "good": "Campeones", "critical": "En riesgo",
            "neutral": "Nuevos / Prometedores", "serious": "Hibernando",
        },
        "quadrant_lines": {"x": round(median_recencia, 1), "y": 50.0},
        "quadrant_labels": [
            {"corner": "top-left", "text": "CAMPEONES"},
            {"corner": "top-right", "text": "EN RIESGO"},
            {"corner": "bottom-left", "text": "NUEVOS"},
            {"corner": "bottom-right", "text": "HIBERNANDO"},
        ],
    },
    {
        "id": "chart_seg_count", "type": "bar",
        "title": "Clientes por cuadrante",
        "subtitle": "Tamaño de cada grupo de acción",
        "labels": quadrant_order,
        "datasets": [{
            "label": "Clientes",
            "data": [int(v) for v in seg_summary["clientes"]],
            "colors": [STATUS[STATUS_OF_QUADRANT[q]] for q in quadrant_order],
        }],
        "y_label": "Clientes",
    },
    {
        "id": "chart_seg_value", "type": "bar",
        "title": "Valor histórico total por cuadrante",
        "subtitle": "MXN acumulados en los últimos 12 meses",
        "labels": quadrant_order,
        "datasets": [{
            "label": "Valor total",
            "data": [round(v, 0) for v in seg_summary["valor_total"]],
            "colors": [STATUS[STATUS_OF_QUADRANT[q]] for q in quadrant_order],
        }],
        "y_label": "MXN",
    },
]

# ---- vistas por variable: Recencia, Frecuencia y Monto cruzadas de a pares -
# La matriz principal solo cruza Recencia x Valor. Estos dos scatters
# adicionales meten a Frecuencia en la lectura (R x F y F x Valor), cada uno
# coloreado por el mismo cuadrante para que se vea si la frecuencia separa
# a los grupos igual de bien que el valor histórico o no.
rf_points = [
    {
        "x": int(r.recencia_dias), "y": int(r.frecuencia),
        "label": f"{r.cliente_id} · {int(r.frecuencia)} compras",
        "status": r.cuadrante_status,
    }
    for r in agg.itertuples()
]
fv_points = [
    {
        "x": int(r.frecuencia), "y": round(r.valor_percentil, 1),
        "label": f"{r.cliente_id} · ${r.monto_total:,.0f} MXN",
        "status": r.cuadrante_status,
    }
    for r in agg.itertuples()
]
rfm_status_labels = {
    "good": "Campeones", "critical": "En riesgo",
    "neutral": "Nuevos / Prometedores", "serious": "Hibernando",
}
rfm_charts = [
    {
        "id": "chart_rf", "type": "scatter",
        "title": "Recencia vs. Frecuencia",
        "subtitle": "Días desde última compra vs. número de compras",
        "points": rf_points,
        "x_label": "Días desde última compra", "y_label": "Frecuencia (compras)",
        "x_unit": " días", "y_unit": " compras",
        "point_radius": 3, "point_alpha": 0.5,
        "status_labels": rfm_status_labels,
    },
    {
        "id": "chart_fv", "type": "scatter",
        "title": "Frecuencia vs. Valor histórico",
        "subtitle": "Número de compras vs. percentil de valor histórico",
        "points": fv_points,
        "x_label": "Frecuencia (compras)", "y_label": "Valor histórico (percentil)",
        "x_unit": " compras", "y_unit": " pct",
        "point_radius": 3, "point_alpha": 0.5,
        "status_labels": rfm_status_labels,
    },
]

insights = [
    f"El plan prioriza valor histórico dentro de \"En riesgo\": llamar primero al cliente de mayor gasto cada día protege el valor más grande con el mismo esfuerzo de llamada, en vez de contactar en el orden en que aparecen.",
    f"<b>En riesgo</b> ({int(en_riesgo.clientes)} clientes) concentra ${en_riesgo.valor_total:,.0f} MXN de valor histórico que se puede perder si no hay contacto proactivo — son clientes que ya demostraron que gastan, solo dejaron de comprar.",
    f"<b>Hibernando</b> ({int(seg_summary.loc['Hibernando','clientes'])} clientes, bajo valor y sin actividad reciente) no debería recibir el mismo presupuesto de marketing que Campeones o Nuevos — la matriz evita gastar igual en todos.",
    "Cada cuadrante tiene una sola acción comercial asociada (columna de la tabla) — la matriz solo vale si esa acción se ejecuta distinto por grupo, no si termina tratándose a todos igual.",
]

table = {
    "title": "Resumen por cuadrante",
    "headers": ["Cuadrante", "Clientes", "Valor promedio", "Valor total", "Acción recomendada"],
    "rows": [
        [q, int(row["clientes"]), f"${row['valor_promedio']:,.0f}", f"${row['valor_total']:,.0f}", ACCIONES[q]]
        for q, row in seg_summary.iterrows()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=5,
    title="Segmentación RFM y Priorización Comercial",
    tagline="No todos los clientes valen el mismo esfuerzo — la matriz de 4 cuadrantes dice a quién llamar hoy y a quién dejar de perseguir.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="top",
    drilldown_charts=rfm_charts,
    drilldown_title="Recencia, Frecuencia y Valor cruzados de a pares",
    banner=banner,
    checklist=checklist,
)

print(f"Clientes: {total_clientes} | Valor total: ${total_valor:,.0f} | En riesgo: {int(en_riesgo.clientes)} clientes / ${en_riesgo.valor_total:,.0f} MXN")
print("OK -> dashboard.html")
