"""Genera seeds/pos/pedido_linea.csv (bronze.pedido_linea del diseño original).

Lee cliente_id de seeds/crm/crm_cliente.csv, sku/precio de seeds/erp/producto.csv
y vendedor_id de seeds/crm/crm_vendedor.csv — los tres los escribe antes
generate_bronze.py, que es el punto de entrada normal (llama a generar() al final).
También se puede correr solo si esos tres seeds ya existen.

Reproducible: semilla fija, sin dependencias más allá de la librería estándar.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
FECHA_INICIO = date(2025, 1, 1)
FECHA_FIN = date(2026, 9, 17)  # un día antes de la "fecha de referencia" del proyecto

CANALES_SIN_VENDEDOR = ["E-commerce", "Marketplace"]

HERE = Path(__file__).resolve().parent
SEEDS_DIR = HERE.parent
CLIENTES_CSV = SEEDS_DIR / "crm" / "crm_cliente.csv"
PRODUCTOS_CSV = SEEDS_DIR / "erp" / "producto.csv"
VENDEDORES_CSV = SEEDS_DIR / "crm" / "crm_vendedor.csv"
OUT_CSV = SEEDS_DIR / "pos" / "pedido_linea.csv"


def cargar_clientes():
    with open(CLIENTES_CSV, newline="", encoding="utf-8") as f:
        return [row["cliente_id"] for row in csv.DictReader(f) if row.get("cliente_id")]


def limpiar_precio(raw):
    return float(raw.replace("$", "").replace(",", "").strip())


def cargar_productos_activos():
    # producto.csv es la fuente sucia de projects/13 — trae precios inválidos
    # a propósito (negativos, "$1,234.50" como texto). El canal de ventas
    # gestionado (este generador) es un sistema moderno: valida el precio del
    # catálogo antes de vender con él, igual que cualquier POS real
    # rechazaría un precio negativo al capturar la venta.
    productos = []
    for row in csv.DictReader(open(PRODUCTOS_CSV, newline="", encoding="utf-8")):
        if row.get("activo", "").strip() != "True":
            continue
        try:
            precio = limpiar_precio(row["precio_unitario"])
        except (ValueError, AttributeError):
            continue
        if precio <= 0:
            continue
        productos.append((row["sku"], precio))
    return productos


def cargar_vendedores():
    with open(VENDEDORES_CSV, newline="", encoding="utf-8") as f:
        return [row["vendedor_id"] for row in csv.DictReader(f)]


def elegir_canal_y_vendedor(rng, vendedores):
    # ~65% de las líneas pasan por un vendedor del equipo comercial;
    # el resto es autoservicio (e-commerce / marketplace), sin vendedor.
    if rng.random() < 0.65:
        return "Equipo comercial", rng.choice(vendedores)
    return rng.choice(CANALES_SIN_VENDEDOR), None


def generar():
    rng = random.Random(SEED)
    clientes = cargar_clientes()
    productos = cargar_productos_activos()
    vendedores = cargar_vendedores()

    rows = []
    pedido_num = 0
    dia = FECHA_INICIO
    while dia <= FECHA_FIN:
        es_finde = dia.weekday() >= 5
        # menos pedidos el fin de semana; ligera tendencia de crecimiento en el tiempo
        progreso = (dia - FECHA_INICIO).days / (FECHA_FIN - FECHA_INICIO).days
        base = 14 + 10 * progreso
        pedidos_del_dia = rng.randint(int(base * 0.5), int(base)) if es_finde else rng.randint(int(base * 0.8), int(base * 1.4))

        for _ in range(pedidos_del_dia):
            pedido_num += 1
            pedido_id = f"PED-{pedido_num:06d}"
            cliente_id = rng.choice(clientes)
            canal_venta, vendedor_id = elegir_canal_y_vendedor(rng, vendedores)
            n_lineas = rng.choices([1, 2, 3, 4], weights=[55, 25, 12, 8])[0]
            skus_pedido = rng.sample(productos, k=min(n_lineas, len(productos)))
            for linea_idx, (sku, precio_catalogo) in enumerate(skus_pedido, start=1):
                cantidad = rng.choices([1, 2, 3, 4, 5, 6], weights=[40, 25, 15, 10, 6, 4])[0]
                # deriva de precio de catálogo con variación realista +/- y descuento ocasional
                variacion = rng.uniform(-0.05, 0.08)
                precio_unitario = round(precio_catalogo * (1 + variacion), 2)
                descuento_pct = rng.choices([0, 0.05, 0.10, 0.15], weights=[70, 15, 10, 5])[0]
                rows.append({
                    "pedido_id": pedido_id,
                    "linea_id": f"{pedido_id}-{linea_idx}",
                    "fecha": dia.isoformat(),
                    "cliente_id": cliente_id,
                    "vendedor_id": vendedor_id or "",
                    "canal_venta": canal_venta,
                    "sku": sku,
                    "cantidad": cantidad,
                    "precio_unitario": precio_unitario,
                    "descuento_pct": descuento_pct,
                })
        dia += timedelta(days=1)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"pedido_linea: {len(rows)} filas")


if __name__ == "__main__":
    generar()
