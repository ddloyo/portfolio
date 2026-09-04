"""
Genera una base sintética de clientes tipo suscripción/membresía con
variables de comportamiento y una etiqueta histórica de churn, construida
para que el churn dependa de forma realista de: antigüedad, tickets de
soporte, uso del producto y días desde la última compra/actividad.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(21)
N = 1200

tenure_months = np.random.gamma(shape=2.0, scale=9, size=N).clip(1, 60).round(0)
monthly_spend = np.random.gamma(shape=3.0, scale=280, size=N).round(2)
support_tickets_90d = np.random.poisson(1.1, size=N)
days_since_last_activity = np.random.exponential(18, size=N).clip(0, 180).round(0)
usage_score = np.clip(np.random.normal(62, 20, size=N), 0, 100).round(1)
contract_type = np.random.choice(["Mensual", "Anual"], size=N, p=[0.65, 0.35])
plan = np.random.choice(["Starter", "Pro", "Business"], size=N, p=[0.45, 0.35, 0.2])

# probabilidad de churn "real" (para generar la etiqueta) según un modelo latente razonable
logit = (
    -2.0
    + 0.032 * days_since_last_activity
    + 0.45 * support_tickets_90d
    - 0.03 * usage_score
    - 0.02 * tenure_months
    + np.where(contract_type == "Mensual", 0.6, -0.6)
    + np.random.normal(0, 0.35, size=N)
)
prob_churn = 1 / (1 + np.exp(-logit))
churned = (np.random.rand(N) < prob_churn).astype(int)

df = pd.DataFrame({
    "cliente_id": [f"CLI-{i:05d}" for i in range(1, N + 1)],
    "antiguedad_meses": tenure_months,
    "gasto_mensual_mxn": monthly_spend,
    "tickets_soporte_90d": support_tickets_90d,
    "dias_desde_ultima_actividad": days_since_last_activity,
    "usage_score": usage_score,
    "tipo_contrato": contract_type,
    "plan": plan,
    "churn_historico": churned,
})

out = Path(__file__).parent / "clientes.csv"
df.to_csv(out, index=False)
print(f"Generados {len(df)} clientes ({df['churn_historico'].mean()*100:.1f}% churn histórico) -> {out}")
