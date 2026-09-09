"""
Genera respuestas sintéticas de encuestas NPS durante 12 meses, con una
caída deliberada del NPS en los últimos 2 meses concentrada en una causa
raíz específica (tiempo de respuesta de soporte) -- el tipo de análisis de
voz del cliente que Diego trabajó de forma extensa en Qualtrics.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(303)

MOTIVOS = ["Tiempo de respuesta", "Calidad del producto", "Precio", "Atención al cliente", "Facilidad de uso"]
months = pd.date_range("2025-09-01", periods=12, freq="MS").strftime("%Y-%m")

rows = []
resp_id = 1
for i, mes in enumerate(months):
    n = np.random.randint(120, 170)
    # la distribución de score se deteriora en los últimos 2 meses
    if i >= 10:
        sesgo = -0.7
    else:
        sesgo = 0.0
    for _ in range(n):
        score = np.clip(np.random.normal(8.1 + sesgo, 1.8), 0, 10)
        score = int(round(score))
        if score <= 6:
            categoria = "Detractor"
        elif score <= 8:
            categoria = "Pasivo"
        else:
            categoria = "Promotor"

        motivo = None
        if categoria == "Detractor":
            if i >= 10:
                # en los últimos 2 meses, la causa dominante es tiempo de respuesta
                motivo = np.random.choice(MOTIVOS, p=[0.55, 0.15, 0.12, 0.1, 0.08])
            else:
                motivo = np.random.choice(MOTIVOS, p=[0.2, 0.25, 0.2, 0.2, 0.15])

        rows.append({
            "respuesta_id": f"R-{resp_id:05d}", "mes": mes, "score": score,
            "categoria": categoria, "motivo_detractor": motivo,
        })
        resp_id += 1

df = pd.DataFrame(rows)
out = Path(__file__).parent / "encuestas_nps.csv"
df.to_csv(out, index=False)
print(f"Generadas {len(df)} respuestas de NPS -> {out}")
