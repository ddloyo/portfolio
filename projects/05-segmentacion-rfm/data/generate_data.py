"""
Genera transacciones sintéticas de clientes retail/e-commerce durante 12
meses, con perfiles de compra deliberadamente distintos (clientes
frecuentes de alto valor, clientes nuevos, clientes que dejaron de comprar,
etc.) para poder construir una segmentación RFM realista.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

np.random.seed(33)
TODAY = date(2026, 8, 31)
N_CUSTOMERS = 600

PROFILES = [
    # (nombre, proporción, freq_mensual_media, ticket_medio, meses_activo_recientes)
    ("campeon", 0.10, 3.2, 950, 12),
    ("leal", 0.20, 1.6, 620, 12),
    ("en_riesgo", 0.18, 1.2, 780, 5),     # compraba bien pero dejó de comprar hace meses
    ("hibernando", 0.22, 0.6, 350, 2),
    ("nuevo", 0.15, 1.0, 450, 1),
    ("ocasional", 0.15, 0.4, 300, 8),
]

rows = []
cust_id = 1
for perfil, prop, freq, ticket, meses_activo in PROFILES:
    n = int(N_CUSTOMERS * prop)
    for _ in range(n):
        n_compras = max(1, int(np.random.poisson(freq * meses_activo)))
        # ventana de actividad: para "en_riesgo" y "hibernando", la actividad se concentra en el pasado
        if perfil in ("en_riesgo", "hibernando"):
            window_end = TODAY - timedelta(days=int(np.random.uniform(90, 220)))
            window_start = window_end - timedelta(days=meses_activo * 30)
        else:
            window_end = TODAY - timedelta(days=int(np.random.uniform(0, 15)))
            window_start = TODAY - timedelta(days=meses_activo * 30)
        span_days = max(1, (window_end - window_start).days)
        for _ in range(n_compras):
            fecha = window_start + timedelta(days=int(np.random.uniform(0, span_days)))
            monto = max(80, np.random.gamma(shape=2.5, scale=ticket / 2.5))
            rows.append({
                "cliente_id": f"C-{cust_id:04d}",
                "fecha": fecha.isoformat(),
                "monto_mxn": round(monto, 2),
            })
        cust_id += 1

df = pd.DataFrame(rows)
out = Path(__file__).parent / "transacciones.csv"
df.to_csv(out, index=False)
print(f"Generadas {len(df)} transacciones de {cust_id - 1} clientes -> {out}")
