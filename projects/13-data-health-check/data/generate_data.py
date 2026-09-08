"""
Simula una base de datos relacional de ventas (clientes, productos,
calendario, facturas) con problemas de calidad inyectados a propósito:
nulos en campos obligatorios, duplicados exactos y "suaves", mayúsculas/
minúsculas inconsistentes, formatos de fecha y moneda mixtos, referencias
rotas entre tablas (integridad referencial) y columnas huérfanas que nunca
se llenan. El objetivo es un dataset con un health score compuesto
alrededor de 70/100 -- ni un caso perfecto de juguete, ni un caos total,
el punto medio real donde vive la mayoría de las bases operativas de una
PyME. `run_analysis.py` audita estas 4 tablas sin conocer de antemano
dónde están los problemas.

Genera:
  data/clientes.csv    -- catálogo de clientes
  data/productos.csv   -- catálogo de productos
  data/calendario.csv  -- dimensión de fechas
  data/facturas.csv    -- hechos de facturación (una fila por línea de factura)
"""

import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(1301)
ROOT = Path(__file__).parent

# ============================================================================
# Catálogos canónicos (la "forma correcta" que las reglas de validación
# esperan encontrar)
# ============================================================================
CIUDADES_CANON = ["Ciudad de México", "Guadalajara", "Monterrey", "Puebla", "Tijuana",
                   "Querétaro", "León", "Mérida", "Toluca", "Cancún"]
SEGMENTOS_CANON = ["Premium", "Estándar", "Básico"]
CATEGORIAS_CANON = ["Electrónica", "Ropa", "Hogar", "Alimentos", "Juguetes", "Deportes", "Belleza", "Papelería"]
MONEDAS_CANON = ["MXN", "USD"]
CANALES_CANON = ["Tienda física", "E-commerce", "Marketplace", "Teléfono"]
MESES_CANON = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS_CANON = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

NOMBRES = ["María", "José", "Juan", "Ana", "Luis", "Laura", "Carlos", "Sofía", "Miguel", "Valeria",
           "Jorge", "Daniela", "Fernando", "Paola", "Ricardo", "Gabriela", "Alejandro", "Andrea",
           "Diego", "Camila", "Roberto", "Fernanda", "Eduardo", "Mariana", "Sergio", "Ximena",
           "Raúl", "Patricia", "Arturo", "Verónica"]
APELLIDOS = ["García", "Martínez", "López", "Hernández", "González", "Pérez", "Sánchez", "Ramírez",
             "Torres", "Flores", "Rivera", "Gómez", "Díaz", "Cruz", "Morales", "Reyes", "Ortiz",
             "Gutiérrez", "Chávez", "Ramos", "Vázquez", "Castillo", "Jiménez", "Mendoza", "Silva",
             "Romero", "Aguilar", "Medina", "Herrera", "Delgado"]
DOMINIOS_EMAIL = ["gmail.com", "hotmail.com", "yahoo.com.mx", "outlook.com"]

CATALOGO_PRODUCTOS = {
    "Electrónica": ["Audífonos inalámbricos", "Cargador rápido USB-C", "Bocina Bluetooth", "Smartwatch deportivo",
                     "Cable HDMI 2m", "Power bank 10000mAh", "Mouse inalámbrico", "Teclado mecánico"],
    "Ropa": ["Playera de algodón", "Sudadera con capucha", "Pantalón deportivo", "Chamarra impermeable",
             "Camisa formal", "Vestido casual", "Shorts deportivos", "Chaleco acolchado"],
    "Hogar": ["Set de sábanas", "Lámpara de mesa", "Organizador plástico", "Juego de toallas",
              "Cortina blackout", "Tapete decorativo", "Set de ollas", "Difusor de aromas"],
    "Alimentos": ["Café molido 500g", "Pasta integral", "Aceite de oliva 1L", "Miel orgánica",
                  "Cereal integral", "Snack proteico", "Té orgánico caja", "Salsa picante"],
    "Juguetes": ["Set de bloques", "Muñeca articulada", "Pista de autos", "Rompecabezas 500 piezas",
                 "Peluche grande", "Juego de mesa familiar", "Dron mini", "Kit de ciencia"],
    "Deportes": ["Balón de fútbol", "Mancuernas 5kg", "Tapete de yoga", "Bicicleta rodante",
                 "Guantes de box", "Cuerda para saltar", "Banda de resistencia", "Botella deportiva"],
    "Belleza": ["Crema hidratante", "Shampoo reparador", "Set de brochas", "Perfume 100ml",
                "Protector solar", "Mascarilla facial", "Esmalte de uñas", "Kit de manicure"],
    "Papelería": ["Cuaderno profesional", "Set de plumas", "Mochila escolar", "Calculadora científica",
                  "Marcadores de colores", "Agenda 2025", "Folder tamaño carta", "Grapadora"],
}
RANGO_PRECIO = {"Electrónica": (250, 3500), "Ropa": (150, 1200), "Hogar": (100, 1800),
                 "Alimentos": (40, 450), "Juguetes": (120, 1500), "Deportes": (150, 2500),
                 "Belleza": (80, 900), "Papelería": (30, 600)}


def dirty_case(s, rng, p=0.5):
    """Con probabilidad p, regresa una variante de mayúsculas/minúsculas
    inconsistente en vez del string canónico -- el error de captura manual
    más común en catálogos alimentados por distintas personas/sistemas."""
    if rng.random() > p:
        return s
    variant = rng.choice(["upper", "lower", "pad"])
    if variant == "upper":
        return s.upper()
    if variant == "lower":
        return s.lower()
    return f" {s} "  # espacios extra al capturar


def dirty_currency(value):
    """Formatea un número como texto de moneda con '$' y comas de miles --
    típico de un export de Excel/ERP que no separó formato de dato."""
    return f"${value:,.2f}"


def mixed_date(d, rng):
    """Regresa la fecha en uno de tres formatos distintos -- el mismo tipo
    de inconsistencia que aparece cuando ventas captura en un formato y el
    ERP exporta en otro."""
    fmt = rng.choice(["iso", "dmy", "mdy"], p=[0.72, 0.16, 0.12])
    if fmt == "iso":
        return d.strftime("%Y-%m-%d")
    if fmt == "dmy":
        return d.strftime("%d/%m/%Y")
    return d.strftime("%m/%d/%Y")


def inject_nulls(series, rate, rng):
    s = series.copy()
    idx = s.sample(frac=rate, random_state=rng.integers(0, 1_000_000)).index
    s.loc[idx] = np.nan
    return s


# ============================================================================
# 1) CLIENTES
# ============================================================================
N_CLIENTES = 500
cliente_ids = [f"CLI-{i:05d}" for i in range(1, N_CLIENTES + 1)]
nombres = [f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}" for _ in range(N_CLIENTES)]
ciudades_limpias = [rng.choice(CIUDADES_CANON) for _ in range(N_CLIENTES)]
segmentos_limpios = [rng.choice(SEGMENTOS_CANON, p=[0.2, 0.5, 0.3]) for _ in range(N_CLIENTES)]
fechas_alta = pd.to_datetime(rng.integers(pd.Timestamp("2019-01-01").value // 10**9,
                                           pd.Timestamp("2025-08-01").value // 10**9,
                                           N_CLIENTES), unit="s")

clientes = pd.DataFrame({
    "cliente_id": cliente_ids,
    "nombre_completo": nombres,
    "email": [
        f"{n.split()[0].lower()}.{n.split()[1].lower()}{rng.integers(1, 999)}@{rng.choice(DOMINIOS_EMAIL)}"
        for n in nombres
    ],
    "telefono": [f"55-{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}" for _ in range(N_CLIENTES)],
    "ciudad": [dirty_case(c, rng, p=0.22) for c in ciudades_limpias],
    "segmento": [dirty_case(s, rng, p=0.15) for s in segmentos_limpios],
    "fecha_alta": [mixed_date(f, rng) for f in fechas_alta],
    "campo_legacy_crm_id": np.nan,  # columna heredada del CRM anterior -- nunca se migró, nadie la usa
})

# -- nulos en campos obligatorios --
clientes["email"] = inject_nulls(clientes["email"], 0.07, rng)
clientes["telefono"] = inject_nulls(clientes["telefono"], 0.06, rng)

# -- emails con formato inválido (de los que sí quedaron no-nulos) --
idx_bad_email = clientes[clientes["email"].notna()].sample(frac=0.045, random_state=11).index
for i in idx_bad_email:
    e = clientes.loc[i, "email"]
    kind = rng.choice(["sin_arroba", "sin_dominio", "espacios"])
    if kind == "sin_arroba":
        clientes.loc[i, "email"] = e.replace("@", "_")
    elif kind == "sin_dominio":
        clientes.loc[i, "email"] = e.split("@")[0] + "@"
    else:
        clientes.loc[i, "email"] = " " + e + " "

# -- espacios/dobles espacios al capturar el nombre --
idx_ws = clientes.sample(frac=0.05, random_state=12).index
clientes.loc[idx_ws, "nombre_completo"] = clientes.loc[idx_ws, "nombre_completo"].apply(
    lambda n: f"  {n}  ".replace(" ", "  ", 1)
)

# -- duplicados exactos (mismo cliente_id capturado dos veces, p.ej. por una recarga fallida) --
dup_exactos = clientes.sample(n=14, random_state=13)
# -- duplicados "suaves": mismo cliente, cliente_id nuevo (alta duplicada por error de captura) --
dup_suaves = clientes.sample(n=10, random_state=14).copy()
dup_suaves["cliente_id"] = [f"CLI-{i:05d}" for i in range(N_CLIENTES + 1, N_CLIENTES + 1 + len(dup_suaves))]

clientes = pd.concat([clientes, dup_exactos, dup_suaves], ignore_index=True)
clientes = clientes.sample(frac=1, random_state=15).reset_index(drop=True)  # desordenar
clientes.to_csv(ROOT / "clientes.csv", index=False)

# ============================================================================
# 2) PRODUCTOS
# ============================================================================
skus, nombres_prod, categorias_prod, precios = [], [], [], []
i = 1
for cat, productos in CATALOGO_PRODUCTOS.items():
    lo, hi = RANGO_PRECIO[cat]
    for _ in range(19):  # ~19 por categoría * 8 categorías = 152
        skus.append(f"SKU-{i:05d}")
        nombres_prod.append(f"{rng.choice(productos)} {rng.choice(['', 'Pro', 'Plus', 'Classic', 'Mini', ''])}".strip())
        categorias_prod.append(cat)
        precios.append(round(rng.uniform(lo, hi), 2))
        i += 1

productos = pd.DataFrame({
    "sku": skus,
    "nombre_producto": nombres_prod,
    "categoria": [dirty_case(c, rng, p=0.18) for c in categorias_prod],
    "precio_unitario": precios,
    "costo_unitario": [round(p * rng.uniform(0.45, 0.7), 2) for p in precios],
    "unidad_medida": ["kg" if c == "Alimentos" and rng.random() < 0.3 else "pieza" for c in categorias_prod],
    "activo": rng.choice([True, True, True, False], size=len(skus)),
    "campo_obsoleto_bodega_2019": np.nan,  # de cuando había 2 bodegas -- ya no aplica, nunca se limpió del esquema
})
precio_limpio_por_sku = dict(zip(skus, precios))  # precio numérico real, capturado antes de ensuciar la columna

# -- nulos --
productos["precio_unitario"] = inject_nulls(productos["precio_unitario"], 0.05, rng)
productos["categoria"] = inject_nulls(productos["categoria"], 0.04, rng)

# -- precio como texto de moneda ("$1,234.50") en vez de número --
productos["precio_unitario"] = productos["precio_unitario"].astype(object)
idx_currency = productos[productos["precio_unitario"].notna()].sample(frac=0.09, random_state=21).index
productos.loc[idx_currency, "precio_unitario"] = productos.loc[idx_currency, "precio_unitario"].apply(
    lambda v: dirty_currency(v)
)

# -- precios inválidos (negativos o cero -- típico error de captura con signo/decimal mal puesto) --
idx_bad_price = productos[productos["precio_unitario"].apply(lambda v: isinstance(v, float) and not pd.isna(v))].sample(
    frac=0.03, random_state=22
).index
productos.loc[idx_bad_price, "precio_unitario"] = productos.loc[idx_bad_price, "precio_unitario"].apply(
    lambda v: round(-abs(v), 2) if rng.random() < 0.6 else 0.0
)

# -- espacios extra en el nombre --
idx_ws2 = productos.sample(frac=0.04, random_state=23).index
productos.loc[idx_ws2, "nombre_producto"] = " " + productos.loc[idx_ws2, "nombre_producto"] + " "

# -- SKUs duplicados con atributos distintos: "deriva" de maestro de producto
# (alguien recapturó el mismo SKU con otro nombre/precio en vez de editar el original) --
dup_sku_idx = productos.sample(n=8, random_state=24).index
dup_sku = productos.loc[dup_sku_idx].copy()
dup_sku["precio_unitario"] = dup_sku["precio_unitario"].apply(
    lambda v: round(float(str(v).replace("$", "").replace(",", "")) * rng.uniform(0.8, 1.25), 2)
    if not pd.isna(v) else v
)
dup_sku["nombre_producto"] = dup_sku["nombre_producto"] + " (recapturado)"

productos = pd.concat([productos, dup_sku], ignore_index=True)
productos = productos.sample(frac=1, random_state=25).reset_index(drop=True)
productos.to_csv(ROOT / "productos.csv", index=False)

productos_validos = productos[
    productos["sku"].notna() & ~productos["sku"].duplicated(keep=False)
].drop_duplicates(subset="sku")

# ============================================================================
# 3) CALENDARIO
# ============================================================================
fechas_completas = pd.date_range("2024-01-01", "2025-12-31", freq="D")
fechas_gap = pd.Series(fechas_completas).drop(
    pd.Series(fechas_completas).sample(n=9, random_state=31).index
).reset_index(drop=True)

calendario = pd.DataFrame({
    "fecha": fechas_gap.dt.strftime("%Y-%m-%d"),
    "anio": fechas_gap.dt.year,
    "mes": fechas_gap.dt.month,
    "nombre_mes": [dirty_case(MESES_CANON[m - 1], rng, p=0.06) for m in fechas_gap.dt.month],
    "trimestre": "Q" + fechas_gap.dt.quarter.astype(str),
    "dia_semana": [dirty_case(DIAS_CANON[d], rng, p=0.06) for d in fechas_gap.dt.dayofweek],
    "es_fin_de_semana": fechas_gap.dt.dayofweek >= 5,
    "es_feriado": np.nan,  # se planeó poblar con el calendario oficial de feriados MX y nunca se hizo
})

dup_fechas = calendario.sample(n=6, random_state=32)
calendario = pd.concat([calendario, dup_fechas], ignore_index=True)
calendario = calendario.sample(frac=1, random_state=33).reset_index(drop=True)
calendario.to_csv(ROOT / "calendario.csv", index=False)

fechas_validas = pd.to_datetime(pd.Series(fechas_completas).astype(str))

# ============================================================================
# 4) FACTURAS (hechos -- una fila por línea de factura)
# ============================================================================
N_FACTURAS = 3500
clientes_validos = clientes[clientes["cliente_id"].notna()]["cliente_id"].unique()
skus_validos = productos_validos["sku"].values

sample_fechas = pd.Series(fechas_completas).sample(n=N_FACTURAS, replace=True, random_state=41).reset_index(drop=True)
sample_clientes = rng.choice(clientes_validos, size=N_FACTURAS)
sample_skus = rng.choice(skus_validos, size=N_FACTURAS)
cantidades = rng.integers(1, 8, size=N_FACTURAS)
monedas = rng.choice(MONEDAS_CANON, size=N_FACTURAS, p=[0.88, 0.12])
canales = rng.choice(CANALES_CANON, size=N_FACTURAS, p=[0.4, 0.35, 0.2, 0.05])

precios_unitarios = np.array([precio_limpio_por_sku[s] * rng.uniform(0.97, 1.05) for s in sample_skus]).round(2)
totales = (cantidades * precios_unitarios).round(2)

facturas = pd.DataFrame({
    "factura_id": [f"FAC-{i:06d}" for i in range(1, N_FACTURAS + 1)],
    "fecha": [mixed_date(f, rng) for f in sample_fechas],
    "cliente_id": sample_clientes,
    "sku": sample_skus,
    "cantidad": cantidades,
    "precio_unitario": precios_unitarios,
    "moneda": [dirty_case(m, rng, p=0.12) for m in monedas],
    "total": totales,
    "canal_venta": canales,
})

# -- integridad referencial rota: cliente_id / sku que ya no existen en el catálogo
# (cliente dado de baja, SKU descontinuado, pero la venta histórica se quedó igual) --
idx_bad_cliente = facturas.sample(frac=0.045, random_state=42).index
facturas.loc[idx_bad_cliente, "cliente_id"] = [f"CLI-{rng.integers(90000, 99999)}" for _ in idx_bad_cliente]

idx_bad_sku = facturas.sample(frac=0.035, random_state=43).index
facturas.loc[idx_bad_sku, "sku"] = [f"SKU-{rng.integers(90000, 99999)}" for _ in idx_bad_sku]

# -- nulos --
facturas["cliente_id"] = inject_nulls(facturas["cliente_id"], 0.035, rng)
facturas["total"] = inject_nulls(facturas["total"], 0.025, rng)

# -- cantidades inválidas (0 o negativas -- típico de una nota de crédito mal
# capturada como venta normal en vez de con su propio tipo de movimiento) --
idx_bad_qty = facturas.sample(frac=0.025, random_state=44).index
facturas.loc[idx_bad_qty, "cantidad"] = -rng.integers(1, 5, size=len(idx_bad_qty))

# -- total que no cuadra con cantidad * precio_unitario (override manual sin
# recalcular -- p.ej. se aplicó un descuento en el sistema y no se reflejó) --
idx_bad_total = facturas[facturas["total"].notna()].sample(frac=0.07, random_state=45).index
facturas.loc[idx_bad_total, "total"] = (facturas.loc[idx_bad_total, "total"] * rng.uniform(0.5, 0.85, size=len(idx_bad_total))).round(2)

# -- precio_unitario como texto de moneda --
idx_currency2 = facturas.sample(frac=0.05, random_state=46).index
facturas["precio_unitario"] = facturas["precio_unitario"].astype(object)
facturas.loc[idx_currency2, "precio_unitario"] = facturas.loc[idx_currency2, "precio_unitario"].apply(dirty_currency)

# -- duplicados exactos (doble captura de la misma línea de factura) --
dup_facturas = facturas.sample(n=95, random_state=47)
facturas = pd.concat([facturas, dup_facturas], ignore_index=True)
facturas = facturas.sample(frac=1, random_state=48).reset_index(drop=True)
facturas.to_csv(ROOT / "facturas.csv", index=False)

print(f"clientes.csv   -> {len(clientes):,} filas")
print(f"productos.csv  -> {len(productos):,} filas")
print(f"calendario.csv -> {len(calendario):,} filas")
print(f"facturas.csv   -> {len(facturas):,} filas")
print("OK -> data/clientes.csv, data/productos.csv, data/calendario.csv, data/facturas.csv")
