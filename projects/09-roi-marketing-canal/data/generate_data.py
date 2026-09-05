"""
Genera inversión mensual de marketing y clientes nuevos adquiridos por
canal durante 12 meses, más supuestos de valor de vida (LTV) por canal, ya
que distintos canales no solo cuestan distinto sino que traen clientes de
distinta calidad/retención.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(88)

CANALES = {
    "Referidos": {"gasto_mensual": 8000, "cac_real": 380, "ticket_prom": 950, "meses_retencion": 18, "margen": 0.42},
    "SEO / Orgánico": {"gasto_mensual": 22000, "cac_real": 620, "ticket_prom": 780, "meses_retencion": 14, "margen": 0.42},
    "Google Ads": {"gasto_mensual": 65000, "cac_real": 1450, "ticket_prom": 820, "meses_retencion": 9, "margen": 0.40},
    "Meta Ads": {"gasto_mensual": 58000, "cac_real": 1180, "ticket_prom": 690, "meses_retencion": 7, "margen": 0.38},
    "Email marketing": {"gasto_mensual": 6000, "cac_real": 210, "ticket_prom": 600, "meses_retencion": 11, "margen": 0.42},
    "Eventos / Ferias": {"gasto_mensual": 30000, "cac_real": 2100, "ticket_prom": 1400, "meses_retencion": 20, "margen": 0.45},
}

months = pd.date_range("2025-08-01", periods=12, freq="MS").strftime("%Y-%m")
rows = []
for canal, cfg in CANALES.items():
    for mes in months:
        gasto = max(0, np.random.normal(cfg["gasto_mensual"], cfg["gasto_mensual"] * 0.08))
        clientes_nuevos = max(1, round(gasto / cfg["cac_real"] * np.random.normal(1, 0.1)))
        rows.append({
            "canal": canal, "mes": mes, "gasto_mxn": round(gasto, 2), "clientes_nuevos": clientes_nuevos,
            "ticket_promedio_mxn": cfg["ticket_prom"], "meses_retencion_prom": cfg["meses_retencion"],
            "margen_bruto": cfg["margen"],
        })

df = pd.DataFrame(rows)
out = Path(__file__).parent / "marketing_canales.csv"
df.to_csv(out, index=False)
print(f"Generadas {len(df)} filas de gasto/adquisición por canal -> {out}")
