"""
Calcula antigüedad de cartera vencida (AR aging), segmenta clientes por
comportamiento de pago (Puntual/Lento/Moroso, derivado de los datos —no de
una etiqueta hardcodeada), cruza esa segmentación con el DSO y la
concentración de riesgo, y proyecta el flujo de cobranza de las próximas 4
semanas por segmento. Genera dashboard.html — banner con la respuesta
primero (pirámide de Minto), matriz de riesgo (tamaño de cliente x días
promedio de pago) y checklist de cobranza priorizada por segmento.

assets/dashboard_preview.png es una captura manual de dashboard.html (no la
genera este script) -- se usa como vista previa en el README. Para
regenerarla tras un cambio visual: abre dashboard.html en el navegador y
toma un screenshot de la página completa (recortando el checklist de
cobranza a unas pocas filas para que la imagen no quede kilométrica).
"""

import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "_lib"))

import numpy as np
import pandas as pd
from xia_style import STATUS
import dashboard as dash

TODAY = pd.Timestamp(date(2026, 8, 31))
df = pd.read_csv(ROOT / "data" / "facturas.csv", parse_dates=["fecha_emision", "fecha_vencimiento", "fecha_pago"])

# ---- segmentación de clientes por comportamiento de pago -------------------
# Rule-based en vez de k-means: con 8 clientes no hay masa crítica para
# clustering (la guía de segmentación pide ~100+ por segmento esperado), así
# que se usa la variable que de verdad separa a los clientes -- días
# promedio para pagar una factura, calculados de su propio historial de
# pagos, no una etiqueta importada del generador de datos. Los cortes (20 y
# 70 días) caen en el hueco natural entre los tres grupos que aparecen en el
# dato: ~10 días, ~35-65 días, ~75-160 días.
pagadas = df[df["estatus"] == "Pagada"].copy()
pagadas["dias_pago"] = (pagadas["fecha_pago"] - pagadas["fecha_emision"]).dt.days
dias_pago_cliente = pagadas.groupby("cliente")["dias_pago"].mean()


def segmento_de(dias):
    if dias < 20:
        return "Puntual"
    if dias < 70:
        return "Lento"
    return "Moroso"


segmento_cliente = dias_pago_cliente.apply(segmento_de)
df["segmento"] = df["cliente"].map(segmento_cliente)
SEGMENT_ORDER = ["Puntual", "Lento", "Moroso"]
SEGMENT_STATUS = {"Puntual": "good", "Lento": "warning", "Moroso": "critical"}

pendientes = df[df["estatus"] == "Pendiente"].copy()
pendientes["dias_vencida"] = (TODAY - pendientes["fecha_vencimiento"]).dt.days


def bucket(d):
    if d <= 0:
        return "Vigente (no vencida)"
    if d <= 30:
        return "1-30 días"
    if d <= 60:
        return "31-60 días"
    if d <= 90:
        return "61-90 días"
    return "90+ días"


pendientes["bucket"] = pendientes["dias_vencida"].apply(bucket)
bucket_order = ["Vigente (no vencida)", "1-30 días", "31-60 días", "61-90 días", "90+ días"]
aging = pendientes.groupby("bucket")["monto_mxn"].sum().reindex(bucket_order).fillna(0)

cartera_total = pendientes["monto_mxn"].sum()
cartera_vencida = pendientes[pendientes["dias_vencida"] > 0]["monto_mxn"].sum()
pct_vencida = round(cartera_vencida / cartera_total * 100, 1) if cartera_total else 0

# DSO simplificado: (cartera pendiente / ventas facturadas en los últimos 90 días) * 90
ventas_90d = df[df["fecha_emision"] >= (TODAY - pd.Timedelta(days=90))]["monto_mxn"].sum()
dso = round(cartera_total / ventas_90d * 90, 1) if ventas_90d else None

# ---- DSO y cartera pendiente por segmento -----------------------------------
# El DSO consolidado es un promedio ponderado que esconde a los clientes que
# de verdad tardan en pagar. Se recalcula el mismo cálculo (cartera pendiente
# / ventas 90d * 90) pero cortado por segmento, para que quede explícito
# cuánto de la mora "normal" es en realidad concentración de riesgo.
pendiente_por_segmento = pendientes.groupby("segmento")["monto_mxn"].sum().reindex(SEGMENT_ORDER).fillna(0)
ventas_90d_segmento = df[df["fecha_emision"] >= (TODAY - pd.Timedelta(days=90))].groupby("segmento")["monto_mxn"].sum().reindex(SEGMENT_ORDER).fillna(0)
dso_por_segmento = (pendiente_por_segmento / ventas_90d_segmento * 90).round(1)
clientes_por_segmento = segmento_cliente.value_counts().reindex(SEGMENT_ORDER).fillna(0).astype(int)
dias_pago_por_segmento = dias_pago_cliente.groupby(segmento_cliente).mean().reindex(SEGMENT_ORDER)

dso_moroso = dso_por_segmento["Moroso"]

# ---- concentración de riesgo: top-2 clientes por cartera pendiente ---------
pendiente_por_cliente = pendientes.groupby("cliente")["monto_mxn"].sum().sort_values(ascending=False)
top2_monto = pendiente_por_cliente.head(2).sum()
top2_pct = round(top2_monto / cartera_total * 100, 1) if cartera_total else 0

# ---- proyección de cobranza próximas 4 semanas, por segmento ---------------
# Se mantiene la curva de cobranza por antigüedad del bucket (más antigua =
# menos probable que se cobre pronto) pero desglosada por segmento, para
# mostrar de quién depende cada semana de flujo de caja -- no solo cuánto
# entra en total.
CURVAS_COBRANZA = {  # probabilidad de cobrarse en cada una de las próximas 4 semanas
    "Vigente (no vencida)": [0.15, 0.35, 0.30, 0.10],
    "1-30 días": [0.30, 0.30, 0.15, 0.08],
    "31-60 días": [0.15, 0.20, 0.20, 0.15],
    "61-90 días": [0.08, 0.10, 0.12, 0.12],
    "90+ días": [0.03, 0.04, 0.05, 0.05],
}
proyeccion = np.zeros(4)
proyeccion_por_segmento = {s: np.zeros(4) for s in SEGMENT_ORDER}
for (b, s), monto in pendientes.groupby(["bucket", "segmento"])["monto_mxn"].sum().items():
    curva = np.array(CURVAS_COBRANZA[b])
    proyeccion += monto * curva
    proyeccion_por_segmento[s] += monto * curva

# ---- matriz de riesgo: tamaño histórico del cliente x comportamiento de pago
monto_historico_cliente = df.groupby("cliente")["monto_mxn"].sum()
tamano_split = monto_historico_cliente.median()
comportamiento_split = 20.0  # frontera Puntual/Lento usada en la segmentación

# ---- clientes con facturas realmente vencidas hoy (checklist de cobranza) --
vencidas = pendientes[pendientes["dias_vencida"] > 0]
riesgo_cliente = vencidas.groupby(["cliente", "segmento"]).agg(
    monto=("monto_mxn", "sum"), dias_prom=("dias_vencida", "mean")
).reset_index().sort_values("monto", ascending=False)


def accion_de(segmento, dias_prom):
    if segmento == "Moroso":
        return "Congelar crédito nuevo + plan de pago"
    if dias_prom > 15:
        return "Llamada de cobranza esta semana"
    return "Recordatorio automático de pago"


riesgo_cliente["accion"] = riesgo_cliente.apply(lambda r: accion_de(r["segmento"], r["dias_prom"]), axis=1)

# ---- serie mensual: facturación vs cobranza ---------------------------------
df["mes_emision"] = df["fecha_emision"].dt.to_period("M")
facturacion_mensual = df.groupby("mes_emision")["monto_mxn"].sum()
pagadas["mes_pago"] = pagadas["fecha_pago"].dt.to_period("M")
cobranza_mensual = pagadas.groupby("mes_pago")["monto_mxn"].sum()
meses = sorted(set(facturacion_mensual.index) | set(cobranza_mensual.index))
facturacion_mensual = facturacion_mensual.reindex(meses).fillna(0)
cobranza_mensual = cobranza_mensual.reindex(meses).fillna(0)
mes_actual_idx = len(meses) - 1  # el último mes del rango siempre está incompleto (corte al día de hoy)

# ---- interactive dashboard --------------------------------------------------
banner = {
    "label": "La respuesta primero",
    "headline": (
        f"${cartera_vencida:,.0f} MXN ({pct_vencida}%) de la cartera está vencida, y el {top2_pct}% de todo lo "
        f"pendiente depende de solo 2 clientes con historial de pago de 100+ días."
    ),
    "subtext": (
        f"El DSO consolidado ({dso} días) esconde que el segmento Moroso tarda en promedio {dso_moroso:.0f} días en "
        f"pagar — casi {dso_moroso/dso:.1f}x el promedio general. No es un problema de flujo futuro difuso: es "
        f"concentración de riesgo en clientes identificables, con una acción distinta para cada uno esta semana."
    ),
}

kpis = [
    {"label": "Cartera vencida", "value": f"${cartera_vencida:,.0f} MXN ({pct_vencida}%)",
     "status": "critical" if pct_vencida > 35 else ("warning" if pct_vencida > 20 else "good"), "hero": True},
    {"label": "DSO consolidado vs. Moroso", "value": f"{dso} días / {dso_moroso:.0f} días", "status": "critical"},
    {"label": "Concentración top-2 clientes", "value": f"{top2_pct}% de la cartera pendiente",
     "status": "critical" if top2_pct > 60 else "warning"},
    {"label": "Cobranza proyectada (4 semanas)", "value": f"${proyeccion.sum():,.0f} MXN"},
]

table = {
    "title": "Cartera pendiente y DSO por segmento de cliente",
    "headers": ["Segmento", "Clientes", "Días promedio de pago", "Cartera pendiente", "% del total", "DSO (días)"],
    "rows": [
        [
            s, str(clientes_por_segmento[s]), f"{dias_pago_por_segmento[s]:.0f} días",
            f"${pendiente_por_segmento[s]:,.0f}",
            f"{pendiente_por_segmento[s] / cartera_total * 100:.1f}%" if cartera_total else "0%",
            f"{dso_por_segmento[s]:.1f}" if pendiente_por_segmento[s] > 0 else "N/D",
        ]
        for s in SEGMENT_ORDER
    ],
}

charts = [
    {
        "id": "chart_aging", "type": "bar",
        "title": "Antigüedad de cartera (AR Aging)",
        "subtitle": "Monto pendiente por rango de días vencido",
        "labels": list(aging.index),
        "datasets": [{"label": "Monto pendiente", "data": [round(v, 0) for v in aging.values]}],
        "y_label": "MXN",
    },
    {
        "id": "chart_segmento", "type": "bar",
        "title": "El 100% de la cartera pendiente está en 2 de 3 segmentos",
        "subtitle": "Cartera pendiente por segmento de comportamiento de pago",
        "labels": SEGMENT_ORDER,
        "datasets": [{"label": "Cartera pendiente", "data": [round(v, 0) for v in pendiente_por_segmento.values],
                      "colors": [STATUS[SEGMENT_STATUS[s]] for s in SEGMENT_ORDER]}],
        "y_label": "MXN",
    },
    {
        "id": "chart_matriz", "type": "scatter", "full_width": True,
        "title": "Quién es grande y además tarda en pagar — la prioridad real de cobranza",
        "subtitle": "Facturación histórica del cliente (tamaño) vs. días promedio para pagar (comportamiento)",
        "points": [
            {"x": round(monto_historico_cliente[c], 2), "y": round(dias_pago_cliente[c], 1),
             "label": f"{c} ({segmento_cliente[c]})", "status": SEGMENT_STATUS[segmento_cliente[c]]}
            for c in monto_historico_cliente.index
        ],
        "x_label": "Facturación histórica (MXN)", "y_label": "Días promedio para pagar",
        "x_unit": " MXN", "y_unit": " días",
        "point_radius": 8, "point_alpha": 0.8,
        "status_labels": {"good": "Puntual", "warning": "Lento", "critical": "Moroso"},
        "quadrant_lines": {"x": round(tamano_split, 2), "y": comportamiento_split},
        "quadrant_labels": [
            {"corner": "top-left", "text": "CHICO + TARDA (VIGILAR)"},
            {"corner": "top-right", "text": "GRANDE + TARDA (PRIORIDAD)"},
            {"corner": "bottom-left", "text": "CHICO + PUNTUAL"},
            {"corner": "bottom-right", "text": "GRANDE + PUNTUAL (ANCLA)"},
        ],
    },
    {
        "id": "chart_mensual", "type": "line", "full_width": True,
        "title": "La cobranza mensual crece, pero la concentración de riesgo no cambió",
        "subtitle": "Facturación vs. cobranza mensual — el último mes está incompleto (corte al día de hoy)",
        "labels": [str(m) for m in meses],
        "datasets": [
            {"label": "Facturación", "data": [round(v, 0) for v in facturacion_mensual.values]},
            {"label": "Cobranza", "data": [round(v, 0) for v in cobranza_mensual.values]},
        ],
        "y_label": "MXN",
        "marker": {"index": mes_actual_idx, "label": "Mes en curso (incompleto)"},
    },
    {
        "id": "chart_forecast", "type": "bar", "stacked": True, "full_width": True,
        "title": "Cobranza proyectada (4 semanas): de quién depende cada semana",
        "subtitle": "Puntual no aporta nada al pronóstico — ya no tiene cartera pendiente",
        "labels": [f"Semana {i+1}" for i in range(4)],
        "datasets": [
            {"label": s, "data": [round(v, 0) for v in proyeccion_por_segmento[s]],
             "colors": STATUS[SEGMENT_STATUS[s]]}
            for s in SEGMENT_ORDER
        ],
        "y_label": "MXN esperados",
    },
]

checklist = {
    "id": "cobranza_semana",
    "title": "Checklist de cobranza — clientes con facturas vencidas hoy",
    "subtitle": f"{len(riesgo_cliente)} clientes con cartera realmente vencida, con la acción recomendada según su segmento. Marca cada uno al gestionarlo.",
    "progress_noun": "gestionados",
    "headers": ["Cliente", "Segmento", "Monto vencido", "Días vencida (prom.)", "Acción recomendada"],
    "rows": [
        {
            "id": r.cliente,
            "cells": [r.cliente, r.segmento, f"${r.monto:,.0f}", f"{r.dias_prom:.0f} días", r.accion],
        }
        for r in riesgo_cliente.itertuples()
    ],
}

insights = [
    f"<b>${top2_monto:,.0f} MXN ({top2_pct}%)</b> de la cartera pendiente está en solo 2 clientes — Importadora Tres Ríos y Servicios Integrales Roble, ambos del segmento Moroso. El riesgo de cash flow no está diversificado: está concentrado, y se gestiona con seguimiento dedicado a esos 2 clientes, no con una campaña genérica de cobranza.",
    f"El DSO consolidado (<b>{dso} días</b>) esconde que el segmento Moroso tarda en promedio <b>{dso_moroso:.0f} días</b> en pagar — casi 3 veces más. Reportar solo el DSO consolidado subestima el riesgo real; el DSO por segmento debería ser el número que se sigue mes a mes.",
    "Los 3 clientes del segmento Puntual (Grupo Ferretero del Bajío, Distribuidora Maple, Grupo Industrial Norte) no tienen ni un peso pendiente hoy — el 100% de la cartera por cobrar está en los segmentos Lento y Moroso. El esfuerzo de cobranza debe concentrarse ahí, no repartirse parejo entre los 8 clientes.",
    "La curva de cobranza por antigüedad proyecta que buena parte de la cartera Moroso se cobrará en las próximas 4 semanas — pero esa curva es genérica y no usa el historial real de esos clientes, que ha tardado 100+ días en pagar en el pasado. Para el segmento Moroso, esa proyección debe leerse como el escenario optimista, no el esperado.",
    f"La cobranza mensual creció de ${cobranza_mensual.iloc[0]:,.0f} MXN en {meses[0]} a ${cobranza_mensual.iloc[-2]:,.0f} MXN en el último mes completo — una tendencia sana en apariencia, pero la concentración de riesgo en 2 clientes no cambió con esa tendencia. La cobranza agregada mejorando no significa que el riesgo de cartera bajó.",
    f"De los {len(riesgo_cliente)} clientes con facturas vencidas hoy, los 2 del segmento Moroso concentran <b>{riesgo_cliente[riesgo_cliente['segmento']=='Moroso']['monto'].sum() / riesgo_cliente['monto'].sum() * 100:.0f}%</b> del monto vencido y requieren la acción más urgente (congelar crédito nuevo + plan de pago), no solo una llamada de cobranza — ver el checklist de esta semana.",
    "Recomendación de política de crédito: exigir anticipo o reducir el límite de crédito a cualquier cliente que caiga en el perfil Moroso (más de 70 días promedio de pago histórico) antes de que acumule más cartera vencida — de lo contrario, la concentración de riesgo vuelve a crecer con cada nueva venta a crédito a esos clientes.",
]

dash.render(
    ROOT / "dashboard.html",
    project_no=8,
    title="Flujo de Caja y Cartera Vencida",
    tagline="No 'cuánto hay pendiente de cobrar', sino de quién depende ese dinero y qué acción tomar con cada uno esta semana.",
    banner=banner,
    kpis=kpis,
    charts=charts,
    insights=insights,
    table=table,
    table_position="top",
    checklist=checklist,
    chart_cols=2,
)

print(f"Cartera vencida: ${cartera_vencida:,.0f} ({pct_vencida}%) | DSO: {dso}d (Moroso: {dso_moroso:.0f}d) | Concentración top-2: {top2_pct}% | Proyección 4 sem: ${proyeccion.sum():,.0f}")
print("OK -> dashboard.html")
