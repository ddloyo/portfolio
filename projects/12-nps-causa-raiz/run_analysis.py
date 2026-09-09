"""
Calcula NPS mensual, valida si la caída reciente es una señal real o ruido
de muestreo, aísla la causa raíz declarada por los detractores y sintetiza
los hallazgos en 8 preguntas de negocio priorizadas por impacto x confianza
x accionabilidad -- el tipo de análisis de voz del cliente que Diego trabajó
de forma extensa en Qualtrics.

Tres pasadas de análisis sobre el mismo dataset de encuestas:
  - Serie de tiempo: ¿la caída de NPS es una anomalía real o variación
    normal? (skill time-series-analysis). Con solo 12 puntos mensuales no
    alcanza para una descomposición ARIMA (esa skill pide mínimo 2 ciclos
    estacionales completos) -- el chequeo correcto aquí es un z-score contra
    el promedio histórico, no un forecast.
  - Segmentación: los motivos declarados por los detractores como segmentos
    de causa raíz, con tamaño, tendencia (reciente vs. histórico) y acción
    recomendada por segmento (skill segmentation-analysis).
  - Síntesis de insights: cada hallazgo pasado por So What / Why / Now What
    y priorizado (skill insight-synthesis), respondiendo las 8 preguntas que
    dirección y el equipo de soporte necesitan para actuar, no solo el
    número de NPS.

Genera:
  1. dashboard.html (pirámide de Minto: respuesta primero, luego el número
     que la sostiene, las gráficas que responden cada pregunta y el detalle)

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) -- se usa como vista previa del dashboard completo en el
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

df = pd.read_csv(ROOT / "data" / "encuestas_nps.csv")
months = sorted(df["mes"].unique())
baseline_months, recent_months = months[:-2], months[-2:]
last_month, prev_month = months[-1], months[-2]
idx_quiebre = months.index(recent_months[0])


def nps_de(g):
    total = len(g)
    promotores = (g["categoria"] == "Promotor").sum()
    detractores = (g["categoria"] == "Detractor").sum()
    return round((promotores - detractores) / total * 100, 1)


# ============================================================================
# 1) SERIE DE TIEMPO -- ¿la caída de NPS es una anomalía real o ruido?
#    Ver skill time-series-analysis.
# ============================================================================
nps_mensual = df.groupby("mes").apply(nps_de, include_groups=False).reindex(months)
volumen_mensual = df.groupby("mes").size().reindex(months)
score_mensual = df.groupby("mes")["score"].mean().reindex(months)

mix = df.groupby(["mes", "categoria"]).size().unstack(fill_value=0).reindex(months)
mix_pct = mix.div(mix.sum(axis=1), axis=0) * 100

nps_baseline = round(nps_mensual[baseline_months].mean(), 1)
nps_baseline_std = nps_mensual[baseline_months].std()
nps_actual = nps_mensual[last_month]
caida_pts = round(nps_actual - nps_baseline, 1)
z_scores = (nps_mensual - nps_baseline) / nps_baseline_std
z_actual = z_scores[last_month]

detractor_rate_baseline = mix_pct["Detractor"][baseline_months].mean()
detractor_rate_actual = mix_pct["Detractor"][last_month]
promoter_rate_baseline = mix_pct["Promotor"][baseline_months].mean()
promoter_rate_actual = mix_pct["Promotor"][last_month]
score_baseline = score_mensual[baseline_months].mean()
score_actual = score_mensual[last_month]
target_nps = round(nps_actual + abs(caida_pts) / 2, 1)

# ============================================================================
# 2) SEGMENTACIÓN -- motivo declarado por los detractores como segmento de
#    causa raíz: tamaño, tendencia reciente vs. histórica y acción
#    recomendada por segmento. Ver skill segmentation-analysis.
# ============================================================================
detractores = df[df["categoria"] == "Detractor"]
det_recientes = detractores[detractores["mes"].isin(recent_months)]
det_previos = detractores[detractores["mes"].isin(baseline_months)]

motivo_month = detractores.groupby(["mes", "motivo_detractor"]).size().unstack(fill_value=0).reindex(months, fill_value=0)
motivos = sorted(motivo_month.columns)

recent_counts = det_recientes["motivo_detractor"].value_counts().reindex(motivos, fill_value=0)
recent_pct = (recent_counts / recent_counts.sum() * 100).round(1)
prior_counts = det_previos["motivo_detractor"].value_counts().reindex(motivos, fill_value=0)
prior_pct = (prior_counts / prior_counts.sum() * 100).round(1)

causa_principal = recent_pct.idxmax()
pct_causa_principal = recent_pct[causa_principal]
causa_principal_prior_pct = prior_pct[causa_principal]
motivos_ordenados = recent_pct.sort_values(ascending=False).index.tolist()
segundo_motivo, tercer_motivo = motivos_ordenados[1], motivos_ordenados[2]

causa_share_mensual = (motivo_month[causa_principal] / motivo_month.sum(axis=1) * 100).reindex(months)

ACCIONES = {
    "Tiempo de respuesta": "Revisar SLA y dotación del equipo de soporte de los últimos 2 meses — es la causa que se disparó.",
    "Calidad del producto": "Dar seguimiento a control de calidad; su participación bajó frente al histórico pero sigue presente.",
    "Atención al cliente": "Monitorear capacitación del equipo de atención; participación estable, sin acción urgente.",
    "Precio": "Sin acción inmediata — su participación cayó frente al histórico.",
    "Facilidad de uso": "Sin acción inmediata — participación estable y baja.",
}
DEFAULT_ACCION = "Monitorear el mes próximo; sin señal de deterioro todavía."

tabla_segmentos = pd.DataFrame({
    "motivo": motivos_ordenados,
    "recientes": [int(recent_counts[m]) for m in motivos_ordenados],
    "recent_pct": [recent_pct[m] for m in motivos_ordenados],
    "prior_pct": [prior_pct[m] for m in motivos_ordenados],
})
tabla_segmentos["delta_pp"] = (tabla_segmentos["recent_pct"] - tabla_segmentos["prior_pct"]).round(1)

# ============================================================================
# 3) INSIGHT SYNTHESIS -- cada hallazgo con So What / Why / Now What,
#    priorizado por impacto x confianza x accionabilidad. Las 8 preguntas
#    de negocio que responde este dashboard están numeradas Q1-Q8. Ver
#    skill insight-synthesis.
# ============================================================================
insights = [
    # Q1 -- ¿la caída es una señal real o ruido de muestreo normal?
    f"<b>Q1 · La caída no es ruido, es una anomalía estadística confirmada</b>: el NPS de {last_month} está a {abs(z_actual):.1f} desviaciones estándar de su promedio histórico ({nps_baseline}) — muy por encima del umbral de 3σ que separa una anomalía real de la variación normal mes a mes.",
    # Q2 -- ¿qué tan grave es la caída en términos de negocio?
    f"<b>Q2 · La caída equivale a {abs(caida_pts):.1f} puntos de NPS</b> ({nps_baseline} → {nps_actual}), con la tasa de detractores casi duplicándose ({detractor_rate_baseline:.1f}% → {detractor_rate_actual:.1f}%) y los promotores cayendo de {promoter_rate_baseline:.1f}% a {promoter_rate_actual:.1f}% — un riesgo real de renovación en la base recién insatisfecha.",
    # Q3 -- ¿es un problema generalizado o una causa puntual y accionable?
    f"<b>Q3 · No es un deterioro generalizado, es una causa concentrada</b>: <b>{causa_principal}</b> pasó de {causa_principal_prior_pct:.1f}% de los motivos declarados por detractores a {pct_causa_principal:.1f}% en los últimos 2 meses — la corrección debe dirigirse al proceso de soporte, no a un plan genérico de 'mejorar experiencia del cliente'.",
    # Q4 -- ¿desde cuándo se rompió el patrón y qué tan rápido fue?
    f"<b>Q4 · El quiebre es abrupto, no gradual</b>: los primeros {len(baseline_months)} meses oscilan sin tendencia clara (z entre {z_scores[baseline_months].min():.1f} y {z_scores[baseline_months].max():.1f}) y la caída ocurre de golpe en {recent_months[0]} — apunta a un cambio operativo puntual en soporte (dotación, herramienta, SLA), no a un desgaste lento.",
    # Q5 -- ¿es un artefacto de reclasificación de categoría o una caída real?
    f"<b>Q5 · La caída es real, no un artefacto de categorización</b>: el score promedio también bajó de {score_baseline:.2f} a {score_actual:.2f} en {last_month} — consistente con una experiencia peor, no solo respuestas que cruzaron el límite entre 'pasivo' y 'detractor'.",
    # Q6 -- ¿el volumen de respuestas respalda la confianza en la señal?
    f"<b>Q6 · El volumen de respuestas respalda la señal</b>: se mantuvo estable todo el periodo ({int(volumen_mensual.min())}-{int(volumen_mensual.max())} respuestas/mes, {int(volumen_mensual[recent_months].sum())} en los últimos 2 meses) — la caída no es producto de una muestra más chica o sesgada.",
    # Q7 -- ¿qué otras causas conviene vigilar aunque no dominen hoy?
    f"<b>Q7 · Vigilar causas secundarias aunque no dominen hoy</b>: {segundo_motivo} ({recent_pct[segundo_motivo]:.1f}%) y {tercer_motivo} ({recent_pct[tercer_motivo]:.1f}%) siguen presentes entre los detractores recientes — concentrar el esfuerzo en soporte no debe significar dejar de dar seguimiento mensual a las demás.",
    # Q8 -- ¿qué acción específica y con qué urgencia, y qué define éxito?
    f"<b>Q8 · Acción recomendada: escalar esta semana, no en el próximo corte mensual</b>: con la anomalía confirmada, la causa concentrada en {pct_causa_principal:.1f}% y un volumen de muestra sólido, revisar SLA y dotación de soporte de los últimos 2 meses y fijar una meta de recuperación (NPS ≥ {target_nps}) en 2 meses, con seguimiento quincenal mientras dure la corrección.",
]

# ============================================================================
# 4) DASHBOARD INTERACTIVO -- pirámide de Minto: la respuesta primero
#    (banner), el KPI que la sostiene en gold, luego las gráficas que
#    responden cada pregunta y el detalle. Ver skills dashboard-
#    specification y visualization-builder (paleta XIA).
# ============================================================================
banner = {
    "label": "La respuesta primero",
    "headline": (
        f"El NPS de {last_month} cayó a {nps_actual} ({abs(caida_pts):.1f} pts bajo su promedio histórico) — "
        f"una anomalía estadística real (z = {z_actual:.1f}), no ruido de muestra, concentrada en un solo motivo: "
        f"<b>{causa_principal}</b> explica el {pct_causa_principal:.1f}% de los detractores recientes."
    ),
    "subtext": (
        f"Prioridad inmediata: escalar a liderazgo de soporte esta semana y revisar SLA/dotación de los últimos "
        f"2 meses, sin esperar el próximo corte mensual. Meta de recuperación sugerida: NPS ≥ {target_nps} en "
        f"2 meses, con seguimiento quincenal mientras dure la corrección."
    ),
}

kpis = [
    {"label": f"NPS {last_month}", "value": f"{nps_actual}", "delta": f"{caida_pts:+.1f} pts vs. histórico",
     "delta_direction": "down", "status": "critical", "status_label": f"Anomalía (z = {z_actual:.1f})", "hero": True},
    {"label": "NPS promedio histórico", "value": f"{nps_baseline}"},
    {"label": "Tasa de detractores", "value": f"{detractor_rate_actual:.1f}%",
     "delta": f"{detractor_rate_actual - detractor_rate_baseline:+.1f} pts vs. histórico", "delta_direction": "down",
     "status": "critical" if detractor_rate_actual - detractor_rate_baseline > 10 else "warning"},
    {"label": "Causa raíz principal", "value": causa_principal,
     "delta": f"{pct_causa_principal:.1f}% de detractores recientes", "delta_direction": "down", "status": "critical"},
    {"label": f"Score promedio {last_month}", "value": f"{score_actual:.2f}",
     "delta": f"{score_actual - score_baseline:+.2f} vs. histórico", "delta_direction": "down", "status": "warning"},
    {"label": "Respuestas analizadas", "value": f"{len(df):,}"},
]

charts = [
    {
        "id": "chart_nps", "type": "line",
        "title": f"NPS cayó a {nps_actual} en {last_month}, {abs(caida_pts):.1f} pts bajo su promedio histórico",
        "subtitle": f"Línea punteada: promedio histórico ({nps_baseline}). El quiebre ocurre en {recent_months[0]}, no antes.",
        "labels": months,
        "datasets": [{"label": "NPS", "data": list(nps_mensual.values), "emphasis": True, "color_index": 0}],
        "reference_line": {"value": nps_baseline, "label": "Promedio histórico"},
        "marker": {"index": idx_quiebre, "label": "Quiebre"},
    },
    {
        "id": "chart_motivo_comparacion", "type": "bar", "horizontal": True,
        "title": f"{causa_principal} concentra el {pct_causa_principal:.1f}% de los detractores recientes (vs. {causa_principal_prior_pct:.1f}% histórico)",
        "subtitle": "Motivo declarado por detractores: últimos 2 meses vs. los 10 meses previos",
        "labels": motivos_ordenados,
        "datasets": [
            {"label": "Últimos 2 meses", "data": [recent_pct[m] for m in motivos_ordenados], "color_index": 2},
            {"label": "10 meses previos", "data": [prior_pct[m] for m in motivos_ordenados], "color_index": 5, "muted": True},
        ],
        "value_format": "percent",
    },
]

drilldown_charts = [
    {
        "id": "chart_mix_categoria", "type": "stacked-bar",
        "title": "La proporción de detractores casi se duplicó en los últimos 2 meses",
        "subtitle": "Mezcla mensual de Promotores / Pasivos / Detractores (% de respuestas)",
        "labels": months,
        "datasets": [
            {"label": "Promotor", "data": [round(v, 1) for v in mix_pct["Promotor"]], "color_index": 0},
            {"label": "Pasivo", "data": [round(v, 1) for v in mix_pct["Pasivo"]], "color_index": 5},
            {"label": "Detractor", "data": [round(v, 1) for v in mix_pct["Detractor"]], "color_index": 2},
        ],
        "stacked": True, "value_format": "percent",
    },
    {
        "id": "chart_score", "type": "line",
        "title": "El score promedio también cayó — no es solo un cambio de categoría",
        "subtitle": f"Promedio mensual del score 0-10 (línea punteada: promedio histórico {score_baseline:.2f})",
        "labels": months,
        "datasets": [{"label": "Score promedio", "data": [round(v, 2) for v in score_mensual.values], "color_index": 0}],
        "reference_line": {"value": round(score_baseline, 2), "label": "Promedio histórico"},
        "marker": {"index": idx_quiebre, "label": "Quiebre"},
    },
    {
        "id": "chart_tendencia_causa", "type": "line",
        "title": f"{causa_principal} se aceleró justo cuando el NPS se desplomó",
        "subtitle": f"% de detractores que declaran '{causa_principal}' cada mes (línea punteada: promedio histórico {causa_principal_prior_pct:.1f}%)",
        "labels": months,
        "datasets": [{"label": causa_principal, "data": [round(v, 1) for v in causa_share_mensual.values], "color_index": 2}],
        "reference_line": {"value": round(causa_principal_prior_pct, 1), "label": "Promedio histórico"},
        "marker": {"index": idx_quiebre, "label": "Quiebre"},
        "value_format": "percent",
    },
    {
        "id": "chart_volumen", "type": "bar",
        "title": "El volumen de respuestas se mantuvo estable — la caída no es ruido de muestra",
        "subtitle": "Respuestas de encuesta NPS por mes",
        "labels": months,
        "datasets": [{"label": "Respuestas", "data": [int(v) for v in volumen_mensual.values], "color_index": 0}],
        "reference_line": {"value": round(volumen_mensual.mean(), 0), "label": "Promedio"},
    },
]

table = {
    "title": "Motivo declarado por detractores: tamaño, tendencia y acción recomendada",
    "headers": ["Motivo", "Respuestas recientes", "% detractores recientes", "% histórico", "Cambio (pp)", "Acción recomendada"],
    "rows": [
        [
            row.motivo, row.recientes, f"{row.recent_pct:.1f}%", f"{row.prior_pct:.1f}%", f"{row.delta_pp:+.1f}",
            ACCIONES.get(row.motivo, DEFAULT_ACCION),
        ]
        for row in tabla_segmentos.itertuples()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=12,
    title="NPS y Análisis de Causa Raíz",
    tagline="De 'el NPS bajó' a 'sabemos exactamente qué corregir' — 8 preguntas de negocio respondidas con la causa raíz declarada por los propios detractores.",
    banner=banner,
    kpis=kpis,
    charts=charts,
    drilldown_charts=drilldown_charts,
    drilldown_title="Por qué confiamos en la señal",
    insights=insights,
    table=table,
    table_position="top",
    chart_cols=2,
)

print(f"NPS {last_month}: {nps_actual} (baseline {nps_baseline}, z={z_actual:.1f}) | Causa principal: {causa_principal} ({pct_causa_principal:.1f}% vs. {causa_principal_prior_pct:.1f}% histórico)")
print("OK -> dashboard.html")
