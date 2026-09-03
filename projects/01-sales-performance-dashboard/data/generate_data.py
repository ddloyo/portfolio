"""
Genera datos sintéticos de ventas diarias por equipo comercial.

Simula el escenario típico descrito en la propuesta de valor de XIA:
"Ventas por equipo, en tiempo real — dejas de esperar el cierre de mes
para reaccionar." Cuatro equipos, 6 meses de historia, con meta mensual
por equipo para poder calcular % de cumplimiento.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date

np.random.seed(42)

TEAMS = ["Centro", "Norte", "Occidente", "Sureste"]
REPS_PER_TEAM = 5
MONTHLY_GOAL = {"Centro": 1_450_000, "Norte": 980_000, "Occidente": 1_120_000, "Sureste": 760_000}
PRODUCT_LINES = ["Software", "Servicios", "Hardware", "Soporte"]

start = date(2026, 1, 1)
end = date(2026, 8, 31)
all_days = pd.date_range(start, end, freq="D")

rows = []
rep_id = 1
reps = {}
for team in TEAMS:
    reps[team] = [f"{team[:3].upper()}-{i+1:02d}" for i in range(REPS_PER_TEAM)]

TEAM_BASELINE = {"Centro": 1.06, "Norte": 0.99, "Occidente": 1.02, "Sureste": 0.91}

for day in all_days:
    if day.weekday() >= 5:  # skip weekends, B2B sales
        continue
    month_factor = 1 + 0.06 * np.sin((day.month - 3) / 6 * np.pi)  # mild seasonality
    for team in TEAMS:
        # Occidente has a visible slump in July-Aug (the "problema" narrative)
        dip = 0.62 if (team == "Occidente" and day.month >= 7) else 1.0
        team_factor = TEAM_BASELINE[team] * dip
        n_deals = np.random.poisson(5.0 * team_factor)
        for _ in range(n_deals):
            rep = np.random.choice(reps[team])
            base = MONTHLY_GOAL[team] / 22 / REPS_PER_TEAM
            amount = max(500, np.random.gamma(shape=2.2, scale=base / 2.2) * month_factor)
            rows.append({
                "fecha": day.date().isoformat(),
                "equipo": team,
                "vendedor": rep,
                "linea_producto": np.random.choice(PRODUCT_LINES, p=[0.4, 0.3, 0.2, 0.1]),
                "monto_mxn": round(amount, 2),
            })
        rep_id += 1

df = pd.DataFrame(rows)
out = Path(__file__).parent / "ventas_diarias.csv"
df.to_csv(out, index=False)

goals = pd.DataFrame([{"equipo": t, "meta_mensual_mxn": g} for t, g in MONTHLY_GOAL.items()])
goals.to_csv(Path(__file__).parent / "metas_mensuales.csv", index=False)

print(f"Generadas {len(df)} transacciones -> {out}")
