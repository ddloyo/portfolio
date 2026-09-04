"""
Estima elasticidad-precio por producto (regresión log-log) y cruza esa
elasticidad con la confianza estadística de la estimación (R²) en una
matriz de 4 cuadrantes de acción -- en vez de solo ordenar productos por
elasticidad, dice qué hacer con cada uno y qué tan seguro se puede estar
de esa recomendación antes de tocar la lista de precios. Genera dashboard.html.

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script), con la tabla del plan de repricing cortada a 5 filas —
se usa como vista previa del dashboard completo en el README. Para
regenerarla tras un cambio visual: abre dashboard.html en el navegador y
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

df = pd.read_csv(ROOT / "data" / "precio_demanda.csv")

# ---- elasticidad + confianza de la estimación por producto -----------------
rows = []
for producto, g in df.groupby("producto"):
    x = np.log(g["precio_mxn"])
    y = np.log(g["unidades_vendidas"])
    # regresión lineal simple: y = a + b*x  ->  b es la elasticidad-precio
    b, a = np.polyfit(x, y, 1)
    yhat = a + b * x
    r2 = 1 - np.sum((y - yhat) ** 2) / np.sum((y - y.mean()) ** 2)

    precio_actual = g["precio_mxn"].iloc[-1]
    unidades_actual = g["unidades_vendidas"].iloc[-1]
    ingreso_actual_semana = precio_actual * unidades_actual
    ingreso_anual = (g["precio_mxn"] * g["unidades_vendidas"]).sum()

    # proyección de un +10% de precio usando la elasticidad estimada,
    # anualizada (52 semanas) para que el impacto se lea en la misma
    # magnitud que el ingreso anual del producto
    cambio_unidades_pct = b * 0.10
    ingreso_proy_semana = precio_actual * 1.10 * unidades_actual * (1 + cambio_unidades_pct)
    impacto_anual = (ingreso_proy_semana - ingreso_actual_semana) * 52

    rows.append({
        "producto": producto,
        "elasticidad": round(b, 2),
        "r2": round(r2, 3),
        "precio_actual": round(precio_actual, 0),
        "ingreso_anual": round(ingreso_anual, 0),
        "impacto_anual": round(impacto_anual, 0),
    })

res = pd.DataFrame(rows)

# ---- matriz elasticidad x confianza: 4 cuadrantes de acción -----------------
# Eje X: elasticidad estimada (más negativo = más elástico). Eje Y: R² de la
# regresión (qué tan bien explica el precio la variación en unidades vendidas
# frente al ruido semanal). La dirección de la recomendación (subir o no) la
# da la elasticidad; la confianza para actuar sobre ella la da el R² -- dos
# productos con la misma elasticidad estimada pueden merecer una acción
# distinta si uno tiene mucha más señal que ruido que el otro. Split por
# mediana en ambos ejes para que los 4 cuadrantes queden balanceados.
mediana_elasticidad = res["elasticidad"].median()
mediana_r2 = res["r2"].median()

QUADRANTS = {
    (True, True): ("good", "Subir precio — ejecutar ya"),
    (True, False): ("neutral", "Subir precio — probar antes de escalar"),
    (False, True): ("critical", "No subir precio — evidencia sólida"),
    (False, False): ("warning", "Recolectar más datos"),
}


def quadrant_of(row):
    key = (row["elasticidad"] >= mediana_elasticidad, row["r2"] >= mediana_r2)
    return QUADRANTS[key]


res[["cuadrante_status", "cuadrante"]] = res.apply(quadrant_of, axis=1, result_type="expand")
res["confianza"] = res["r2"].apply(lambda v: f"{'Alta' if v >= mediana_r2 else 'Baja'} (R²={v:.2f})")

ACCIONES = {
    "Subir precio — ejecutar ya": "Aplicar el incremento en la próxima actualización de lista — demanda inelástica y el modelo explica bien la variación de unidades: bajo riesgo de sorpresa.",
    "Subir precio — probar antes de escalar": "La dirección apunta a subir precio, pero el R² es bajo — validar con una prueba piloto (una región o segmento de clientes) antes de aplicarlo a todo el catálogo.",
    "No subir precio — evidencia sólida": "No subir precio — la demanda es elástica y el modelo lo explica con alta confianza; un alza aquí golpea el ingreso de forma predecible.",
    "Recolectar más datos": "Ni la dirección ni la magnitud son confiables todavía (R² bajo) — no tomar una decisión de precio con este dato; ampliar el histórico o correr una prueba controlada primero.",
}
res["accion_recomendada"] = res["cuadrante"].map(ACCIONES)

quadrant_order = list(ACCIONES.keys())

seg_summary = res.groupby("cuadrante").agg(
    productos=("producto", "count"),
    elasticidad_prom=("elasticidad", "mean"),
    r2_prom=("r2", "mean"),
    impacto_anual=("impacto_anual", "sum"),
).reindex(quadrant_order).fillna(0)

res = res.sort_values("elasticidad")
total_productos = len(res)


def fmt_money(v):
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}"

ejecutar = res[res["cuadrante"] == "Subir precio — ejecutar ya"]
probar = res[res["cuadrante"] == "Subir precio — probar antes de escalar"]
proteger = res[res["cuadrante"] == "No subir precio — evidencia sólida"]
recolectar = res[res["cuadrante"] == "Recolectar más datos"]

impacto_ejecutar = ejecutar["impacto_anual"].sum()
impacto_probar = probar["impacto_anual"].sum()
impacto_subir_total = impacto_ejecutar + impacto_probar
impacto_protegido = -proteger["impacto_anual"].sum()

# ---- interactive dashboard ------------------------------------------------
banner = {
    "label": "Próxima actualización de lista de precios",
    "headline": (
        f"{len(ejecutar)} de {total_productos} productos listo para subir precio ya "
        f"(+${impacto_ejecutar:,.0f} MXN/año) — {len(probar)} más apuntan en la misma dirección "
        f"pero necesitan una prueba piloto primero."
    ),
    "subtext": (
        f"La evidencia es sólida en {len(proteger)} productos para NO subir precio: hacerlo "
        f"destruiría ${impacto_protegido:,.0f} MXN/año de ingreso. "
        f"{len(recolectar)} producto no tiene suficiente señal (R² bajo) para decidir en ningún sentido todavía."
    ),
}

kpis = [
    {"label": "Productos analizados", "value": str(total_productos)},
    {"label": "Impacto anual si se ejecutan las subidas recomendadas", "value": f"${impacto_subir_total:,.0f} MXN", "hero": True},
    {"label": "Ejecutar ya (alta confianza)", "value": f"{len(ejecutar)} producto" + ("s" if len(ejecutar) != 1 else ""), "status": "good"},
    {"label": "Requieren piloto antes de escalar", "value": f"{len(probar) + len(recolectar)} productos", "status": "warning"},
    {"label": "Ingreso protegido al no subir precio", "value": f"${impacto_protegido:,.0f} MXN", "status": "critical"},
]

scatter_points = [
    {
        "x": r.elasticidad, "y": r.r2,
        "label": f"{r.producto} · elasticidad {r.elasticidad} · R²={r.r2:.2f}",
        "status": r.cuadrante_status,
    }
    for r in res.itertuples()
]

charts = [
    {
        "id": "chart_matriz", "type": "scatter", "full_width": True,
        "title": "Matriz elasticidad x confianza: qué acción de precio corresponde a cada producto",
        "subtitle": f"{total_productos} productos — elasticidad estimada vs. R² del modelo, divididos en la mediana de cada eje",
        "points": scatter_points,
        "x_label": "Elasticidad-precio (más negativo = más sensible al precio)", "y_label": "Confianza del modelo (R²)",
        "x_unit": "", "y_unit": " R²",
        "point_radius": 7, "point_alpha": 0.85,
        "status_labels": {
            "good": "Subir — ejecutar ya", "neutral": "Subir — probar antes",
            "critical": "No subir — evidencia sólida", "warning": "Recolectar más datos",
        },
        "quadrant_lines": {"x": round(mediana_elasticidad, 2), "y": round(mediana_r2, 3)},
        "quadrant_labels": [
            {"corner": "top-left", "text": "NO SUBIR — EVIDENCIA SÓLIDA"},
            {"corner": "top-right", "text": "EJECUTAR YA"},
            {"corner": "bottom-left", "text": "RECOLECTAR MÁS DATOS"},
            {"corner": "bottom-right", "text": "PROBAR ANTES DE ESCALAR"},
        ],
    },
    {
        "id": "chart_impacto", "type": "bar", "horizontal": True, "full_width": True,
        "title": "Impacto anual proyectado por producto (+10% de precio)",
        "subtitle": "MXN/año — positivo donde subir precio conviene, negativo donde destruye ingreso",
        "labels": list(res["producto"]),
        "datasets": [{
            "label": "Impacto anual",
            "data": [int(v) for v in res["impacto_anual"]],
            "colors": [STATUS[s] for s in res["cuadrante_status"]],
        }],
        "y_label": "MXN/año",
        "value_format": "currency",
    },
]

insights = [
    f"<b>{ejecutar.iloc[0]['producto']}</b> es el único producto con evidencia suficiente (R²={ejecutar.iloc[0]['r2']:.2f}, elasticidad {ejecutar.iloc[0]['elasticidad']}) para subir precio en la próxima lista sin necesidad de prueba piloto — impacto estimado +${impacto_ejecutar:,.0f} MXN/año.",
    f"<b>{len(probar)} productos</b> ({', '.join(p.split(' (')[0] for p in probar['producto'])}) apuntan a subir precio (+${impacto_probar:,.0f} MXN/año combinado) pero con R² por debajo de {mediana_r2:.2f} — antes de aplicarlo a todo el catálogo conviene una prueba piloto en una región o segmento de clientes.",
    f"<b>{len(proteger)} productos</b> ({', '.join(p.split(' (')[0] for p in proteger['producto'])}) tienen evidencia sólida (R² {proteger['r2'].min():.2f}–{proteger['r2'].max():.2f}) de ser altamente elásticos — subir su precio destruiría ${impacto_protegido:,.0f} MXN/año; no deben tocarse en esta ronda.",
    "La confianza estadística (R²) importa tanto como la dirección de la elasticidad: dos productos con la misma elasticidad estimada pueden merecer una acción distinta si uno tiene mucha más señal que ruido que el otro — por eso la matriz cruza ambos ejes en vez de ordenar solo por elasticidad.",
]

table = {
    "title": "Resumen por cuadrante de acción",
    "headers": ["Cuadrante", "Productos", "Elasticidad promedio", "R² promedio", "Impacto anual", "Acción recomendada"],
    "rows": [
        [q, int(row["productos"]), round(row["elasticidad_prom"], 2), round(row["r2_prom"], 2), fmt_money(row["impacto_anual"]), ACCIONES[q]]
        for q, row in seg_summary.iterrows()
    ],
}

checklist = {
    "id": "plan_repricing",
    "title": "Plan de repricing — próxima actualización de lista",
    "subtitle": "Los 8 productos ordenados por prioridad de acción. Marca cada uno al aplicarlo (o al confirmar que se deja igual) en el ERP — el progreso se guarda en este navegador.",
    "progress_noun": "revisados",
    "headers": ["Producto", "Elasticidad", "Confianza", "Impacto anual estimado", "Acción"],
    "rows": [
        {
            "id": r.producto,
            "cells": [r.producto, r.elasticidad, r.confianza, fmt_money(r.impacto_anual), r.accion_recomendada],
        }
        for r in res.sort_values("cuadrante", key=lambda s: s.map({q: i for i, q in enumerate(quadrant_order)})).itertuples()
    ],
}

dash.render(
    ROOT / "dashboard.html",
    project_no=6,
    title="Elasticidad de Precios y Price Intelligence",
    tagline="No todos los productos reaccionan igual a un cambio de precio — la matriz dice a cuáles subirles precio ya, a cuáles con prueba piloto primero, y a cuáles no tocar.",
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="top",
    banner=banner,
    checklist=checklist,
    chart_cols=1,
)

print(res[["producto", "elasticidad", "r2", "cuadrante", "impacto_anual"]].to_string(index=False))
print(f"Ejecutar ya: {len(ejecutar)} | Probar antes: {len(probar)} | No subir: {len(proteger)} | Recolectar datos: {len(recolectar)}")
print("OK -> dashboard.html")
