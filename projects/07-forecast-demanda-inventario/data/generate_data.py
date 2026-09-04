"""
Genera demanda diaria sintética de 400 SKUs durante 18 meses, agrupados en
5 categorías de producto (cada categoría = un proveedor -> mismo lead time
para todos sus SKUs), con una mezcla de 5 perfiles de volumen de demanda
(alta/media/baja/esporádica/nula), más un snapshot de inventario, costo y
precio unitario por SKU.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date

np.random.seed(9)

N_SKUS = 400
OUT_DIR = Path(__file__).parent

start = date(2025, 3, 1)
end = date(2026, 8, 31)
days = pd.date_range(start, end, freq="D")
n_days = len(days)
fechas_str = days.strftime("%Y-%m-%d").to_numpy()

weekday_index = np.array([1.0, 1.05, 1.1, 1.1, 1.25, 0.75, 0.55])  # lun..dom, pico jue/vie, baja fin de semana
dow = days.weekday.to_numpy()
day_of_year = days.dayofyear.to_numpy()
t_years = np.arange(n_days) / 365

# ---- categorías: 5 categorías, cada una = 1 proveedor -> 1 lead time --------
CATEGORIAS = {
    "Alimentos y Bebidas":       {"lead_time_dias": 6,  "costo_rango": (15, 60)},
    "Limpieza del Hogar":        {"lead_time_dias": 10, "costo_rango": (10, 45)},
    "Cuidado Personal":          {"lead_time_dias": 14, "costo_rango": (20, 80)},
    "Ferretería y Herramientas": {"lead_time_dias": 21, "costo_rango": (30, 150)},
    "Electrónica y Accesorios":  {"lead_time_dias": 30, "costo_rango": (50, 300)},
}
categoria_nombres = list(CATEGORIAS.keys())

# distribución aleatoria (no uniforme) de las 400 SKUs entre las 5 categorías
pesos_categoria = np.random.dirichlet(np.ones(len(categoria_nombres)) * 4)
categoria_sku = np.random.choice(categoria_nombres, size=N_SKUS, p=pesos_categoria)

# ---- mezcla de demanda: 20% alta / 40% media / 20% baja / 15% esporádica / 5% nula --
n_alta = int(round(N_SKUS * 0.20))
n_media = int(round(N_SKUS * 0.40))
n_baja = int(round(N_SKUS * 0.20))
n_esporadica = int(round(N_SKUS * 0.15))
n_nula = N_SKUS - (n_alta + n_media + n_baja + n_esporadica)  # resto exacto -> 5%

segmentos = np.array(
    ["alta"] * n_alta
    + ["media"] * n_media
    + ["baja"] * n_baja
    + ["esporadica"] * n_esporadica
    + ["nula"] * n_nula
)
np.random.shuffle(segmentos)

PERFIL_DEMANDA = {
    "alta": {"base": (60, 150)},
    "media": {"base": (20, 60)},
    "baja": {"base": (5, 20)},
    "esporadica": {"base": (3, 12), "prob_venta": (0.15, 0.4)},
    "nula": {"base": (0.05, 0.3)},
}

skus = [f"SKU-{i:04d}" for i in range(1, N_SKUS + 1)]

demanda_por_sku = []
sku_rows = []

for i, sku in enumerate(skus):
    categoria = categoria_sku[i]
    segmento = segmentos[i]
    perfil = PERFIL_DEMANDA[segmento]

    base = np.random.uniform(*perfil["base"])
    tendencia_anual = np.random.uniform(-0.10, 0.20)
    es_estacional = np.random.rand() < 0.15
    amp_estacional = np.random.uniform(0.3, 0.6) if es_estacional else 0.0
    fase = np.random.uniform(0, 2 * np.pi)

    tendencia = 1 + tendencia_anual * t_years
    estacional_semana = weekday_index[dow]
    estacional_anual = 1 + amp_estacional * np.sin((day_of_year / 365) * 2 * np.pi + fase)
    media = base * tendencia * estacional_semana * estacional_anual
    media = np.maximum(media, 0.01)

    if segmento == "esporadica":
        prob_venta = np.random.uniform(*perfil["prob_venta"])
        ocurre = np.random.rand(n_days) < prob_venta
        demanda = np.where(ocurre, np.random.poisson(media), 0)
    else:
        demanda = np.random.poisson(media)

    demanda = np.maximum(demanda, 0).astype(int)
    demanda_por_sku.append(demanda)

    # ---- costo y precio: costo acotado a +/-2.5 std dentro de su categoría --
    costo_min, costo_max = CATEGORIAS[categoria]["costo_rango"]
    costo_media_cat = (costo_min + costo_max) / 2
    costo_std_cat = (costo_max - costo_min) / 6
    costo = np.random.normal(costo_media_cat, costo_std_cat)
    # se acota con margen extra (2.2 std en vez de 2.5) porque el std muestral
    # real de la categoría, calculado después con todos los SKUs ya generados,
    # puede quedar un poco por debajo del std teórico usado aquí
    costo = np.clip(costo, costo_media_cat - 2.2 * costo_std_cat, costo_media_cat + 2.2 * costo_std_cat)
    costo = round(max(costo, 1.0), 2)

    margen = np.random.uniform(0.10, 0.45)
    precio = round(costo / (1 - margen), 2)

    # ---- stock actual: se calibra más abajo para lograr ~320 sanos / 80 en riesgo --
    avg_daily_demand = demanda[-90:].mean()
    daily_std = demanda[-90:].std()
    lead_time = CATEGORIAS[categoria]["lead_time_dias"]
    reorder_point_aprox = avg_daily_demand * lead_time + 1.65 * daily_std * np.sqrt(lead_time)

    sku_rows.append({
        "sku": sku,
        "categoria": categoria,
        "segmento_demanda": segmento,
        "lead_time_dias": lead_time,
        "costo_unitario": costo,
        "precio_unitario": precio,
        "margen_pct": round(margen * 100, 1),
        "_reorder_point_aprox": reorder_point_aprox,
    })

inv = pd.DataFrame(sku_rows)

# ---- calibrar stock_actual: 80 SKUs (20%) en riesgo, 320 sanos --------------
n_en_riesgo = 80
idx_en_riesgo = np.random.choice(inv.index, size=n_en_riesgo, replace=False)
factor = np.where(
    inv.index.isin(idx_en_riesgo),
    np.random.uniform(0.5, 0.9, size=len(inv)),
    np.random.uniform(1.3, 4.0, size=len(inv)),
)
stock_actual = np.maximum(inv["_reorder_point_aprox"] * factor, 1).round().astype(int)
inv["stock_actual"] = stock_actual
inv = inv.drop(columns="_reorder_point_aprox")
inv = inv[["sku", "categoria", "segmento_demanda", "lead_time_dias", "stock_actual",
           "costo_unitario", "precio_unitario", "margen_pct"]]

# ---- exportar demanda diaria (formato largo) --------------------------------
all_skus = np.repeat(skus, n_days)
all_fechas = np.tile(fechas_str, N_SKUS)
all_demanda = np.concatenate(demanda_por_sku)
all_costo = np.repeat(inv["costo_unitario"].to_numpy(), n_days)
all_precio = np.repeat(inv["precio_unitario"].to_numpy(), n_days)
df = pd.DataFrame({
    "sku": all_skus,
    "fecha": all_fechas,
    "unidades_vendidas": all_demanda,
    "costo_unitario": all_costo,
    "precio_unitario": all_precio,
})
df["ingreso"] = (df["unidades_vendidas"] * df["precio_unitario"]).round(2)
df["costo_total"] = (df["unidades_vendidas"] * df["costo_unitario"]).round(2)
df.to_csv(OUT_DIR / "demanda_diaria.csv", index=False)

inv.to_csv(OUT_DIR / "inventario_actual.csv", index=False)

print(f"Generadas {len(df)} filas de demanda diaria para {N_SKUS} SKUs")
print(inv["categoria"].value_counts())
print(inv["segmento_demanda"].value_counts())
