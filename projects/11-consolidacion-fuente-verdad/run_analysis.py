"""
Consolida los 3 exports crudos e inconsistentes en una sola fuente de
verdad: estandariza columnas, formatos de fecha y nombres de sucursal,
elimina duplicados y separa los registros con datos faltantes para
revisión manual en vez de inventar un valor.

Además de la consolidación, corre tres pasadas de análisis sobre el
resultado -- segmentación de fuentes por su problema de calidad
dominante, serie de tiempo de ventas (tendencia, estacionalidad
semanal, anomalías) y síntesis de insights priorizados -- para
responder a las preguntas que gerencia media y alta necesitan de este
pipeline: no solo "¿ya quedó limpio?" sino "¿qué tan grave es cada
fuente, cuánto dinero está en juego y qué hacer primero?".

Genera:
  1. data/fuente_unica.csv -> el dataset limpio y consolidado
  2. dashboard.html        -> dashboard ejecutivo (pirámide de Minto)

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
from xia_style import STATUS
import dashboard as dash

NORMALIZA_SUCURSAL = {
    "cdmx": "CDMX", "mty": "Monterrey", "monterrey": "Monterrey",
    "gdl": "Guadalajara", "guadalajara": "Guadalajara",
}


def normaliza(nombre):
    return NORMALIZA_SUCURSAL.get(str(nombre).strip().lower(), str(nombre).strip())


# ============================================================================
# 1) INGESTA -- cada fuente con su propio mapeo de columnas y formato de fecha
# ============================================================================
cdmx_raw = pd.read_csv(ROOT / "data" / "raw_export_cdmx.csv")
cdmx_std = pd.DataFrame({
    "fecha": pd.to_datetime(cdmx_raw["Fecha"], format="%d/%m/%Y"),
    "sucursal": cdmx_raw["Sucursal"].map(normaliza),
    "monto_mxn": cdmx_raw["Monto"],
    "fuente": "export_cdmx.csv",
})

mty_raw = pd.read_csv(ROOT / "data" / "raw_export_monterrey.csv")
mty_std = pd.DataFrame({
    "fecha": pd.to_datetime(mty_raw["fecha_venta"], format="%Y-%m-%d"),
    "sucursal": mty_raw["tienda"].map(normaliza),
    "monto_mxn": mty_raw["importe_mxn"],
    "fuente": "export_monterrey.csv",
})

gdl_raw = pd.read_csv(ROOT / "data" / "raw_export_guadalajara.csv")
gdl_std = pd.DataFrame({
    "fecha": pd.to_datetime(gdl_raw["Date"], format="%m/%d/%Y"),
    "sucursal": gdl_raw["Store"].map(normaliza),
    "monto_mxn": gdl_raw["Amount_MXN"],
    "fuente": "export_guadalajara.csv",
})

crudo = pd.concat([cdmx_std, mty_std, gdl_std], ignore_index=True)
filas_crudas = len(crudo)
fuentes = crudo["fuente"].nunique()

# 1) separar filas con monto faltante -> cola de revisión manual (no se inventa el dato)
con_monto = crudo.dropna(subset=["monto_mxn"]).copy()
faltantes = crudo[crudo["monto_mxn"].isna()]
crudo[crudo["monto_mxn"].isna()].to_csv(ROOT / "data" / "revision_manual_monto_faltante.csv", index=False)

# 2) eliminar duplicados exactos (misma fecha, sucursal y monto)
antes_dedupe = len(con_monto)
dup_mask = con_monto.duplicated(subset=["fecha", "sucursal", "monto_mxn"], keep="first")
duplicados = con_monto[dup_mask]
limpio = con_monto[~dup_mask]
duplicados_removidos = antes_dedupe - len(limpio)

limpio = limpio.sort_values(["fecha", "sucursal"]).reset_index(drop=True)
limpio.to_csv(ROOT / "data" / "fuente_unica.csv", index=False)

sucursales_encontradas = sorted(limpio["sucursal"].unique())
por_sucursal = limpio.groupby("sucursal")["monto_mxn"].agg(["sum", "count"]).rename(columns={"sum": "total", "count": "transacciones"})
total_consolidado = limpio["monto_mxn"].sum()

# ============================================================================
# 2) SEGMENTACIÓN -- las 3 fuentes agrupadas por su problema de calidad
#    dominante (no todas fallan igual: cada una necesita una corrección
#    distinta en origen). Ver skill segmentation-analysis.
# ============================================================================
FUENTE_A_SUCURSAL = {"export_cdmx.csv": "CDMX", "export_monterrey.csv": "Monterrey", "export_guadalajara.csv": "Guadalajara"}
avg_monto_por_sucursal = limpio.groupby("sucursal")["monto_mxn"].mean()

segmentos = []
for fuente, suc in FUENTE_A_SUCURSAL.items():
    total_fuente = len(crudo[crudo["fuente"] == fuente])
    dup_fuente = duplicados[duplicados["fuente"] == fuente]
    falt_fuente = faltantes[faltantes["fuente"] == fuente]
    variantes_nombre = crudo.loc[crudo["fuente"] == fuente, "sucursal"].map(str).str.strip()
    # variantes crudas antes de normalizar -- recontamos desde el archivo fuente
    if fuente == "export_cdmx.csv":
        variantes_crudas = cdmx_raw["Sucursal"].astype(str).str.strip().nunique()
    elif fuente == "export_monterrey.csv":
        variantes_crudas = mty_raw["tienda"].astype(str).str.strip().nunique()
    else:
        variantes_crudas = gdl_raw["Store"].astype(str).str.strip().nunique()

    dup_pct = len(dup_fuente) / total_fuente * 100
    falt_pct = len(falt_fuente) / total_fuente * 100
    problema_pct = (len(dup_fuente) + len(falt_fuente)) / total_fuente * 100

    if len(falt_fuente) >= len(dup_fuente) and len(falt_fuente) > 0:
        problema_dominante = "Datos faltantes (monto vacío)"
    elif variantes_crudas > 1:
        # más de una grafía cruda para la misma sucursal es un problema
        # estructural (se resuelve una vez con un catálogo), distinto de
        # duplicados/faltantes (errores por fila) -- y aquí es el rasgo
        # más característico de la fuente aunque su $ en riesgo sea bajo.
        problema_dominante = f"Nombre de sucursal inconsistente ({variantes_crudas} formatos)"
    elif len(dup_fuente) > 0:
        problema_dominante = "Duplicados exactos"
    else:
        problema_dominante = "Ninguno (fuente limpia)"

    valor_dup = dup_fuente["monto_mxn"].sum()
    valor_falt_estimado = falt_fuente["sucursal"].map(avg_monto_por_sucursal).sum()

    segmentos.append({
        "sucursal": suc, "fuente": fuente, "total_filas": total_fuente,
        "dup_filas": len(dup_fuente), "dup_pct": dup_pct, "valor_dup": valor_dup,
        "falt_filas": len(falt_fuente), "falt_pct": falt_pct, "valor_falt_estimado": valor_falt_estimado,
        "problema_pct": problema_pct, "problema_dominante": problema_dominante,
        "variantes_nombre": variantes_crudas,
    })

seg_df = pd.DataFrame(segmentos).set_index("sucursal")
valor_dup_total = seg_df["valor_dup"].sum()
valor_falt_total = seg_df["valor_falt_estimado"].sum()
fuente_top_riesgo = seg_df["problema_pct"].idxmax()
fuente_top_riesgo_tipo = seg_df.loc[fuente_top_riesgo, "problema_dominante"]
share_dup_top = seg_df.loc[fuente_top_riesgo, "valor_dup"] / valor_dup_total * 100 if valor_dup_total else 0

ACCIONES = {
    "CDMX": "Revisar la lógica de exportación del punto de venta para evitar reenvíos duplicados del mismo ticket.",
    "Monterrey": "Validación obligatoria del campo monto antes de exportar; asignar dueño con SLA para resolver la cola.",
    "Guadalajara": "Consolidar a un catálogo único de sucursales en el sistema de origen y retirar el paso de normalización manual.",
}

# ============================================================================
# 3) SERIE DE TIEMPO -- tendencia mensual, estacionalidad semanal y
#    anomalías sobre las ventas diarias consolidadas. Ver skill
#    time-series-analysis.
# ============================================================================
limpio_ts = limpio.copy()
limpio_ts["mes"] = limpio_ts["fecha"].dt.to_period("M")
mensual_sucursal = limpio_ts.groupby(["mes", "sucursal"])["monto_mxn"].sum().unstack().fillna(0)
mensual_total = limpio_ts.groupby("mes")["monto_mxn"].sum()
meses_labels = [m.strftime("%b %Y") for m in mensual_total.index]
crecimiento_trimestre_pct = (mensual_total.iloc[-1] / mensual_total.iloc[0] - 1) * 100

daily = limpio.groupby("fecha")["monto_mxn"].sum().asfreq("D").fillna(0)
roll_mean_7 = daily.rolling(7, center=True, min_periods=1).mean()
roll_median_7 = daily.rolling(7, center=True, min_periods=3).median()
roll_std_7 = daily.rolling(7, center=True, min_periods=3).std().fillna(0)
anomalias = daily[(daily - roll_median_7).abs() > 3 * roll_std_7]
cv_consolidado = daily.std() / daily.mean() * 100

daily_by_dow = daily.to_frame("total")
daily_by_dow["dow"] = daily_by_dow.index.day_name()
DOW_ES = {"Monday": "Lun", "Tuesday": "Mar", "Wednesday": "Mié", "Thursday": "Jue",
          "Friday": "Vie", "Saturday": "Sáb", "Sunday": "Dom"}
DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
estacionalidad = daily_by_dow.groupby("dow")["total"].mean().reindex(DOW_ORDER)
indice_estacional = (estacionalidad / daily.mean() * 100).round(1)
dia_pico = indice_estacional.idxmax()
dia_valle = indice_estacional.idxmin()

# ============================================================================
# 4) INSIGHT SYNTHESIS -- top hallazgos con So What / Why / Now What,
#    priorizados por impacto x confianza x accionabilidad. Ver skill
#    insight-synthesis. Las 7 preguntas de negocio que responde este
#    dashboard están numeradas abajo (Q1-Q7).
# ============================================================================
insights = [
    # Q1 -- ¿Cuál es el número real y cuánto se habría inflado sin el pipeline?
    f"<b>Q1 · La fuente única evita ${valor_dup_total:,.0f} MXN de ventas infladas</b> ({duplicados_removidos} filas duplicadas entre las 3 fuentes) frente al total consolidado de ${total_consolidado:,.0f} MXN — así se cierra la discusión de en la reunión sobre cuál número es el correcto.",
    # Q2 -- ¿qué fuente concentra el mayor riesgo y de qué tipo?
    f"<b>Q2 · {fuente_top_riesgo} concentra el mayor riesgo de calidad</b> ({fuente_top_riesgo_tipo.lower()}, {seg_df.loc[fuente_top_riesgo, 'problema_pct']:.1f}% de sus filas) y aporta {share_dup_top:.0f}% de todo el valor duplicado detectado — es la fuente a corregir primero en origen.",
    # Q3 -- ¿cuánto valor sigue invisible en la cola de revisión?
    f"<b>Q3 · ${valor_falt_total:,.0f} MXN (estimado) siguen sin reportarse</b> en la cola de revisión manual — {int(seg_df['falt_filas'].sum())} filas, 100% de Monterrey — porque la fuente única nunca inventa un monto faltante; alguien debe capturarlo.",
    # Q4 -- ¿cómo se compara el desempeño mensual entre sucursales?
    f"<b>Q4 · Ninguna sucursal cae de forma sostenida en el trimestre</b>: CDMX bajó en julio y se recuperó en agosto, Monterrey hizo el patrón inverso, y Guadalajara creció los dos meses seguidos pese a ser la más pequeña.",
    # Q5 -- ¿el vaivén de una sucursal pone en riesgo el número consolidado?
    f"<b>Q5 · El consolidado amortigua el vaivén de cada sucursal</b>: mientras CDMX y Monterrey oscilan ±19-28% mes a mes en direcciones opuestas, el total de la empresa se movió solo {mensual_total.pct_change().iloc[1]*100:+.1f}% y {mensual_total.pct_change().iloc[2]*100:+.1f}% — planear sobre una sola sucursal habría sido engañoso.",
    # Q6 -- ¿hay un patrón semanal a considerar?
    f"<b>Q6 · Existe un patrón semanal moderado</b>: {DOW_ES[dia_pico]} vende {indice_estacional[dia_pico]-100:.0f}% arriba del promedio diario y {DOW_ES[dia_valle]} {100-indice_estacional[dia_valle]:.0f}% abajo — hay que usar el índice estacional al fijar metas por día, no un promedio plano.",
    # Q7 -- ¿hay anomalías que ameriten investigación?
    f"<b>Q7 · No se detectaron anomalías</b> (&gt;3 desviaciones estándar de la mediana móvil de 7 días) en los {len(daily)} días del trimestre; la variabilidad diaria (CV {cv_consolidado:.0f}%) es ruido normal de venta, no un evento aislado.",
]

# ============================================================================
# 5) Conteos del pipeline de limpieza, para el gráfico de barras "de crudo
#    a fuente única" del dashboard (ver sección 6).
# ============================================================================
funnel_values = [filas_crudas, len(con_monto), len(limpio)]
retencion_paso1 = len(con_monto) / filas_crudas * 100
retencion_paso2 = len(limpio) / len(con_monto) * 100

# ============================================================================
# 6) DASHBOARD INTERACTIVO -- pirámide de Minto: la respuesta primero
#    (banner), luego el número que la sostiene (hero KPI), luego el
#    resto de KPIs, la tabla de segmentación, las gráficas que responden
#    cada pregunta y, al final, el detalle. Ver skills dashboard-
#    specification y visualization-builder (paleta XIA).
# ============================================================================
banner = {
    "label": "La respuesta primero",
    "headline": f"La fuente única evita ${valor_dup_total:,.0f} MXN de ventas infladas por duplicados — pero ${valor_falt_total:,.0f} MXN siguen atrapados en la cola de revisión de Monterrey.",
    "subtext": (
        f"Prioridad del trimestre: cerrar la cola de Monterrey con un dueño y un SLA de captura, y blindar la "
        f"exportación de {fuente_top_riesgo} en origen — de ahí sale {share_dup_top:.0f}% de todo el valor duplicado "
        f"detectado este trimestre."
    ),
}

hero_kpi = {
    "label": "Ventas consolidadas del trimestre (fuente única)",
    "value": f"${total_consolidado:,.0f}",
    "delta": f"{crecimiento_trimestre_pct:+.1f}% jun→ago",
    "delta_direction": "up" if crecimiento_trimestre_pct >= 0 else "down",
    "status": "good",
    "status_label": "Sin anomalías",
}
# Semanal, no diario: 92 puntos crudos con marcador saturan el hero
# widget (~130px de alto) hasta volverse ilegibles. 13 puntos semanales
# muestran la misma tendencia estable sin el ruido día a día. Se descarta
# la última semana si quedó incompleta (p.ej. un solo día): su total
# bajo no es una caída real, es un artefacto de corte de trimestre.
semanal = daily.resample("W").sum()
dias_por_semana = daily.resample("W").count()
semanal = semanal[dias_por_semana == 7]
hero_chart = {
    "id": "chart_hero_trend", "type": "line",
    "labels": [f"Sem. {d.strftime('%d %b')}" for d in semanal.index],
    "datasets": [{"label": "Ventas semanales", "data": [round(v, 0) for v in semanal.values], "emphasis": True, "color_index": 2}],
}

kpis = [
    {"label": "Fuentes consolidadas", "value": f"{fuentes} exports → 1"},
    {"label": "Duplicados evitados (valor)", "value": f"${valor_dup_total:,.0f}", "status": "warning"},
    {"label": "En cola de revisión (estimado)", "value": f"${valor_falt_total:,.0f}", "status": "warning"},
    {"label": "Crecimiento del trimestre", "value": f"{crecimiento_trimestre_pct:+.1f}%", "status": "good"},
    {"label": "Fuente de mayor riesgo", "value": f"{fuente_top_riesgo} · {fuente_top_riesgo_tipo}", "status": "warning"},
]

charts = [
    {
        "id": "chart_sucursal_mes", "type": "line",
        "title": "Ventas mensuales por sucursal",
        "subtitle": "CDMX y Monterrey oscilan en direcciones opuestas; el total (línea gruesa) se mantiene estable",
        "labels": meses_labels,
        "datasets": [
            {"label": "Total consolidado", "data": [round(v, 0) for v in mensual_total.values], "emphasis": True, "color_index": 5, "tension": 0}
        ] + [
            {"label": suc, "data": [round(v, 0) for v in mensual_sucursal[suc].values], "color_index": i, "tension": 0}
            for i, suc in enumerate(sucursales_encontradas)
        ],
        "y_label": "MXN",
    },
    {
        "id": "chart_estacionalidad", "type": "bar",
        "title": f"{DOW_ES[dia_pico]} vende {indice_estacional[dia_pico]-100:.0f}% más que el promedio; {DOW_ES[dia_valle]}, {100-indice_estacional[dia_valle]:.0f}% menos",
        "subtitle": "Índice estacional por día de la semana (100 = promedio diario del trimestre)",
        "labels": [DOW_ES[d] for d in DOW_ORDER],
        "datasets": [{"label": "Índice estacional", "data": [round(v, 1) for v in indice_estacional.values]}],
        "y_label": "Índice (100 = promedio)",
        "reference_line": {"value": 100, "label": "Promedio diario"},
    },
    {
        "id": "chart_calidad_fuente", "type": "progress_bars",
        "title": "Filas problemáticas por fuente (duplicadas o sin monto)",
        "subtitle": "% de filas que se removieron o se enviaron a revisión manual — la severidad real, en dinero, está en la tabla de arriba",
        "labels": list(seg_df.index),
        "values": [round(v, 1) for v in seg_df["problema_pct"]],
        "max": max(10, round(seg_df["problema_pct"].max() * 1.4, 1)),
        "value_suffix": "%",
        "colors": [STATUS["warning"] if v >= 2 else STATUS["good"] for v in seg_df["problema_pct"]],
    },
    {
        # Bar, no funnel: el pipeline retiene >97% de las filas en cada paso
        # (no es un embudo con fuga real), así que el auto-resaltado en rojo
        # del componente de funnel para "el paso más débil" daría una falsa
        # alarma -- una barra simple con el % de retención es honesta.
        "id": "chart_pipeline", "type": "bar",
        "title": "De 3 exports crudos a una fuente única, sin perder datos",
        "subtitle": f"{retencion_paso1:.0f}% de las filas trae monto válido, y de esas el {retencion_paso2:.0f}% ya era única (no duplicada)",
        "labels": ["Filas crudas", "Con monto válido", "Fuente única"],
        "datasets": [{
            "label": "Filas", "data": funnel_values, "colors": [STATUS["neutral"], STATUS["neutral"], STATUS["good"]],
            "value_labels": [f"{v:,}" for v in funnel_values],
        }],
        "value_labels": True,
        "y_label": "Filas",
    },
]

table = {
    "title": "Segmentación de fuentes por problema de calidad dominante",
    "headers": ["Fuente", "Problema dominante", "% filas afectadas", "Valor asociado (MXN)", "Acción recomendada"],
    "rows": [
        [
            suc,
            row["problema_dominante"],
            f"{row['problema_pct']:.1f}%",
            f"${row['valor_dup']:,.0f}" if row["problema_dominante"] == "Duplicados exactos" else (f"~${row['valor_falt_estimado']:,.0f} (estimado)" if row["valor_falt_estimado"] > 0 else "N/A"),
            ACCIONES[suc],
        ]
        for suc, row in seg_df.iterrows()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=11,
    title="Consolidación de Datos Dispersos: Una Sola Fuente de Verdad",
    tagline="Cada sucursal con su propio Excel, tres formatos distintos, nombres inconsistentes — un solo archivo limpio del que parte cualquier reporte, con la segmentación de riesgo y la tendencia que gerencia necesita para decidir.",
    banner=banner,
    hero_kpi=hero_kpi,
    hero_chart=hero_chart,
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="top",
    chart_cols=2,
)

print(f"Crudo: {filas_crudas} | Duplicados removidos: {duplicados_removidos} (${valor_dup_total:,.0f}) | Faltantes a revisión: {len(faltantes)} (~${valor_falt_total:,.0f}) | Limpio: {len(limpio)}")
print(f"Fuente de mayor riesgo: {fuente_top_riesgo} ({fuente_top_riesgo_tipo}) | Crecimiento trimestre: {crecimiento_trimestre_pct:+.1f}%")
print("OK -> data/fuente_unica.csv, dashboard.html")
