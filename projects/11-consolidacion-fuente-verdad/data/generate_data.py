"""
Genera 3 exports "crudos" y deliberadamente inconsistentes -- como los que
mandaría cada sucursal por su cuenta -- con columnas distintas, formatos de
fecha distintos, nombres de sucursal escritos de forma distinta, filas
duplicadas y montos faltantes. El objetivo del proyecto es consolidarlos
en una sola fuente de verdad limpia.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

np.random.seed(202)
OUT = Path(__file__).parent
start = date(2026, 6, 1)
end = date(2026, 8, 31)
days = pd.date_range(start, end, freq="D")


def build_branch(nombre, n_por_dia_lambda):
    rows = []
    for day in days:
        n = np.random.poisson(n_por_dia_lambda)
        for _ in range(n):
            monto = max(200, np.random.gamma(2.2, 450))
            rows.append({"fecha": day.date(), "sucursal": nombre, "monto": round(monto, 2)})
    return pd.DataFrame(rows)


cdmx = build_branch("CDMX", 6)
mty = build_branch("Monterrey", 4)
gdl = build_branch("Guadalajara", 3)

# --- export 1: CDMX, columnas en español, fecha DD/MM/YYYY, ~4% duplicados
cdmx_raw = cdmx.copy()
dup_idx = cdmx_raw.sample(frac=0.04, random_state=1).index
cdmx_raw = pd.concat([cdmx_raw, cdmx_raw.loc[dup_idx]], ignore_index=True)
cdmx_raw["Fecha"] = pd.to_datetime(cdmx_raw["fecha"]).dt.strftime("%d/%m/%Y")
cdmx_raw["Sucursal"] = cdmx_raw["sucursal"]
cdmx_raw["Monto"] = cdmx_raw["monto"]
cdmx_raw[["Fecha", "Sucursal", "Monto"]].to_csv(OUT / "raw_export_cdmx.csv", index=False)

# --- export 2: Monterrey, columnas distintas, fecha ISO, nombre "MTY", ~3% monto faltante
mty_raw = mty.copy()
mty_raw["fecha_venta"] = pd.to_datetime(mty_raw["fecha"]).dt.strftime("%Y-%m-%d")
mty_raw["tienda"] = "MTY"
mty_raw["importe_mxn"] = mty_raw["monto"]
missing_idx = mty_raw.sample(frac=0.03, random_state=2).index
mty_raw.loc[missing_idx, "importe_mxn"] = np.nan
mty_raw[["fecha_venta", "tienda", "importe_mxn"]].to_csv(OUT / "raw_export_monterrey.csv", index=False)

# --- export 3: Guadalajara, encabezados en inglés (sistema legado), fecha MM/DD/YYYY,
#     nombre de sucursal con inconsistencias de mayúsculas/espacios
gdl_raw = gdl.copy()
gdl_raw["Date"] = pd.to_datetime(gdl_raw["fecha"]).dt.strftime("%m/%d/%Y")
labels = ["guadalajara", "GDL ", "Guadalajara"]
gdl_raw["Store"] = [labels[i % len(labels)] for i in range(len(gdl_raw))]
gdl_raw["Amount_MXN"] = gdl_raw["monto"]
gdl_raw[["Date", "Store", "Amount_MXN"]].to_csv(OUT / "raw_export_guadalajara.csv", index=False)

print("Generados 3 exports crudos e inconsistentes:")
print(f"  raw_export_cdmx.csv         -> {len(cdmx_raw)} filas (incluye duplicados)")
print(f"  raw_export_monterrey.csv    -> {len(mty_raw)} filas (incluye montos faltantes)")
print(f"  raw_export_guadalajara.csv  -> {len(gdl_raw)} filas (nombres de sucursal inconsistentes)")
