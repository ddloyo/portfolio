"""
Genera un scorecard ejecutivo sintético: metas vs. resultados cruzando
áreas (Ventas, Marketing, Operaciones, Finanzas, Servicio), cada indicador
con un responsable claro -- el entregable "Metas vs. resultados, sin
vueltas: una pantalla, una conclusión, una acción" de XIA.

Produce:
  1. data/kpi_historico.csv -> resultado mensual (9 meses) de cada uno de
     los 10 KPIs, para dibujar tendencias, dispersión y correlación.
  2. data/scorecard.csv     -> snapshot del mes actual (el último mes del
     histórico), usado para los tiles y la tabla de detalle.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(11)

KPIS = [
    {"kpi": "Ingresos mensuales", "area": "Ventas", "owner": "Dir. Comercial", "meta": 3_200_000, "unidad": "MXN", "sesgo": 0.02},
    {"kpi": "Nuevos clientes", "area": "Ventas", "owner": "Dir. Comercial", "meta": 45, "unidad": "clientes", "sesgo": -0.08},
    {"kpi": "Costo de adquisición (CAC)", "area": "Marketing", "owner": "Gerente de Marketing", "meta": 1800, "unidad": "MXN", "sesgo": 0.12, "menor_es_mejor": True},
    {"kpi": "Leads calificados", "area": "Marketing", "owner": "Gerente de Marketing", "meta": 380, "unidad": "leads", "sesgo": 0.05},
    {"kpi": "Entregas a tiempo", "area": "Operaciones", "owner": "Gerente de Operaciones", "meta": 96, "unidad": "%", "sesgo": -0.03},
    {"kpi": "Costo operativo por unidad", "area": "Operaciones", "owner": "Gerente de Operaciones", "meta": 210, "unidad": "MXN", "sesgo": 0.04, "menor_es_mejor": True},
    {"kpi": "Cobranza a 30 días", "area": "Finanzas", "owner": "Gerente de Finanzas", "meta": 90, "unidad": "%", "sesgo": -0.11},
    {"kpi": "Cartera vencida", "area": "Finanzas", "owner": "Gerente de Finanzas", "meta": 5, "unidad": "%", "sesgo": 0.35, "menor_es_mejor": True},
    {"kpi": "CSAT (satisfacción)", "area": "Servicio", "owner": "Gerente de Servicio", "meta": 4.5, "unidad": "/5", "sesgo": -0.02},
    {"kpi": "Tickets resueltos < 24h", "area": "Servicio", "owner": "Gerente de Servicio", "meta": 85, "unidad": "%", "sesgo": 0.01},
]

MONTHS = pd.date_range("2026-01-01", periods=9, freq="MS").strftime("%Y-%m")

# ---- histórico mensual por KPI --------------------------------------------
# El sesgo del mes actual (el último) es el que ya vivía en el snapshot
# original; los meses previos derivan hacia ese sesgo con una tendencia
# suave + ruido, para que la serie se vea orgánica y no una línea recta.
hist_rows = []
for k in KPIS:
    trend = np.linspace(k["sesgo"] * 0.25, k["sesgo"], len(MONTHS))
    noise = np.random.normal(0, 0.035, size=len(MONTHS))
    monthly_bias = trend + noise
    for mes, bias in zip(MONTHS, monthly_bias):
        resultado = k["meta"] * (1 + bias)
        hist_rows.append({"mes": mes, "kpi": k["kpi"], "area": k["area"], "resultado": round(resultado, 2)})

hist = pd.DataFrame(hist_rows)
hist_out = Path(__file__).parent / "kpi_historico.csv"
hist.to_csv(hist_out, index=False)

# ---- snapshot del mes actual (= último mes del histórico) ----------------
last_month = MONTHS[-1]
current = hist[hist["mes"] == last_month].set_index("kpi")["resultado"]

rows = []
for k in KPIS:
    rows.append({
        "kpi": k["kpi"], "area": k["area"], "responsable": k["owner"],
        "meta": round(k["meta"], 2), "resultado": current[k["kpi"]],
        "unidad": k["unidad"], "menor_es_mejor": k.get("menor_es_mejor", False),
    })

df = pd.DataFrame(rows)
scorecard_out = Path(__file__).parent / "scorecard.csv"
df.to_csv(scorecard_out, index=False)

print(f"Generado histórico de {len(KPIS)} KPIs x {len(MONTHS)} meses -> {hist_out}")
print(f"Generado scorecard (mes actual: {last_month}) -> {scorecard_out}")
