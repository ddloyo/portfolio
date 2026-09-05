"""
Genera facturas sintéticas por cobrar con distintos perfiles de cliente
(pagadores puntuales, pagadores lentos, morosos) para poder construir un
análisis de antigüedad de cartera (AR aging) y proyección de flujo de caja.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

np.random.seed(66)
TODAY = date(2026, 8, 31)

CLIENTES = {
    "Grupo Ferretero del Bajío": {"perfil": "puntual", "n_facturas": 14, "ticket": 85000},
    "Distribuidora Maple": {"perfil": "puntual", "n_facturas": 10, "ticket": 62000},
    "Comercial Alfa y Omega": {"perfil": "lento", "n_facturas": 12, "ticket": 48000},
    "Constructora del Valle": {"perfil": "lento", "n_facturas": 9, "ticket": 110000},
    "Servicios Integrales Roble": {"perfil": "moroso", "n_facturas": 8, "ticket": 74000},
    "Importadora Tres Ríos": {"perfil": "moroso", "n_facturas": 7, "ticket": 95000},
    "Grupo Industrial Norte": {"perfil": "puntual", "n_facturas": 11, "ticket": 130000},
    "Refaccionaria Central": {"perfil": "lento", "n_facturas": 13, "ticket": 30000},
}

PERFIL_DIAS_PAGO = {"puntual": (5, 15), "lento": (35, 65), "moroso": (75, 160)}

rows = []
fac_id = 1
for cliente, cfg in CLIENTES.items():
    for _ in range(cfg["n_facturas"]):
        fecha_emision = TODAY - timedelta(days=int(np.random.uniform(10, 180)))
        fecha_vencimiento = fecha_emision + timedelta(days=30)
        monto = max(5000, np.random.gamma(shape=2.5, scale=cfg["ticket"] / 2.5))

        dias_pago_min, dias_pago_max = PERFIL_DIAS_PAGO[cfg["perfil"]]
        dias_para_pagar = int(np.random.uniform(dias_pago_min, dias_pago_max))
        fecha_pago_hipotetica = fecha_emision + timedelta(days=dias_para_pagar)

        if fecha_pago_hipotetica <= TODAY:
            estatus = "Pagada"
            fecha_pago = fecha_pago_hipotetica.isoformat()
        else:
            estatus = "Pendiente"
            fecha_pago = ""

        rows.append({
            "factura_id": f"F-{fac_id:04d}",
            "cliente": cliente,
            "fecha_emision": fecha_emision.isoformat(),
            "fecha_vencimiento": fecha_vencimiento.isoformat(),
            "monto_mxn": round(monto, 2),
            "estatus": estatus,
            "fecha_pago": fecha_pago,
        })
        fac_id += 1

df = pd.DataFrame(rows)
out = Path(__file__).parent / "facturas.csv"
df.to_csv(out, index=False)
print(f"Generadas {len(df)} facturas ({(df['estatus']=='Pendiente').sum()} pendientes) -> {out}")
