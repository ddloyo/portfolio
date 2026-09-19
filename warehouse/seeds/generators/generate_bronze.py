"""Genera los seeds de bronze que no existen tal cual en projects/*/data/.

Migración 1:1 del DDL original de bronze (21 tablas; el archivo ya se eliminó,
ver database/LEGACY_TABLES.md). De esas:
  - 4 se reusan sin tocar de projects/11 y projects/13 (calendario y las 3
    sucursales): ya están en seeds/, movidas y renombradas.
  - 3 se AUMENTAN a partir de projects/13 (crm_cliente, producto,
    factura_linea): se conservan TODAS las columnas y filas originales, en el
    mismo orden y con su suciedad intacta, y se agregan las columnas que el
    DDL de bronze define y el CSV original no tenía.
  - 14 se generan (catálogos de equipo/vendedor, oportunidades, pagos,
    suscripción, soporte, actividad, cancelaciones, marketing, NPS, KPIs
    manuales, inventario, pedido_linea).

Además genera scorecard/kpi_meta.csv, que NO está en el DDL de bronze (ver
database/LEGACY_TABLES.md).

Reproducible: cada tabla tiene su propio generador aleatorio derivado de un
texto fijo (no de un único stream compartido), así que cambiar una tabla no
mueve los datos de las demás. Solo usa la librería estándar.

Uso (desde warehouse/):
    python3 seeds/generators/generate_bronze.py
"""
import csv
import random
import re
from collections import OrderedDict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = HERE.parent
REPO = SEEDS.parent.parent
P13 = REPO / "projects" / "13-data-health-check" / "data"
P01 = REPO / "projects" / "01-sales-performance-dashboard" / "data"

FECHA_INICIO = date(2025, 1, 1)
FECHA_FIN = date(2026, 9, 17)
PRIMER_MES = (2025, 1)
ULTIMO_MES = (2026, 8)

EQUIPOS = [("EQ-01", "Centro", "CEN"), ("EQ-02", "Norte", "NOR"),
           ("EQ-03", "Occidente", "OCC"), ("EQ-04", "Sureste", "SUR")]
VENDEDORES_POR_EQUIPO = 3

REGION_POR_CIUDAD = {
    "ciudad de méxico": "Centro", "toluca": "Centro", "puebla": "Centro", "querétaro": "Centro",
    "guadalajara": "Occidente", "león": "Occidente",
    "monterrey": "Norte", "tijuana": "Norte",
    "mérida": "Sureste", "cancún": "Sureste",
}
CANALES_ADQUISICION = ["Referidos", "Google Ads", "Meta Ads", "Email", "Eventos", "Orgánico"]
PESOS_ADQUISICION = [22, 20, 16, 12, 10, 20]
CANALES_CON_GASTO = {"Referidos": 260, "Google Ads": 900, "Meta Ads": 700, "Email": 150, "Eventos": 400}

# (patrón sobre el nombre en minúsculas, subcategoría) — el primero que calce gana
SUBCATEGORIAS = [
    (r"aceite|pasta|cereal|miel|salsa", "Despensa"),
    (r"café|\bté\b", "Bebidas"),
    (r"snack", "Botanas"),
    (r"crema|protector|mascarilla", "Cuidado de la piel"),
    (r"shampoo", "Cuidado del cabello"),
    (r"esmalte|manicure|brochas", "Maquillaje y uñas"),
    (r"perfume", "Fragancias"),
    (r"banda|cuerda|tapete de yoga|guantes", "Fitness"),
    (r"balón", "Deportes de equipo"),
    (r"bicicleta", "Ciclismo"),
    (r"botella", "Accesorios deportivos"),
    (r"cortina|toallas|sábanas|tapete decorativo", "Textil de hogar"),
    (r"ollas", "Cocina"),
    (r"lámpara|organizador", "Iluminación y organización"),
    (r"audífonos", "Audio"),
    (r"mouse|teclado", "Cómputo"),
    (r"cable|power bank", "Accesorios electrónicos"),
    (r"smartwatch", "Wearables"),
    (r"juego de mesa|rompecabezas", "Juegos de mesa"),
    (r"bloques|kit de ciencia|pista", "Construcción y ciencia"),
    (r"dron", "Juguetes electrónicos"),
    (r"peluche", "Peluches"),
    (r"plumas|marcadores", "Escritura"),
    (r"grapadora|folder|calculadora", "Oficina"),
    (r"cuaderno|agenda", "Cuadernos y agendas"),
    (r"chamarra|chaleco|sudadera", "Prendas de abrigo"),
    (r"playera|vestido|camisa|pantalón|shorts", "Ropa casual"),
]


# ------------------------------------------------------------------ utilidades
def rng_for(*key):
    return random.Random("|".join(str(k) for k in key))


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"  {path.relative_to(SEEDS)}: {len(rows)} filas")


def parse_fecha(v):
    """ISO o DD/MM/AAAA (el formato de las fuentes de projects/13). None si no parsea."""
    v = (v or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    return None


def parse_money(v):
    try:
        return float((v or "").replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def meses(desde=PRIMER_MES, hasta=ULTIMO_MES):
    y, m = desde
    while (y, m) <= hasta:
        yield date(y, m, 1)
        m += 1
        if m == 13:
            y, m = y + 1, 1


def mes_txt(d):
    return d.strftime("%Y-%m")


def dia_en_mes(rng, mes_inicio, tope=FECHA_FIN):
    d = mes_inicio + timedelta(days=rng.randint(0, 27))
    return min(d, tope)


def numerar(rows, prefijo, ancho, campo):
    for i, r in enumerate(rows, start=1):
        r[campo] = f"{prefijo}{i:0{ancho}d}"
    return rows


# ---------------------------------------------------------------- CRM (catálogos)
def gen_catalogos_crm():
    write_csv(SEEDS / "crm" / "crm_equipo.csv", ["equipo_id", "nombre_equipo"],
              [{"equipo_id": eid, "nombre_equipo": nombre} for eid, nombre, _ in EQUIPOS])

    vendedores, n = [], 0
    for eid, _, prefijo in EQUIPOS:
        for i in range(1, VENDEDORES_POR_EQUIPO + 1):
            n += 1
            vendedores.append({"vendedor_id": f"VEN-{n:03d}", "codigo_vendedor": f"{prefijo}-{i:02d}", "equipo_id": eid})
    write_csv(SEEDS / "crm" / "crm_vendedor.csv", ["vendedor_id", "codigo_vendedor", "equipo_id"], vendedores)

    _, metas = read_csv(P01 / "metas_mensuales.csv")
    meta_por_equipo = {r["equipo"]: r["meta_mensual_mxn"] for r in metas}
    write_csv(SEEDS / "crm" / "crm_meta_venta.csv", ["equipo_id", "meta_mensual_mxn"],
              [{"equipo_id": eid, "meta_mensual_mxn": meta_por_equipo[nombre]} for eid, nombre, _ in EQUIPOS])
    return [v["vendedor_id"] for v in vendedores]


# ---------------------------------------------------- tablas de projects/13 aumentadas
def atributos_cliente(cliente_id):
    r = rng_for("crm_cliente", cliente_id)
    canal = r.choices(CANALES_ADQUISICION, weights=PESOS_ADQUISICION)[0]
    if r.random() < 0.35:
        tipo = r.choices(["Mensual", "Anual"], weights=[60, 40])[0]
        plan = r.choices(["Starter", "Pro", "Business"], weights=[45, 35, 20])[0]
    else:
        tipo, plan = "", ""
    return {"canal_adquisicion": canal, "tipo_contrato": tipo, "plan": plan}


def gen_crm_cliente():
    _, rows = read_csv(P13 / "clientes.csv")
    out = []
    for r in rows:
        a = atributos_cliente(r["cliente_id"])
        region = REGION_POR_CIUDAD.get(r["ciudad"].strip().lower(), "")
        out.append(OrderedDict([
            ("cliente_id", r["cliente_id"]), ("nombre_completo", r["nombre_completo"]),
            ("email", r["email"]), ("telefono", r["telefono"]), ("ciudad", r["ciudad"]),
            ("region", region), ("segmento", r["segmento"]), ("fecha_alta", r["fecha_alta"]),
            ("tipo_contrato", a["tipo_contrato"]), ("plan", a["plan"]),
            ("canal_adquisicion", a["canal_adquisicion"]),
            ("campo_legacy_crm_id", r["campo_legacy_crm_id"]),
        ]))
    write_csv(SEEDS / "crm" / "crm_cliente.csv", list(out[0].keys()), out)
    return rows


def subcategoria(nombre):
    n = (nombre or "").strip().lower()
    for patron, sub in SUBCATEGORIAS:
        if re.search(patron, n):
            return sub
    raise ValueError(f"Sin subcategoría para el producto: {nombre!r}")


def gen_producto():
    _, rows = read_csv(P13 / "productos.csv")
    out = []
    for r in rows:
        out.append(OrderedDict([
            ("sku", r["sku"]), ("nombre_producto", r["nombre_producto"]), ("categoria", r["categoria"]),
            ("subcategoria", subcategoria(r["nombre_producto"])),
            ("precio_unitario", r["precio_unitario"]), ("costo_unitario", r["costo_unitario"]),
            ("unidad_medida", r["unidad_medida"]), ("activo", r["activo"]),
            ("campo_obsoleto_bodega_2019", r["campo_obsoleto_bodega_2019"]),
        ]))
    write_csv(SEEDS / "erp" / "producto.csv", list(out[0].keys()), out)
    return rows


def gen_factura_linea():
    _, rows = read_csv(P13 / "facturas.csv")
    out = []
    for r in rows:
        f = parse_fecha(r["fecha"])
        plazo = rng_for("plazo", r["cliente_id"]).choice([15, 30, 30, 45, 60])
        venc = (f + timedelta(days=plazo)).isoformat() if f else ""
        out.append(OrderedDict([
            ("factura_id", r["factura_id"]), ("fecha", r["fecha"]), ("fecha_vencimiento", venc),
            ("cliente_id", r["cliente_id"]), ("sku", r["sku"]), ("cantidad", r["cantidad"]),
            ("precio_unitario", r["precio_unitario"]), ("moneda", r["moneda"]),
            ("total", r["total"]), ("canal_venta", r["canal_venta"]),
        ]))
    write_csv(SEEDS / "erp" / "factura_linea.csv", list(out[0].keys()), out)
    return rows


# ------------------------------------------------------------------- facturación
def gen_pago(facturas):
    vistos, pagos = set(), []
    for r in facturas:
        fid = r["factura_id"]
        if not fid or fid in vistos:
            continue
        vistos.add(fid)
        f = parse_fecha(r["fecha"])
        total = parse_money(r["total"])
        if total is None:
            cant, precio = parse_money(r["cantidad"]), parse_money(r["precio_unitario"])
            total = cant * precio if cant is not None and precio is not None else None
        if f is None or total is None or total <= 0:
            continue
        perfil = rng_for("pago_perfil", r["cliente_id"]).choices(["puntual", "lento", "moroso"], weights=[50, 35, 15])[0]
        rng = rng_for("pago", fid)
        prob_pago = {"puntual": 0.99, "lento": 0.94, "moroso": 0.75}[perfil]
        if rng.random() >= prob_pago:
            continue
        rango = {"puntual": (5, 25), "lento": (28, 65), "moroso": (55, 120)}[perfil]
        dias = rng.randint(*rango)
        metodo = rng.choices(["Transferencia", "Cheque", "Tarjeta", "Efectivo"], weights=[60, 15, 20, 5])[0]
        if rng.random() < 0.06:
            primero = round(total * 0.6, 2)
            pagos.append({"factura_id": fid, "fecha_pago": (f + timedelta(days=dias)).isoformat(),
                          "monto_pagado": f"{primero:.2f}", "metodo_pago": metodo})
            pagos.append({"factura_id": fid, "fecha_pago": (f + timedelta(days=dias + rng.randint(10, 30))).isoformat(),
                          "monto_pagado": f"{round(total - primero, 2):.2f}", "metodo_pago": metodo})
        else:
            pagos.append({"factura_id": fid, "fecha_pago": (f + timedelta(days=dias)).isoformat(),
                          "monto_pagado": f"{total:.2f}", "metodo_pago": metodo})
    numerar(pagos, "PAG-", 6, "pago_id")
    write_csv(SEEDS / "erp" / "pago.csv", ["pago_id", "factura_id", "fecha_pago", "monto_pagado", "metodo_pago"], pagos)


# ----------------------------------------- clientes con plan: cargos, soporte, uso, bajas
def gen_ciclo_clientes(clientes_rows):
    primera_alta = {}
    for r in clientes_rows:
        primera_alta.setdefault(r["cliente_id"], r["fecha_alta"])

    cargos, tickets, eventos, bajas = [], [], [], []
    ultimo = date(ULTIMO_MES[0], ULTIMO_MES[1], 1)
    for cid, alta_txt in primera_alta.items():
        a = atributos_cliente(cid)
        if not a["plan"]:
            continue
        alta = parse_fecha(alta_txt) or date(2025, 1, 1)
        inicio = max(date(alta.year, alta.month, 1), date(PRIMER_MES[0], PRIMER_MES[1], 1))
        if inicio > ultimo:
            continue
        r = rng_for("ciclo", cid)
        lista = list(meses((inicio.year, inicio.month), ULTIMO_MES))
        activos = lista
        if r.random() < 0.18 and len(lista) > 4:
            idx = r.randint(3, len(lista) - 1)
            activos = lista[:idx]
            baja = min(lista[idx] + timedelta(days=r.randint(0, 27)), FECHA_FIN)
            bajas.append({"cliente_id": cid, "fecha_cancelacion": baja.isoformat(),
                          "motivo": r.choice(["Precio", "Migró a competidor", "Cierre del negocio",
                                              "Servicio insatisfactorio", "Falta de uso"])})
        churner = len(activos) < len(lista)
        base = {"Starter": r.uniform(380, 620), "Pro": r.uniform(750, 1150), "Business": r.uniform(1500, 2600)}[a["plan"]]
        if a["tipo_contrato"] == "Anual":
            base *= 0.9
        for i, m in enumerate(activos):
            cargos.append({"cliente_id": cid, "mes": mes_txt(m),
                           "gasto_mensual_mxn": f"{base * (1 + r.uniform(-0.02, 0.02)):.2f}"})
            ultimos_dos = churner and i >= len(activos) - 2
            pesos_tickets = [40, 30, 20, 10] if ultimos_dos else [70, 20, 7, 3]
            for _ in range(r.choices([0, 1, 2, 3], weights=pesos_tickets)[0]):
                ap = dia_en_mes(r, m)
                cierre = ap + timedelta(days=r.randint(0, 7))
                tickets.append({"cliente_id": cid, "fecha_apertura": ap.isoformat(),
                                "fecha_cierre": cierre.isoformat() if cierre <= FECHA_FIN else "",
                                "categoria": r.choice(["Facturación", "Acceso", "Bug", "Consulta", "Rendimiento"])})
            n_ev = r.randint(0, 2) if ultimos_dos else r.randint(1, 5)
            for _ in range(n_ev):
                tipo = r.choices(["login", "uso_feature", "descarga_reporte", "invitacion_usuario"], weights=[50, 30, 15, 5])[0]
                puntos = {"login": 1, "uso_feature": 3, "descarga_reporte": 5, "invitacion_usuario": 8}[tipo] + r.choice([0, 0, 1])
                eventos.append({"cliente_id": cid, "fecha": dia_en_mes(r, m).isoformat(),
                                "tipo_evento": tipo, "usage_points": str(puntos)})

    write_csv(SEEDS / "erp" / "suscripcion_cargo.csv", ["cliente_id", "mes", "gasto_mensual_mxn"], cargos)
    tickets.sort(key=lambda t: (t["fecha_apertura"], t["cliente_id"]))
    numerar(tickets, "TCK-", 5, "ticket_id")
    write_csv(SEEDS / "helpdesk" / "ticket_soporte.csv",
              ["ticket_id", "cliente_id", "fecha_apertura", "fecha_cierre", "categoria"], tickets)
    eventos.sort(key=lambda e: (e["fecha"], e["cliente_id"]))
    numerar(eventos, "EVT-", 6, "evento_id")
    write_csv(SEEDS / "producto_analytics" / "evento_actividad.csv",
              ["evento_id", "cliente_id", "fecha", "tipo_evento", "usage_points"], eventos)
    write_csv(SEEDS / "crm" / "cancelacion.csv", ["cliente_id", "fecha_cancelacion", "motivo"], bajas)


# ----------------------------------------------------------------- pipeline comercial
def gen_oportunidades(vendedor_ids):
    rng = rng_for("funnel")
    eventos, opp_n = [], 0
    semana = date(2025, 1, 6)
    idx_semana = 0
    while semana <= FECHA_FIN:
        p_propuesta = 0.55 if idx_semana < 52 else 0.30  # fuga a partir de 2026
        for _ in range(rng.randint(45, 65)):
            opp_n += 1
            opp = f"OPP-{opp_n:06d}"
            vend = rng.choice(vendedor_ids)
            fecha = semana + timedelta(days=rng.randint(0, 4))
            cadena = [("lead", 1.0), ("contactado", 0.72), ("calificado", 0.55), ("propuesta", p_propuesta), ("cierre", 0.32)]
            for etapa, prob in cadena:
                if rng.random() >= prob:
                    break
                if fecha > FECHA_FIN:
                    break
                eventos.append({"oportunidad_id": opp, "etapa": etapa, "fecha_evento": fecha.isoformat(), "vendedor_id": vend})
                fecha += timedelta(days=rng.randint(0, 3))
        semana += timedelta(days=7)
        idx_semana += 1
    eventos.sort(key=lambda e: (e["fecha_evento"], e["oportunidad_id"]))
    numerar(eventos, "EVO-", 6, "evento_id")
    write_csv(SEEDS / "crm" / "crm_oportunidad_evento.csv",
              ["evento_id", "oportunidad_id", "etapa", "fecha_evento", "vendedor_id"], eventos)


# ------------------------------------------------------------ marketing, NPS, KPIs, stock
def gen_marketing_gasto():
    rows = []
    for canal, base in CANALES_CON_GASTO.items():
        rng = rng_for("marketing", canal)
        d = FECHA_INICIO
        while d <= FECHA_FIN:
            factor = 0.7 if d.weekday() >= 5 else 1.0
            rows.append({"canal": canal, "fecha": d.isoformat(),
                         "gasto_mxn": f"{base * factor * rng.uniform(0.8, 1.2):.2f}"})
            d += timedelta(days=1)
    rows.sort(key=lambda r: (r["fecha"], r["canal"]))
    write_csv(SEEDS / "ads" / "marketing_gasto.csv", ["canal", "fecha", "gasto_mxn"], rows)


def gen_encuesta_nps(clientes_rows):
    ids = list(OrderedDict.fromkeys(r["cliente_id"] for r in clientes_rows))
    rng = rng_for("nps")
    motivos = ["Tiempos de entrega", "Precio", "Soporte lento", "Calidad del producto", "Facturación"]
    rows = []
    for m in meses():
        reciente = m >= date(2026, 6, 1)
        pesos_cat = [38, 30, 32] if reciente else [48, 30, 22]
        for _ in range(rng.randint(40, 60)):
            cat = rng.choices(["promotor", "pasivo", "detractor"], weights=pesos_cat)[0]
            if cat == "promotor":
                score, motivo = rng.choice([9, 10]), ""
            elif cat == "pasivo":
                score, motivo = rng.choice([7, 8]), ""
            else:
                score = rng.choices([0, 1, 2, 3, 4, 5, 6], weights=[3, 3, 5, 8, 12, 25, 44])[0]
                pesos_m = [50, 12, 14, 14, 10] if reciente else [20, 22, 22, 20, 16]
                motivo = rng.choices(motivos, weights=pesos_m)[0]
            rows.append({"cliente_id": rng.choice(ids), "fecha": dia_en_mes(rng, m).isoformat(),
                         "score": str(score), "motivo_detractor": motivo})
    rows.sort(key=lambda r: (r["fecha"], r["cliente_id"]))
    numerar(rows, "R-", 5, "respuesta_id")
    write_csv(SEEDS / "encuestas" / "encuesta_nps.csv",
              ["respuesta_id", "cliente_id", "fecha", "score", "motivo_detractor"], rows)


def gen_kpi_manual():
    kpis = [("Satisfacción del equipo (eNPS)", "Recursos Humanos", "Dir. RH", "puntos", "False", 32, 5),
            ("SLA de soporte", "Operaciones", "Dir. Operaciones", "%", "False", 92, 3),
            ("Rotación de personal", "Recursos Humanos", "Dir. RH", "%", "True", 2.4, 0.6)]
    rows = []
    for nombre, area, resp, unidad, menor, media, desv in kpis:
        rng = rng_for("kpi", nombre)
        for m in meses():
            rows.append({"kpi": nombre, "area": area, "responsable": resp, "mes": mes_txt(m),
                         "resultado": f"{rng.gauss(media, desv / 2):.1f}", "unidad": unidad, "menor_es_mejor": menor})
    write_csv(SEEDS / "scorecard" / "kpi_captura_manual.csv",
              ["kpi", "area", "responsable", "mes", "resultado", "unidad", "menor_es_mejor"], rows)


def gen_kpi_meta():
    """Metas de planeación por KPI (insumo, no cálculo). No existía en el DDL de
    bronze: cierra el hueco de silver.fact_kpi_meta. Valores ilustrativos."""
    metas = [("Ingresos mensuales", "2000000"), ("Nuevos clientes", "10"), ("NPS", "40"),
             ("Satisfacción del equipo (eNPS)", "35"), ("SLA de soporte", "95"), ("Rotación de personal", "2.0")]
    write_csv(SEEDS / "scorecard" / "kpi_meta.csv", ["kpi", "meta"], [{"kpi": k, "meta": m} for k, m in metas])


def gen_inventario_snapshot(productos_rows):
    skus = [s for s in OrderedDict.fromkeys(r["sku"] for r in productos_rows) if s]
    fechas = [FECHA_FIN - timedelta(days=7 * i) for i in (3, 2, 1, 0)]
    rows = []
    for sku in skus:
        rng = rng_for("inventario", sku)
        stock, lead = rng.randint(50, 900), rng.choice([7, 14, 21, 30, 45])
        for f in fechas:
            stock = max(0, stock + rng.randint(-60, 60))
            rows.append({"sku": sku, "fecha_snapshot": f.isoformat(), "stock_actual": str(stock), "lead_time_dias": str(lead)})
    write_csv(SEEDS / "wms" / "inventario_snapshot.csv", ["sku", "fecha_snapshot", "stock_actual", "lead_time_dias"], rows)


def main():
    print("Bronze: catálogos CRM")
    vendedor_ids = gen_catalogos_crm()
    print("Bronze: tablas aumentadas de projects/13")
    clientes = gen_crm_cliente()
    productos = gen_producto()
    facturas = gen_factura_linea()
    print("Bronze: facturación y ciclo de clientes con plan")
    gen_pago(facturas)
    gen_ciclo_clientes(clientes)
    print("Bronze: pipeline comercial, marketing, NPS, KPIs, inventario")
    gen_oportunidades(vendedor_ids)
    gen_marketing_gasto()
    gen_encuesta_nps(clientes)
    gen_kpi_manual()
    gen_kpi_meta()
    gen_inventario_snapshot(productos)
    print("Bronze: pedido_linea")
    from generate_pedido_linea import generar
    generar()


if __name__ == "__main__":
    main()
