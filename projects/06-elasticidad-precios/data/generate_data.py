"""
Genera historial semanal sintético de precio y unidades vendidas para 8
productos, cada uno con una elasticidad-precio "real" distinta (algunos
elásticos, algunos inelásticos) para poder estimarla después con una
regresión log-log -- el tipo de análisis de price intelligence que Diego
desarrolló en su etapa de Sales Analytics / Pricing en la industria
industrial.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(55)

PRODUCTS = {
    "Componente A (commodity)": {"elasticidad": -2.1, "precio_base": 145, "demanda_base": 900},
    "Componente B (commodity)": {"elasticidad": -1.7, "precio_base": 98, "demanda_base": 1200},
    "Kit de mantenimiento": {"elasticidad": -1.1, "precio_base": 310, "demanda_base": 420},
    "Repuesto especializado X": {"elasticidad": -0.6, "precio_base": 780, "demanda_base": 150},
    "Repuesto especializado Y": {"elasticidad": -0.4, "precio_base": 1250, "demanda_base": 90},
    "Servicio de instalación": {"elasticidad": -0.5, "precio_base": 2100, "demanda_base": 60},
    "Accesorio estándar": {"elasticidad": -1.9, "precio_base": 60, "demanda_base": 2100},
    "Refacción crítica (sin sustituto)": {"elasticidad": -0.25, "precio_base": 540, "demanda_base": 210},
}

N_WEEKS = 52
rows = []
for producto, cfg in PRODUCTS.items():
    precio = cfg["precio_base"]
    for week in range(1, N_WEEKS + 1):
        # cambios de precio ocasionales (~cada 6-9 semanas), +/- 8%
        if week > 1 and week % np.random.randint(6, 10) == 0:
            precio = precio * (1 + np.random.choice([-1, 1]) * np.random.uniform(0.03, 0.09))
        precio_semana = precio * (1 + np.random.normal(0, 0.01))
        log_demanda = (
            np.log(cfg["demanda_base"])
            + cfg["elasticidad"] * (np.log(precio_semana) - np.log(cfg["precio_base"]))
            + np.random.normal(0, 0.06)
        )
        unidades = max(1, np.exp(log_demanda))
        rows.append({
            "producto": producto,
            "semana": week,
            "precio_mxn": round(precio_semana, 2),
            "unidades_vendidas": round(unidades, 0),
        })

df = pd.DataFrame(rows)
out = Path(__file__).parent / "precio_demanda.csv"
df.to_csv(out, index=False)
print(f"Generadas {len(df)} observaciones semana-producto -> {out}")
