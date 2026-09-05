"""
Calcula CAC, LTV, ratio LTV:CAC, segmentación tipo BCG (gasto vs. retorno) y
tendencia por canal de marketing, y genera dashboard.html — banner con la
respuesta primero (pirámide de Minto), matriz de segmentación, tendencia de
CAC y tabla de recomendación por canal.

Todo el texto (banner, KPIs, insights) se calcula a partir de los datos, no
de nombres de canal hardcodeados, para que siga siendo correcto si cambia el
número de meses o el resultado de data/generate_data.py.

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) -- se usa como vista previa en el README. Para
regenerarla tras un cambio visual: abre dashboard.html en el navegador y
toma un screenshot de la página completa.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import numpy as np
import pandas as pd
import dashboard as dash

UMBRAL_SANO = 3.0
CANALES_ORDEN = ["Referidos", "SEO / Orgánico", "Google Ads", "Meta Ads", "Email marketing", "Eventos / Ferias"]

df = pd.read_csv(ROOT / "data" / "marketing_canales.csv")
df["canal"] = pd.Categorical(df["canal"], categories=CANALES_ORDEN, ordered=True)
df = df.sort_values(["canal", "mes"])

meses = sorted(df["mes"].unique())
n_meses = len(meses)
periodo = f"{n_meses} meses"

# ---- agregado por canal -------------------------------------------------
agg = df.groupby("canal", observed=True).agg(
    gasto_total=("gasto_mxn", "sum"),
    clientes_nuevos=("clientes_nuevos", "sum"),
    ticket_promedio=("ticket_promedio_mxn", "first"),
    meses_retencion=("meses_retencion_prom", "first"),
    margen=("margen_bruto", "first"),
).reset_index()

agg["cac"] = (agg["gasto_total"] / agg["clientes_nuevos"]).round(0)
# LTV simplificado: compras mensuales asumidas ~1/mes * ticket * margen * meses de retención
agg["ltv"] = (agg["ticket_promedio"] * agg["margen"] * agg["meses_retencion"]).round(0)
agg["ratio_ltv_cac"] = (agg["ltv"] / agg["cac"]).round(2)
agg["payback_meses"] = (agg["cac"] / (agg["ticket_promedio"] * agg["margen"])).round(1)

# ---- tendencia por canal (primer vs. último mes) -------------------------
df["cac_mensual"] = df["gasto_mxn"] / df["clientes_nuevos"]
df["ltv_mensual"] = df["ticket_promedio_mxn"] * df["margen_bruto"] * df["meses_retencion_prom"]
df["ratio_mensual"] = df["ltv_mensual"] / df["cac_mensual"]
df["en_riesgo"] = df["ratio_mensual"] < UMBRAL_SANO

trend_rows = []
for canal, g in df.groupby("canal", sort=False, observed=True):
    g = g.sort_values("mes").reset_index(drop=True)
    cli_change_pct = (g["clientes_nuevos"].iloc[-1] - g["clientes_nuevos"].iloc[0]) / g["clientes_nuevos"].iloc[0] * 100
    cac_change_pct = (g["cac_mensual"].iloc[-1] - g["cac_mensual"].iloc[0]) / g["cac_mensual"].iloc[0] * 100
    trend_rows.append({
        "canal": canal,
        "cac_mensual_serie": g["cac_mensual"].round(0).tolist(),
        "cac_change_pct": round(cac_change_pct, 1),
        "cli_change_pct": round(cli_change_pct, 1),
    })
trend = pd.DataFrame(trend_rows)
agg = agg.merge(trend, on="canal")

# ---- segmentación tipo BCG (gasto vs. ratio LTV:CAC) ---------------------
mediana_gasto = agg["gasto_total"].median()
agg["seg_gasto"] = np.where(agg["gasto_total"] >= mediana_gasto, "alto", "bajo")
agg["seg_ratio"] = np.where(agg["ratio_ltv_cac"] >= UMBRAL_SANO, "saludable", "riesgo")


def cuadrante(r):
    if r["seg_ratio"] == "riesgo":
        return "Recorte prioritario" if r["seg_gasto"] == "alto" else "Optimizar antes de escalar"
    return "Mantener / vigilar" if r["seg_gasto"] == "alto" else "Escalar — alto retorno, bajo gasto"


def punto_status(r):
    if r["seg_ratio"] == "riesgo":
        return "critical"
    return "warning" if r["seg_gasto"] == "alto" else "good"


def recomendacion(r):
    if r["seg_ratio"] == "riesgo":
        if r["cli_change_pct"] > 20:
            return "Optimizar y monitorear — mejorando, aún no cruza el benchmark"
        return "Recorte prioritario — sin mejora y por debajo del benchmark"
    if r["seg_gasto"] == "alto":
        return "Mantener con vigilancia — retorno sano pero tendencia en enfriamiento"
    if r["cli_change_pct"] < -5:
        return "Escalar con cautela — señal de techo de capacidad"
    return "Escalar agresivamente — mayor prioridad de inversión"


agg["cuadrante"] = agg.apply(cuadrante, axis=1)
agg["punto_status"] = agg.apply(punto_status, axis=1)
agg["recomendacion"] = agg.apply(recomendacion, axis=1)
agg = agg.sort_values("ratio_ltv_cac", ascending=False).reset_index(drop=True)

total_gasto = agg["gasto_total"].sum()
total_clientes = agg["clientes_nuevos"].sum()
canal_top = agg.iloc[0]
canal_peor = agg.sort_values("ratio_ltv_cac").iloc[0]
riesgo_df = agg[agg["seg_ratio"] == "riesgo"].sort_values("gasto_total", ascending=False)
saludable_bajo = agg[(agg["seg_ratio"] == "saludable") & (agg["seg_gasto"] == "bajo")].sort_values("ratio_ltv_cac", ascending=False)
saludable_alto = agg[(agg["seg_ratio"] == "saludable") & (agg["seg_gasto"] == "alto")]
pct_gasto_riesgo = riesgo_df["gasto_total"].sum() / total_gasto * 100
pct_gasto_saludable_bajo = saludable_bajo["gasto_total"].sum() / total_gasto * 100

# % del gasto mensual en canales por debajo del benchmark, mes a mes (para el hero chart)
riesgo_mensual = df.groupby("mes").apply(
    lambda g: g.loc[g["en_riesgo"], "gasto_mxn"].sum() / g["gasto_mxn"].sum() * 100,
    include_groups=False,
).round(1)
riesgo_mensual = riesgo_mensual.reindex(meses)


def lista_canales(nombres):
    nombres = list(nombres)
    if len(nombres) <= 1:
        return nombres[0] if nombres else ""
    return ", ".join(nombres[:-1]) + f" y {nombres[-1]}"


# ---- narrativa Minto (banner + recomendación) ----------------------------
canal_recorte = riesgo_df.sort_values("cli_change_pct").iloc[0] if not riesgo_df.empty else None
canales_optimizar = riesgo_df[riesgo_df["canal"] != (canal_recorte["canal"] if canal_recorte is not None else None)]
canales_optimizar = canales_optimizar[canales_optimizar["cli_change_pct"] > 20]
canal_cautela = agg[(agg["seg_ratio"] == "saludable") & (agg["cli_change_pct"] < -5)]
canal_cautela = canal_cautela.iloc[0] if not canal_cautela.empty else None
canales_escalar = saludable_bajo[saludable_bajo["canal"] != (canal_cautela["canal"] if canal_cautela is not None else None)]

recomendacion_partes = []
if canal_recorte is not None and not canales_escalar.empty:
    recomendacion_partes.append(
        f"mover presupuesto de {canal_recorte['canal']} (el de peor tendencia entre los canales de riesgo) "
        f"hacia {lista_canales(canales_escalar['canal'])} (mejores ratios, con capacidad de crecer)"
    )
if not canales_optimizar.empty:
    recomendacion_partes.append(
        f"mantener {lista_canales(canales_optimizar['canal'])} en optimización porque su tendencia mejora"
    )
if canal_cautela is not None:
    recomendacion_partes.append(
        f"escalar {canal_cautela['canal']} con cautela — ya muestra señales de techo de capacidad"
    )
banner_subtext = f"Recomendación para el próximo trimestre: {'; '.join(recomendacion_partes)}." if recomendacion_partes else ""

banner = {
    "label": "La respuesta primero",
    "headline": (
        f"{pct_gasto_riesgo:.0f}% del presupuesto de marketing ({lista_canales(riesgo_df['canal'])}) no cubre el "
        f"benchmark de retorno {UMBRAL_SANO:.0f}:1 — mientras los canales más eficientes reciben apenas "
        f"{pct_gasto_saludable_bajo:.0f}% del gasto."
    ) if not riesgo_df.empty else "Todos los canales cubren el benchmark de retorno — el foco es priorizar dónde escalar más.",
    "subtext": banner_subtext,
}

hero_kpi = {
    "label": f"% del gasto en canales por debajo del benchmark {UMBRAL_SANO:.0f}:1",
    "value": f"{pct_gasto_riesgo:.1f}%",
    "status": "critical" if pct_gasto_riesgo >= 40 else "warning" if pct_gasto_riesgo > 0 else "good",
    "status_label": "Riesgo estructural" if pct_gasto_riesgo >= 40 else "Vigilar",
}
hero_chart = {
    "id": "chart_hero_riesgo", "type": "line",
    "labels": meses,
    "datasets": [{"label": "% del gasto en canales de riesgo", "data": riesgo_mensual.tolist(), "emphasis": True}],
}

top_change = canal_top["cli_change_pct"]
kpis = [
    {"label": f"Inversión total ({periodo})", "value": f"${total_gasto:,.0f} MXN"},
    {"label": "Clientes nuevos totales", "value": f"{int(total_clientes):,}"},
    {"label": "Mejor canal (LTV:CAC)", "value": f"{canal_top['canal']} ({canal_top['ratio_ltv_cac']}:1)", "status": "good"},
    {"label": "Peor canal (LTV:CAC)", "value": f"{canal_peor['canal']} ({canal_peor['ratio_ltv_cac']}:1)", "status": "critical"},
    {"label": f"{canal_top['canal']}: clientes nuevos ({periodo})", "value": f"{top_change:+.0f}%",
     "status": "warning" if top_change < -5 else "good",
     "delta": "techo de capacidad" if top_change < -5 else "buen ritmo",
     "delta_direction": "down" if top_change < 0 else "up"},
]

# canal de riesgo que más mejora, para resaltar junto al mejor canal en la tendencia de CAC
canal_mejora_riesgo = riesgo_df.sort_values("cli_change_pct", ascending=False).iloc[0] if not riesgo_df.empty else canal_peor
canales_resaltados = {canal_top["canal"], canal_mejora_riesgo["canal"]}

charts = [
    {
        "id": "chart_matriz", "type": "scatter", "full_width": True,
        "title": "Matriz de segmentación: gasto vs. retorno por canal (tipo BCG)",
        "subtitle": f"Eje X: gasto total {periodo} (línea = mediana) · Eje Y: ratio LTV:CAC (línea = benchmark {UMBRAL_SANO:.0f}:1)",
        "points": [
            {"x": float(r["gasto_total"]), "y": float(r["ratio_ltv_cac"]), "label": r["canal"], "status": r["punto_status"]}
            for _, r in agg.iterrows()
        ],
        "x_label": "Gasto total (MXN)", "y_label": "Ratio LTV:CAC",
        "status_labels": {
            "good": "Escalar (bajo gasto, buen retorno)",
            "warning": "Mantener / vigilar (alto gasto, retorno sano)",
            "critical": "Recorte prioritario (alto gasto, bajo retorno)",
        },
        "point_radius": 8,
        "quadrant_lines": {"x": float(mediana_gasto), "y": UMBRAL_SANO},
        "quadrant_labels": [
            {"corner": "top-left", "text": "Escalar — alto retorno, bajo gasto"},
            {"corner": "top-right", "text": "Mantener — vigilar tendencia"},
            {"corner": "bottom-left", "text": "Optimizar antes de escalar"},
            {"corner": "bottom-right", "text": "Recorte prioritario"},
        ],
    },
    {
        "id": "chart_cac", "type": "bar", "horizontal": True,
        "title": "Costo de adquisición (CAC) por canal",
        "subtitle": f"MXN por cliente nuevo — total de {periodo}",
        "labels": list(agg["canal"]),
        "datasets": [{"label": "CAC", "data": list(agg["cac"])}],
        "y_label": "MXN", "value_format": "currency",
    },
    {
        "id": "chart_ratio", "type": "bar", "horizontal": True,
        "title": "Ratio LTV:CAC por canal",
        "subtitle": f"Benchmark saludable: {UMBRAL_SANO:.0f}:1",
        "labels": list(agg["canal"]),
        "datasets": [{"label": "LTV:CAC", "data": list(agg["ratio_ltv_cac"])}],
        "reference_line": {"value": UMBRAL_SANO, "label": f"Benchmark {UMBRAL_SANO:.0f}:1"},
    },
    {
        "id": "chart_tendencia_cac", "type": "line", "full_width": True,
        "title": f"Tendencia del CAC mensual ({periodo}) — ¿quién mejora y quién empeora?",
        "subtitle": f"{canal_top['canal']} (mejor ratio) vs. {canal_mejora_riesgo['canal']} (en riesgo, vigilar mejora) — resaltados, resto atenuado",
        "labels": meses,
        "datasets": [
            {
                "label": r["canal"],
                "data": r["cac_mensual_serie"],
                "color_index": CANALES_ORDEN.index(r["canal"]),
                "emphasis": r["canal"] in canales_resaltados,
                "muted": r["canal"] not in canales_resaltados,
            }
            for _, r in agg.sort_values("canal").iterrows()
        ],
        "y_label": "CAC mensual (MXN)",
    },
]

# ---- insights (responden cada pregunta de negocio, calculados de los datos) ----
insights = []

if not riesgo_df.empty:
    insights.append(
        f"<b>¿Dónde recortar ya?</b> {lista_canales(riesgo_df['canal'])} concentra"
        f"{'n' if len(riesgo_df) > 1 else ''} {pct_gasto_riesgo:.0f}% del gasto de {periodo} "
        f"(${riesgo_df['gasto_total'].sum():,.0f} MXN) y está{'n' if len(riesgo_df) > 1 else ''} por debajo "
        f"del benchmark {UMBRAL_SANO:.0f}:1."
    )

if not saludable_bajo.empty:
    nombres = ", ".join(f"{r.canal} ({r.ratio_ltv_cac}:1)" for r in saludable_bajo.itertuples())
    insights.append(
        f"<b>¿Qué canales merecen más presupuesto?</b> {nombres} tienen los mejores ratios, con solo "
        f"{pct_gasto_saludable_bajo:.0f}% del gasto combinado."
    )

if top_change < -5:
    insights.append(
        f"<b>¿{canal_top['canal']} puede escalar sin límite?</b> No — su CAC {canal_top['cac_change_pct']:+.1f}% y "
        f"sus clientes nuevos {top_change:+.1f}% en {periodo}: señal de techo de capacidad. Escalar con cautela, "
        f"priorizando el resto de los canales eficientes para el grueso del incremento de presupuesto."
    )
else:
    insights.append(
        f"<b>¿{canal_top['canal']} puede escalar más?</b> Sí — mejor ratio ({canal_top['ratio_ltv_cac']}:1) y sin "
        f"señales de deterioro en clientes nuevos ({top_change:+.1f}% en {periodo})."
    )

for r in riesgo_df.itertuples():
    if r.cli_change_pct > 20:
        insights.append(
            f"<b>¿Hay que abandonar {r.canal}?</b> No todavía — su CAC {r.cac_change_pct:+.1f}% y sus clientes "
            f"nuevos {r.cli_change_pct:+.1f}% en {periodo}: es un canal de riesgo que está mejorando. Vale la pena "
            f"seguir optimizando antes de recortar."
        )
    else:
        insights.append(
            f"<b>¿{r.canal} merece la misma paciencia?</b> No — CAC {r.cac_change_pct:+.1f}% y clientes nuevos "
            f"{r.cli_change_pct:+.1f}% en {periodo}: sin mejora clara y por debajo del benchmark. Candidato "
            f"principal a recorte de presupuesto."
        )

if not riesgo_df.empty:
    insights.append(
        f"<b>¿Cuánto dinero está en juego?</b> ${riesgo_df['gasto_total'].sum():,.0f} MXN de los últimos {periodo} "
        f"se fueron a canales que no cubren el retorno mínimo esperado."
    )

for r in saludable_alto.itertuples():
    tendencia = "enfriándose" if r.cli_change_pct < 0 else "sin señales de deterioro"
    insights.append(
        f"<b>¿{r.canal}, con gasto alto, es seguro?</b> Su ratio es sano ({r.ratio_ltv_cac}:1) pero está {tendencia} "
        f"(clientes nuevos {r.cli_change_pct:+.1f}% en {periodo}) — mantener el presupuesto, vigilar antes de "
        f"escalarlo más."
    )

insights.append(
    f"<b>¿El problema se está resolviendo solo?</b> No — el % del gasto en canales de riesgo se mantuvo entre "
    f"{riesgo_mensual.min():.1f}% y {riesgo_mensual.max():.1f}% durante los últimos {periodo}, sin tendencia clara "
    f"de mejora: requiere una decisión activa de reasignación, no esperar a que se corrija solo."
)

table = {
    "title": "Segmentación y recomendación por canal",
    "headers": ["Canal", "Segmento", "Gasto total", "Ratio LTV:CAC", f"Clientes nuevos ({n_meses}m)", "Recomendación"],
    "rows": [
        [r.canal, r.cuadrante, f"${r.gasto_total:,.0f}", f"{r.ratio_ltv_cac}:1",
         f"{r.cli_change_pct:+.1f}%", r.recomendacion]
        for r in agg.itertuples()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=9,
    title="ROI de Marketing: CAC vs. LTV por Canal",
    tagline="No todos los pesos de marketing valen lo mismo — saber qué canal escalar y cuál replantear.",
    banner=banner,
    hero_kpi=hero_kpi,
    hero_chart=hero_chart,
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="top",
)

print(agg[["canal", "cac", "ltv", "ratio_ltv_cac", "cuadrante", "cac_change_pct", "cli_change_pct"]].to_string(index=False))
print(f"\n% gasto en canales de riesgo por mes:\n{riesgo_mensual.to_string()}")
print("\nOK -> dashboard.html")
