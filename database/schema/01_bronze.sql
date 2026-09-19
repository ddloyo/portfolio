-- =============================================================================
-- BRONZE LAYER — sistemas operativos de la empresa (raw landing zone)
-- =============================================================================
-- Perfil de negocio asumido (documentado aquí porque no es derivable del
-- código, es una decisión de diseño): una PyME que vende producto físico por
-- equipos comerciales y por sucursal/e-commerce, y que además tiene una
-- cartera de clientes con plan de servicio recurrente (mensual/anual) — así
-- conviven en un solo negocio la venta transaccional y el negocio de suscripción
-- con churn.
--
-- Tipos permisivos (TEXT) en todo bronze: es zona de aterrizaje, nunca debe
-- fallar por un formato inesperado. Tres tablas conservan la suciedad real
-- que los proyectos 11 y 13 ya modelaban (fechas mixtas, catálogos sin
-- normalizar, nulos, referencias rotas) porque ESA es la fuente real de la
-- empresa — de ahí es de donde salen los issues que projects/13 audita y que
-- projects/11 consolida.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS bronze;

-- Columnas de linaje repetidas en cada tabla:
--   _source_system TEXT   sistema origen (crm | pos | erp_facturacion | ...)
--   _batch_id      UUID   corrida de ingesta
--   _loaded_at     TIMESTAMPTZ

-- -----------------------------------------------------------------------------
-- CRM — gestión de clientes, equipo comercial y oportunidades
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.crm_cliente (
    cliente_id                 TEXT,
    nombre_completo            TEXT,
    email                      TEXT,
    telefono                   TEXT,
    ciudad                     TEXT,
    region                     TEXT,   -- territorio comercial asignado por el CRM
    segmento                   TEXT,   -- perfil comercial del cliente
    fecha_alta                 TEXT,   -- ISO / DD-MM-YYYY / MM-DD-YYYY mezclados (fuente real, sin ETL previo)
    tipo_contrato              TEXT,   -- Mensual / Anual / NULL (clientes transaccionales sin contrato)
    plan                       TEXT,   -- Starter / Pro / NULL
    canal_adquisicion          TEXT,   -- Referidos / Ads / Orgánico / Ventas directas...
    campo_legacy_crm_id        TEXT,   -- columna huérfana heredada de un CRM anterior, 100% vacía
    _source_system             TEXT DEFAULT 'crm',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.crm_cliente IS 'Maestro de clientes del CRM. Con problemas de calidad reales (nulos, duplicados, mayúsculas/minúsculas inconsistentes) — de aquí sale el score de projects/13-data-health-check.';

CREATE TABLE bronze.crm_equipo (
    equipo_id                  TEXT,
    nombre_equipo              TEXT,
    _source_system             TEXT DEFAULT 'crm',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.crm_equipo IS 'Catálogo de equipos comerciales.';

CREATE TABLE bronze.crm_vendedor (
    vendedor_id                TEXT,
    codigo_vendedor            TEXT,
    equipo_id                  TEXT,
    _source_system             TEXT DEFAULT 'crm',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.crm_vendedor IS 'Catálogo de vendedores, cada uno asignado a un equipo.';

CREATE TABLE bronze.crm_meta_venta (
    equipo_id                  TEXT,
    meta_mensual_mxn           TEXT,   -- meta vigente, capturada por planeación comercial (no se deriva de ventas)
    _source_system             TEXT DEFAULT 'crm',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.crm_meta_venta IS 'Meta mensual por equipo. Insumo de planeación, no un cálculo — igual que un target en cualquier CRM.';

CREATE TABLE bronze.crm_oportunidad_evento (
    evento_id                  TEXT,
    oportunidad_id             TEXT,
    etapa                      TEXT,   -- lead | contactado | calificado | propuesta | cierre
    fecha_evento               TEXT,
    vendedor_id                TEXT,
    _source_system             TEXT DEFAULT 'crm',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.crm_oportunidad_evento IS 'Bitácora de eventos del pipeline (1 fila por cambio de etapa de una oportunidad). Insumo crudo del funnel semanal.';

-- -----------------------------------------------------------------------------
-- VENTAS — pedidos transaccionales (el hecho de ventas central de la empresa)
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.pedido_linea (
    pedido_id                  TEXT,
    linea_id                   TEXT,
    fecha                      TEXT,
    cliente_id                 TEXT,
    sucursal                   TEXT,   -- venta atendida por un vendedor/equipo (canal "gestionado")
    vendedor_id                TEXT,
    canal_venta                TEXT,   -- Tienda / E-commerce / Marketplace / Equipo comercial
    sku                        TEXT,
    cantidad                   TEXT,
    precio_unitario            TEXT,
    descuento_pct              TEXT,
    _source_system             TEXT DEFAULT 'pos_crm',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.pedido_linea IS 'Línea de pedido del sistema de ventas gestionado (equipos comerciales / e-commerce / marketplace). Grano: 1 fila por SKU vendido. Es el hecho del que se derivan 01, 05, 06, 07, 09 y 10.';

-- Tres sucursales que NO están integradas al sistema de ventas gestionado:
-- reportan por su cuenta, cada una con su propio formato — el problema real
-- que resuelve projects/11-consolidacion-fuente-verdad.
CREATE TABLE bronze.pedido_sucursal_cdmx (
    "Fecha"                    TEXT,   -- DD/MM/YYYY
    "Sucursal"                 TEXT,
    "Monto"                    TEXT,
    _source_system             TEXT DEFAULT 'export_sucursal_cdmx',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.pedido_sucursal_cdmx IS 'Export manual de ventas de la sucursal CDMX (columnas en español, fecha DD/MM/YYYY) — sin detalle de línea/SKU, solo total del día.';

CREATE TABLE bronze.pedido_sucursal_guadalajara (
    "Date"                     TEXT,   -- MM/DD/YYYY
    "Store"                    TEXT,   -- 'guadalajara' / 'GDL ' / 'Guadalajara' sin normalizar
    "Amount_MXN"               TEXT,
    _source_system             TEXT DEFAULT 'export_sucursal_guadalajara',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.pedido_sucursal_guadalajara IS 'Export de un sistema legado en inglés — catálogo de sucursal sin normalizar.';

CREATE TABLE bronze.pedido_sucursal_monterrey (
    fecha_venta                TEXT,   -- YYYY-MM-DD
    tienda                     TEXT,
    importe_mxn                TEXT,   -- algunos montos vienen vacíos
    _source_system             TEXT DEFAULT 'export_sucursal_monterrey',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.pedido_sucursal_monterrey IS 'Export de la sucursal Monterrey, con montos faltantes en algunas filas.';

-- -----------------------------------------------------------------------------
-- CATÁLOGO E INVENTARIO
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.producto (
    sku                        TEXT,
    nombre_producto            TEXT,
    categoria                  TEXT,
    subcategoria               TEXT,
    precio_unitario            TEXT,   -- a veces "$1,234.50"
    costo_unitario             TEXT,
    unidad_medida              TEXT,
    activo                     TEXT,
    campo_obsoleto_bodega_2019 TEXT,   -- columna huérfana, 100% vacía
    _source_system             TEXT DEFAULT 'erp_catalogo',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.producto IS 'Maestro de producto/SKU del ERP. Con problemas de calidad reales (precio como texto, duplicados suaves) — insumo de projects/13.';

CREATE TABLE bronze.inventario_snapshot (
    sku                        TEXT,
    fecha_snapshot             TEXT,
    stock_actual               TEXT,
    lead_time_dias             TEXT,
    _source_system             TEXT DEFAULT 'wms',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.inventario_snapshot IS 'Foto periódica de inventario por SKU (sistema de almacén). El segmento de demanda (alta/media/baja) NO viene de aquí — se calcula en silver a partir del historial de ventas.';

-- -----------------------------------------------------------------------------
-- FACTURACIÓN Y COBRANZA
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.factura_linea (
    factura_id                 TEXT,
    fecha                      TEXT,
    fecha_vencimiento          TEXT,
    cliente_id                 TEXT,   -- puede apuntar a un cliente_id que ya no existe
    sku                        TEXT,   -- puede apuntar a un sku descontinuado
    cantidad                   TEXT,
    precio_unitario            TEXT,
    moneda                     TEXT,
    total                      TEXT,   -- a veces total <> cantidad * precio_unitario (override manual)
    canal_venta                TEXT,
    _source_system             TEXT DEFAULT 'erp_facturacion',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.factura_linea IS 'Línea de facturación del ERP, con integridad referencial rota y errores de cálculo reales — insumo de projects/13 y, ya limpia, de projects/08.';

CREATE TABLE bronze.pago (
    pago_id                    TEXT,
    factura_id                 TEXT,
    fecha_pago                 TEXT,
    monto_pagado               TEXT,
    metodo_pago                TEXT,
    _source_system             TEXT DEFAULT 'erp_facturacion',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.pago IS 'Ledger de pagos recibidos contra factura. De aquí sale estatus/fecha_pago/aging de projects/08 — no es una columna plana en la factura.';

CREATE TABLE bronze.suscripcion_cargo (
    cliente_id                 TEXT,
    mes                        TEXT,
    gasto_mensual_mxn          TEXT,
    _source_system             TEXT DEFAULT 'erp_facturacion',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.suscripcion_cargo IS 'Cargo recurrente mensual para clientes con plan de servicio. Insumo de la feature gasto_mensual_mxn de churn (04).';

-- -----------------------------------------------------------------------------
-- SOPORTE Y ACTIVIDAD DE PRODUCTO
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.ticket_soporte (
    ticket_id                  TEXT,
    cliente_id                 TEXT,
    fecha_apertura             TEXT,
    fecha_cierre               TEXT,
    categoria                  TEXT,
    _source_system             TEXT DEFAULT 'helpdesk',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.ticket_soporte IS 'Tickets del helpdesk. Insumo de tickets_soporte_90d en el feature set de churn.';

CREATE TABLE bronze.evento_actividad (
    evento_id                  TEXT,
    cliente_id                 TEXT,
    fecha                      TEXT,
    tipo_evento                TEXT,   -- login, uso de feature, descarga de reporte...
    usage_points               TEXT,
    _source_system             TEXT DEFAULT 'producto_analytics',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.evento_actividad IS 'Log de actividad del producto/servicio. Insumo de dias_desde_ultima_actividad y usage_score.';

CREATE TABLE bronze.cancelacion (
    cliente_id                 TEXT,
    fecha_cancelacion          TEXT,
    motivo                     TEXT,
    _source_system             TEXT DEFAULT 'crm',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.cancelacion IS 'Baja de contrato/plan. Insumo de churn_historico (04) y de la retención por canal (09).';

-- -----------------------------------------------------------------------------
-- MARKETING
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.marketing_gasto (
    canal                      TEXT,
    fecha                      TEXT,
    gasto_mxn                  TEXT,
    _source_system             TEXT DEFAULT 'ads_platforms',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.marketing_gasto IS 'Gasto diario por canal, exportado de las plataformas de pauta. Los clientes_nuevos por canal se calculan en silver a partir de crm_cliente.canal_adquisicion, no vienen de aquí.';

-- -----------------------------------------------------------------------------
-- ENCUESTAS
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.encuesta_nps (
    respuesta_id               TEXT,
    cliente_id                 TEXT,
    fecha                      TEXT,
    score                      TEXT,
    motivo_detractor           TEXT,
    _source_system             TEXT DEFAULT 'encuestas_voc',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.encuesta_nps IS 'Export crudo de la herramienta de encuestas. La categoría (Promotor/Pasivo/Detractor) es una regla de negocio sobre score, no un dato capturado — se calcula en silver.';

-- -----------------------------------------------------------------------------
-- CALENDARIO Y PLANEACIÓN
-- -----------------------------------------------------------------------------
CREATE TABLE bronze.calendario (
    fecha                      TEXT,
    anio                       TEXT,
    mes                        TEXT,
    nombre_mes                 TEXT,
    trimestre                  TEXT,
    dia_semana                 TEXT,
    es_fin_de_semana           TEXT,
    es_feriado                 TEXT,   -- columna huérfana, prácticamente vacía
    _source_system             TEXT DEFAULT 'erp_calendario',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.calendario IS 'Calendario maestro del ERP, insumo crudo de silver.dim_fecha — auditado también por projects/13.';

CREATE TABLE bronze.kpi_captura_manual (
    kpi                        TEXT,
    area                       TEXT,
    responsable                TEXT,
    mes                        TEXT,
    resultado                  TEXT,
    unidad                     TEXT,
    menor_es_mejor             TEXT,
    _source_system             TEXT DEFAULT 'scorecard_manual',
    _batch_id                  UUID,
    _loaded_at                 TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE bronze.kpi_captura_manual IS 'KPIs que ningún sistema transaccional captura solo (p.ej. satisfacción interna, SLA) y que el dueño del indicador registra a mano en el scorecard cada mes. Los demás KPIs del scorecard (ingresos, NPS, nuevos clientes...) se calculan en silver/gold a partir de otras tablas, no se duplican aquí.';
