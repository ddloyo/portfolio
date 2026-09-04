"""
Entrena un modelo de riesgo de churn (regresión logística) sobre la base
histórica, aplica el score a la cartera activa, la cruza con el gasto
mensual para formar una matriz riesgo x valor de 4 cuadrantes de acción,
y genera dashboard.html: banner con el plan de la semana (principio de
Minto), matriz interactiva, pirámide de cartera por gasto, histogramas por
variable (coloreados por cuadrante) y el plan de llamadas con checkboxes.

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) -- se usa como vista previa en el README. Para
regenerarla tras un cambio visual: abre dashboard.html en el navegador y
toma un screenshot de la página completa (recortando la tabla de llamadas
a unas pocas filas para que la imagen no quede kilométrica).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

from xia_style import STATUS
import dashboard as dash

df = pd.read_csv(ROOT / "data" / "clientes.csv")

FEATURES_NUM = ["antiguedad_meses", "gasto_mensual_mxn", "tickets_soporte_90d", "dias_desde_ultima_actividad", "usage_score"]
df["es_mensual"] = (df["tipo_contrato"] == "Mensual").astype(int)
FEATURES = FEATURES_NUM + ["es_mensual"]

X = df[FEATURES].values
y = df["churn_historico"].values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=21, stratify=y)
scaler = StandardScaler().fit(X_train)
model = LogisticRegression(max_iter=1000).fit(scaler.transform(X_train), y_train)

auc = roc_auc_score(y_test, model.predict_proba(scaler.transform(X_test))[:, 1])

# score a toda la cartera (simula "clientes activos hoy")
df["riesgo_churn"] = model.predict_proba(scaler.transform(X))[:, 1]

# La tasa base de churn es baja, así que la probabilidad cruda queda muy
# comprimida cerca de 0 con una cola larga -- un scatter sobre ese eje se ve
# aplastado contra el borde. Se usa el percentil de riesgo dentro de la
# cartera activa (0-100, distribuido uniforme por construcción) para el eje
# y para el corte de cuadrante, mientras la tabla de prioridad sigue
# mostrando la probabilidad real.
df["riesgo_percentil"] = df["riesgo_churn"].rank(pct=True) * 100

# ---- matriz riesgo x valor: 4 cuadrantes de acción -------------------------
# Split por mediana en ambos ejes: los 4 cuadrantes quedan balanceados en
# tamaño y la matriz es legible como scatter, en vez de 3 cuadrantes casi
# vacíos si se cortara en el top 15% de riesgo.
risk_split = 50.0  # mediana del percentil, por construcción
value_split = df["gasto_mensual_mxn"].median()

QUADRANTS = {
    (True, True): ("critical", "Rescate prioritario"),
    (True, False): ("serious", "Riesgo menor"),
    (False, True): ("good", "Clientes ancla"),
    (False, False): ("neutral", "Base estable"),
}
def quadrant_of(row):
    key = (row["riesgo_percentil"] >= risk_split, row["gasto_mensual_mxn"] >= value_split)
    return QUADRANTS[key]


df[["cuadrante_status", "cuadrante"]] = df.apply(quadrant_of, axis=1, result_type="expand")

quadrant_order = ["Rescate prioritario", "Riesgo menor", "Clientes ancla", "Base estable"]
resumen = (
    df.groupby("cuadrante")
    .agg(clientes=("cliente_id", "count"), ingreso_mensual=("gasto_mensual_mxn", "sum"))
    .reindex(quadrant_order)
)
resumen["pct"] = (resumen["clientes"] / len(df) * 100).round(1)

rescate = resumen.loc["Rescate prioritario"]
riesgo_menor = resumen.loc["Riesgo menor"]
ancla = resumen.loc["Clientes ancla"]
base_estable = resumen.loc["Base estable"]

# ---- plan operativo de la semana -------------------------------------------
# La pirámide Minto exige la respuesta primero: no "aquí está el riesgo de
# cada cliente" sino "esto es lo que hay que hacer esta semana". Rescate
# Prioritario (295 clientes) excede lo que un equipo puede llamar en una
# semana -- se define una capacidad explícita y se prioriza por gasto
# mensual dentro del cuadrante, para proteger primero el ingreso más grande
# con el mismo esfuerzo de llamada. Lo que no cabe pasa a la cola de la
# próxima semana en vez de fingir que todo se atiende hoy.
CAPACIDAD_POR_DIA = 20
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
CAPACIDAD_SEMANA = CAPACIDAD_POR_DIA * len(DIAS)

cola_rescate = df[df["cuadrante"] == "Rescate prioritario"].sort_values("gasto_mensual_mxn", ascending=False).reset_index(drop=True)
esta_semana = cola_rescate.iloc[:CAPACIDAD_SEMANA].copy()
backlog = cola_rescate.iloc[CAPACIDAD_SEMANA:]
esta_semana["dia"] = [DIAS[i // CAPACIDAD_POR_DIA] for i in range(len(esta_semana))]

ingreso_semana = esta_semana["gasto_mensual_mxn"].sum()
ingreso_backlog = backlog["gasto_mensual_mxn"].sum()

coef = pd.Series(model.coef_[0], index=FEATURES).sort_values()
readable_names = {
    "antiguedad_meses": "Antigüedad (meses)",
    "gasto_mensual_mxn": "Gasto mensual",
    "tickets_soporte_90d": "Tickets de soporte (90d)",
    "dias_desde_ultima_actividad": "Días sin actividad",
    "usage_score": "Score de uso del producto",
    "es_mensual": "Contrato mensual (vs. anual)",
}
coef.index = [readable_names[i] for i in coef.index]

# ---- interactive dashboard ------------------------------------------------
banner = {
    "label": "Esta semana",
    "headline": f"{len(esta_semana)} llamadas de retención prioritaria — ${ingreso_semana:,.0f} MXN/mes en juego",
    "subtext": (
        f"Ordenadas por gasto mensual, {CAPACIDAD_POR_DIA} por día de lunes a viernes: empieza el lunes por los clientes de mayor valor. "
        f"Quedan {len(backlog)} clientes en cola (${ingreso_backlog:,.0f} MXN/mes adicionales) para la próxima semana."
    ),
}

kpis = [
    {"label": "Llamadas esta semana", "value": f"{len(esta_semana)} de {int(rescate.clientes)}", "status": "critical"},
    {"label": "Cola automatizada", "value": f"{int(riesgo_menor.clientes)} clientes", "status": "serious"},
    {"label": "Backlog próxima semana", "value": f"{len(backlog)} clientes", "status": "warning"},
    {"label": "Sin acción esta semana", "value": f"{int(ancla.clientes + base_estable.clientes)} clientes", "status": "good"},
]

checklist = {
    "id": "rescate_semana",
    "title": "Plan de llamadas de esta semana",
    "subtitle": f"{len(esta_semana)} clientes de Rescate Prioritario repartidos en {len(DIAS)} días ({CAPACIDAD_POR_DIA}/día). Marca cada uno al contactarlo — el progreso se guarda en este navegador.",
    "progress_noun": "contactados",
    "headers": ["Día", "Cliente", "Gasto mensual", "Riesgo", "Días sin actividad", "Contrato"],
    "rows": [
        {
            "id": r.cliente_id,
            "cells": [r.dia, r.cliente_id, f"${r.gasto_mensual_mxn:,.0f}", f"{r.riesgo_churn*100:.0f}%", int(r.dias_desde_ultima_actividad), r.tipo_contrato],
        }
        for r in esta_semana.itertuples()
    ],
}

scatter_points = [
    {"x": round(r.riesgo_percentil, 1), "y": round(r.gasto_mensual_mxn, 2), "label": f"{r.cliente_id} ({r.riesgo_churn*100:.0f}% riesgo)", "status": r.cuadrante_status}
    for r in df.itertuples()
]

charts = [
    {
        "id": "chart_matriz", "type": "scatter", "full_width": True,
        "title": "Matriz riesgo x valor: qué acción corresponde a cada cliente",
        "subtitle": f"{len(df):,} clientes activos — riesgo relativo de churn vs. gasto mensual, divididos en la mediana de cada eje",
        "points": scatter_points,
        "x_label": "Riesgo relativo de churn (percentil)", "y_label": "Gasto mensual (MXN)",
        "x_unit": " pct", "y_unit": " MXN",
        "point_radius": 4, "point_alpha": 0.55,
        "status_labels": {
            "critical": "Rescate prioritario", "serious": "Riesgo menor",
            "good": "Clientes ancla", "neutral": "Base estable",
        },
        "quadrant_lines": {"x": risk_split, "y": round(value_split, 2)},
        "quadrant_labels": [
            {"corner": "top-left", "text": "CLIENTES ANCLA"},
            {"corner": "top-right", "text": "RESCATE PRIORITARIO"},
            {"corner": "bottom-left", "text": "BASE ESTABLE"},
            {"corner": "bottom-right", "text": "RIESGO MENOR"},
        ],
    },
    {
        "id": "chart_importance", "type": "bar",
        "title": "Qué empuja el riesgo de churn",
        "subtitle": "Coeficientes estandarizados del modelo (+ = más riesgo)",
        "labels": list(coef.index),
        "datasets": [{"label": "Efecto en el riesgo", "data": [round(v, 2) for v in coef.values]}],
    },
]

STATUS_OF_CUADRANTE = {"Rescate prioritario": "critical", "Riesgo menor": "serious", "Clientes ancla": "good", "Base estable": "neutral"}


def stacked_by_cuadrante(bin_col, bin_order=None):
    """Cuenta clientes por bin (columna ya categorizada/discreta) x cuadrante,
    devuelve un dataset de Chart.js por cuadrante coloreado con su color de
    la matriz, para que las 4 barras apiladas se lean con el mismo código de
    color que el scatter. `bin_order` fuerza el orden de las filas para
    columnas planas (no Categorical) donde groupby ordenaría alfabéticamente."""
    counts = df.groupby([bin_col, "cuadrante"], observed=True).size().unstack(fill_value=0).reindex(columns=quadrant_order, fill_value=0)
    if bin_order is not None:
        counts = counts.reindex(bin_order, fill_value=0)
    return [
        {"label": q, "data": [int(v) for v in counts[q]], "colors": STATUS[STATUS_OF_CUADRANTE[q]]}
        for q in quadrant_order
    ]


# ---- pirámide poblacional: gasto mensual x cuadrante -----------------------
# Barras horizontales apiladas y espejadas: bajo riesgo (base estable +
# clientes ancla) a la izquierda en negativo, alto riesgo (riesgo menor +
# rescate prioritario) a la derecha en positivo -- el eje de valores usa
# value_format "abs_count" para mostrar conteos siempre positivos pese al
# espejo. Bins de $400 (0-4,000 MXN), orden descendente para que el gasto
# alto quede arriba, como una pirámide poblacional clásica.
gasto_edges = list(range(0, 4001, 400))
gasto_labels = [f"${gasto_edges[i]:,}-{gasto_edges[i+1]:,}" for i in range(len(gasto_edges) - 1)]
df["gasto_bin"] = pd.cut(df["gasto_mensual_mxn"], bins=gasto_edges, labels=gasto_labels, include_lowest=True)
gasto_counts = df.groupby(["gasto_bin", "cuadrante"], observed=True).size().unstack(fill_value=0).reindex(columns=quadrant_order, fill_value=0)
gasto_counts = gasto_counts.iloc[::-1]  # bins de mayor a menor gasto, arriba primero

pyramid_max = max(
    (gasto_counts["Base estable"] + gasto_counts["Clientes ancla"]).max(),
    (gasto_counts["Riesgo menor"] + gasto_counts["Rescate prioritario"]).max(),
)

pyramid_chart = {
    "id": "chart_pyramid", "type": "bar", "horizontal": True, "stacked": True, "full_width": True,
    "title": "Pirámide de la cartera: bajo riesgo vs. alto riesgo por nivel de gasto",
    "subtitle": "Izquierda = base estable + clientes ancla (bajo riesgo) · Derecha = riesgo menor + rescate prioritario (alto riesgo)",
    "labels": list(gasto_counts.index),
    "datasets": [
        {"label": "Base estable", "data": [-int(v) for v in gasto_counts["Base estable"]], "colors": STATUS["neutral"]},
        {"label": "Clientes ancla", "data": [-int(v) for v in gasto_counts["Clientes ancla"]], "colors": STATUS["good"]},
        {"label": "Riesgo menor", "data": [int(v) for v in gasto_counts["Riesgo menor"]], "colors": STATUS["serious"]},
        {"label": "Rescate prioritario", "data": [int(v) for v in gasto_counts["Rescate prioritario"]], "colors": STATUS["critical"]},
    ],
    "value_format": "abs_count",
    "value_min": -pyramid_max * 1.05, "value_max": pyramid_max * 1.05,
    "y_label": "Clientes",
}
charts.append(pyramid_chart)

# ---- histogramas por variable, coloreados por cuadrante --------------------
usage_edges = list(range(0, 101, 10))
usage_labels = [f"{usage_edges[i]}-{usage_edges[i+1]}" for i in range(len(usage_edges) - 1)]
df["usage_bin"] = pd.cut(df["usage_score"], bins=usage_edges, labels=usage_labels, include_lowest=True)

antiguedad_edges = list(range(0, 61, 6))
antiguedad_labels = [f"{antiguedad_edges[i]}-{antiguedad_edges[i+1]}" for i in range(len(antiguedad_edges) - 1)]
df["antiguedad_bin"] = pd.cut(df["antiguedad_meses"], bins=antiguedad_edges, labels=antiguedad_labels, include_lowest=True)

actividad_edges = list(range(0, 181, 20))
actividad_labels = [f"{actividad_edges[i]}-{actividad_edges[i+1]}" for i in range(len(actividad_edges) - 1)]
df["actividad_bin"] = pd.cut(df["dias_desde_ultima_actividad"], bins=actividad_edges, labels=actividad_labels, include_lowest=True)

histogram_charts = [
    {
        "id": "chart_hist_usage", "type": "bar", "stacked": True,
        "title": "Score de uso del producto",
        "subtitle": "A menor uso, mayor concentración de alto riesgo (rojo/café)",
        "labels": usage_labels, "datasets": stacked_by_cuadrante("usage_bin"), "y_label": "Clientes",
    },
    {
        "id": "chart_hist_antiguedad", "type": "bar", "stacked": True,
        "title": "Antigüedad (meses)",
        "subtitle": "Los clientes más nuevos concentran más riesgo que los antiguos",
        "labels": antiguedad_labels, "datasets": stacked_by_cuadrante("antiguedad_bin"), "y_label": "Clientes",
    },
    {
        "id": "chart_hist_gasto", "type": "bar", "stacked": True,
        "title": "Gasto mensual (MXN)",
        "subtitle": "El riesgo aparece en todos los niveles de gasto — por eso importa cruzarlo con valor",
        "labels": gasto_labels, "datasets": stacked_by_cuadrante("gasto_bin"), "y_label": "Clientes",
    },
    {
        "id": "chart_hist_tickets", "type": "bar", "stacked": True,
        "title": "Tickets de soporte (90 días)",
        "subtitle": "Más tickets recientes, más concentración de alto riesgo",
        "labels": [str(v) for v in sorted(df["tickets_soporte_90d"].unique())],
        "datasets": stacked_by_cuadrante("tickets_soporte_90d", bin_order=sorted(df["tickets_soporte_90d"].unique())), "y_label": "Clientes",
    },
    {
        "id": "chart_hist_contrato", "type": "bar", "stacked": True,
        "title": "Tipo de contrato",
        "subtitle": "El contrato mensual concentra más riesgo que el anual",
        "labels": ["Mensual", "Anual"], "datasets": stacked_by_cuadrante("tipo_contrato", bin_order=["Mensual", "Anual"]), "y_label": "Clientes",
    },
    {
        "id": "chart_hist_actividad", "type": "bar", "stacked": True,
        "title": "Días desde la última actividad",
        "subtitle": "La señal más fuerte del modelo: más días inactivo, más riesgo",
        "labels": actividad_labels, "datasets": stacked_by_cuadrante("actividad_bin"), "y_label": "Clientes",
    },
]

insights = [
    f"El plan prioriza gasto mensual dentro de Rescate Prioritario: llamar primero a los {CAPACIDAD_POR_DIA} clientes de mayor valor cada día protege el ingreso más grande con el mismo esfuerzo de llamada, en vez de ordenar solo por score de riesgo.",
    f"\"Riesgo menor\" ({int(riesgo_menor.clientes)} clientes, {riesgo_menor.pct}%, alto riesgo pero bajo gasto) no entra al plan de llamadas — una campaña automatizada de email/WhatsApp cuesta lo mismo para 1 cliente que para {int(riesgo_menor.clientes)}, así que ahí se gana eficiencia sin ocupar tiempo del equipo comercial.",
    f"\"Clientes ancla\" y \"Base estable\" (bajo riesgo, {int(ancla.clientes + base_estable.clientes)} clientes) no requieren acción esta semana — se revisan en la cadencia mensual. Ancla (${ancla.ingreso_mensual:,.0f} MXN/mes) es la cartera más valiosa y candidata a upsell o plan anual en esa revisión, no solo \"sin riesgo\".",
    "Los días sin actividad y los tickets de soporte recientes son las señales más fuertes del modelo — más que la antigüedad del cliente. Si el backlog de la próxima semana sigue creciendo semana a semana, vale la pena revisar la capacidad del equipo antes de mover el corte de \"alto riesgo\".",
]

dash.render(
    ROOT / "dashboard.html",
    project_no=4,
    title="Predicción de Riesgo de Churn",
    tagline="De 'sabemos que algo bajó' a 'aquí está el plan de llamadas de esta semana, en orden' — planeación semanal y seguimiento diario, no solo un score.",
    banner=banner,
    kpis=kpis,
    checklist=checklist,
    charts=charts,
    insights=insights,
    drilldown_charts=histogram_charts,
    drilldown_title=f"Revisión mensual (no semanal): distribución de la cartera y salud del modelo — AUC {auc:.2f}",
)

print(f"AUC: {auc:.3f} | Esta semana: {len(esta_semana)} llamadas (${ingreso_semana:,.0f} MXN/mes) | Backlog: {len(backlog)} (${ingreso_backlog:,.0f} MXN/mes)")
print("OK -> dashboard.html")
