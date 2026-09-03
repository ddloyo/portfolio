"""
Genera un funnel comercial semanal sintético con una fuga deliberada en la
transición Calificados -> Propuesta a partir de la semana 10 (de 16), para
poder demostrar una alerta automática de fuga -- el entregable "Funnel con
alertas automáticas" de la propuesta de valor de XIA.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(7)

N_WEEKS = 16
rows = []

for week in range(1, N_WEEKS + 1):
    leads = int(np.random.normal(520, 40))
    contact_rate = np.clip(np.random.normal(0.74, 0.03), 0.6, 0.9)
    qualify_rate = np.clip(np.random.normal(0.52, 0.03), 0.35, 0.7)

    # la fuga: la tasa de calificados -> propuesta cae de ~55% a ~28% desde la semana 10
    if week < 10:
        propose_rate = np.clip(np.random.normal(0.55, 0.03), 0.4, 0.7)
    else:
        # caída progresiva, como ocurre en la vida real (no es un escalón perfecto)
        decay = min((week - 9) * 0.045, 0.27)
        propose_rate = np.clip(np.random.normal(0.55 - decay, 0.03), 0.2, 0.6)

    close_rate = np.clip(np.random.normal(0.34, 0.03), 0.2, 0.5)

    contactados = int(leads * contact_rate)
    calificados = int(contactados * qualify_rate)
    propuestas = int(calificados * propose_rate)
    cierres = int(propuestas * close_rate)

    rows.append({
        "semana": week,
        "leads": leads,
        "contactados": contactados,
        "calificados": calificados,
        "propuestas": propuestas,
        "cierres": cierres,
    })

df = pd.DataFrame(rows)
out = Path(__file__).parent / "funnel_semanal.csv"
df.to_csv(out, index=False)
print(f"Generadas {len(df)} semanas de funnel -> {out}")
