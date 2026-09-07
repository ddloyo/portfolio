"""
Simula la cartera comercial completa detrás del reporte ejecutivo mensual:
200 clientes repartidos en 5 regiones y 4 perfiles de compra (volumen x
frecuencia), comprando de forma dispersa entre 8 subcategorías de producto --
no todos los clientes compran todo.

La tendencia mensual ya no es un parámetro fijo por categoría (como en la v1):
se define a nivel subcategoría-cliente -- la base de la subcategoría más el
ruido idiosincrático de cada cliente -- y el ingreso de cada categoría emerge
de agregar hacia arriba esas ~200 x 3-4 series individuales, igual que en un
negocio real. run_analysis.py recalcula tendencia y volatilidad a partir de
estos datos agregados; no las lee de aquí.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(101)

N_MESES = 20
N_CLIENTES = 200

# ---- estructura comercial: 5 regiones -------------------------------------
REGIONES = {
    "Centro": 0.30,
    "Norte": 0.38,
    "Occidente": 0.15,
    "Sureste": 0.12,
    "Bajío": 0.05,
}

# ---- 4 perfiles de cliente: volumen (tamaño de ticket) x frecuencia -------
# "n_subcats" es cuántas de las 8 subcategorías tiene activas ese cliente --
# el mecanismo que hace que no todos los clientes compren todos los productos.
PERFILES = {
    "VIP (alto volumen / alta frecuencia)": {
        "peso": 0.12, "prob_compra": 0.90, "ticket_mult": (1.6, 2.2), "n_subcats": (5, 8),
    },
    "Recurrente (bajo volumen / alta frecuencia)": {
        "peso": 0.33, "prob_compra": 0.75, "ticket_mult": (0.5, 0.9), "n_subcats": (4, 6),
    },
    "Ocasional (alto volumen / baja frecuencia)": {
        "peso": 0.20, "prob_compra": 0.30, "ticket_mult": (1.4, 2.0), "n_subcats": (2, 4),
    },
    "Esporádico (bajo volumen / baja frecuencia)": {
        "peso": 0.35, "prob_compra": 0.15, "ticket_mult": (0.4, 0.8), "n_subcats": (1, 3),
    },
}

# ---- 4 categorías -> 1 a 3 subcategorías cada una (8 en total) -----------
# "tendencia_base" es el punto de partida por subcategoría; cada cliente
# activo en esa subcategoría se desvía de ahí con su propio ruido (ver abajo).
SUBCATEGORIAS = {
    "Línea Premium": {
        "tendencia_base": 0.010,
        "subcats": {"Premium Hogar": 550, "Premium Oficina": 480, "Premium Exportación": 600},
    },
    "Línea Estándar": {
        "tendencia_base": 0.001,
        "subcats": {"Estándar Retail": 420, "Estándar Mayoreo": 500},
    },
    "Línea Económica": {
        "tendencia_base": -0.0015,
        "subcats": {"Económica Básica": 300, "Económica Promocional": 250},
    },
    "Servicios postventa": {
        "tendencia_base": 0.018,
        "subcats": {"Soporte y Mantenimiento": 150},
    },
}

SUBCAT_TO_CAT = {sc: cat for cat, cfg in SUBCATEGORIAS.items() for sc in cfg["subcats"]}
ALL_SUBCATS = list(SUBCAT_TO_CAT.keys())

# Preferencia de cada perfil por línea de producto: los de ticket alto
# (VIP / Ocasional) sesgan hacia Premium y Postventa; los de ticket bajo
# (Recurrente / Esporádico) sesgan hacia Estándar/Económica -- una selección
# uniforme haría que un cliente de bajo ticket comprara Premium tan seguido
# como uno VIP, lo cual no pasa en una cartera real.
PREFERENCIA_LINEA = {
    "VIP (alto volumen / alta frecuencia)": {"Línea Premium": 3, "Línea Estándar": 1, "Línea Económica": 0.5, "Servicios postventa": 2},
    "Recurrente (bajo volumen / alta frecuencia)": {"Línea Premium": 0.5, "Línea Estándar": 2, "Línea Económica": 2, "Servicios postventa": 1},
    "Ocasional (alto volumen / baja frecuencia)": {"Línea Premium": 2, "Línea Estándar": 2, "Línea Económica": 0.5, "Servicios postventa": 1},
    "Esporádico (bajo volumen / baja frecuencia)": {"Línea Premium": 0.5, "Línea Estándar": 1, "Línea Económica": 3, "Servicios postventa": 0.5},
}


def subcat_weights_for(perfil):
    prefs = PREFERENCIA_LINEA[perfil]
    pesos = np.array([prefs[SUBCAT_TO_CAT[sc]] for sc in ALL_SUBCATS], dtype=float)
    return pesos / pesos.sum()


months = pd.date_range("2025-01-01", periods=N_MESES, freq="MS").strftime("%Y-%m")

# ---- cartera de clientes: región y perfil asignados de forma independiente,
# cada uno según su propia distribución de pesos --------------------------
region_names = list(REGIONES.keys())
perfil_names = list(PERFILES.keys())

clientes = pd.DataFrame({
    "cliente_id": [f"CLI-{i + 1:03d}" for i in range(N_CLIENTES)],
    "region": np.random.choice(region_names, size=N_CLIENTES, p=list(REGIONES.values())),
    "perfil": np.random.choice(perfil_names, size=N_CLIENTES, p=[PERFILES[p]["peso"] for p in perfil_names]),
})

rows = []
for cli in clientes.itertuples():
    perfil_cfg = PERFILES[cli.perfil]
    n_lo, n_hi = perfil_cfg["n_subcats"]
    n_activas = np.random.randint(n_lo, n_hi + 1)
    subcats_activas = np.random.choice(
        ALL_SUBCATS, size=min(n_activas, len(ALL_SUBCATS)), replace=False, p=subcat_weights_for(cli.perfil)
    )
    ticket_mult = np.random.uniform(*perfil_cfg["ticket_mult"])
    prob_compra = perfil_cfg["prob_compra"]

    for subcat in subcats_activas:
        categoria = SUBCAT_TO_CAT[subcat]
        tendencia_base = SUBCATEGORIAS[categoria]["tendencia_base"]
        # Tendencia idiosincrática: base de la subcategoría + ruido propio del
        # cliente -- esto es "bajar la tendencia a la granularidad
        # subcategoría-cliente" en vez de un solo número por categoría.
        tendencia_ic = tendencia_base + np.random.normal(0, 0.005)
        nivel = SUBCATEGORIAS[categoria]["subcats"][subcat] * ticket_mult

        for i, mes in enumerate(months):
            # El nivel evoluciona cada mes exista o no compra, para que la
            # tendencia no se distorsione por los meses sin transacción.
            nivel = nivel * (1 + tendencia_ic)
            if np.random.random() > prob_compra:
                continue  # este cliente no compró esta subcategoría este mes
            ruido = np.random.normal(0, 0.12)
            valor = max(nivel * (1 + ruido), 0)
            # Caída deliberada y aislada: un cliente grande de Estándar
            # Mayoreo pausa pedidos el último mes -- el patrón que el reporte
            # ejecutivo está diseñado para detectar y explicar.
            if subcat == "Estándar Mayoreo" and i == len(months) - 1:
                valor *= 0.65
            rows.append({
                "mes": mes, "region": cli.region, "cliente_id": cli.cliente_id, "perfil": cli.perfil,
                "categoria": categoria, "subcategoria": subcat, "ingreso_mxn": round(valor, 2),
            })

df = pd.DataFrame(rows)
out = Path(__file__).parent / "transacciones.csv"
df.to_csv(out, index=False)

print(f"Generadas {len(df):,} transacciones -> {out}")
print(f"Clientes: {N_CLIENTES} | Regiones: {len(REGIONES)} | Perfiles: {len(PERFILES)} "
      f"| Categorías: {len(SUBCATEGORIAS)} | Subcategorías: {len(ALL_SUBCATS)}")
