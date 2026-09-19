-- =============================================================================
-- SILVER LAYER — bodega operativa conformada de la empresa
-- =============================================================================
-- Dimensiones y hechos tipados, limpios y deduplicados a partir de bronze.
--
-- Dos tipos de tabla conviven aquí:
--   1) Hechos operativos — traducción directa y tipada de bronze (fact_pedido,
--      fact_factura, fact_ticket_soporte...).
--   2) Hechos enriquecidos — features y salidas de modelo calculadas a partir
--      de los hechos operativos (fact_cliente_features_churn,
--      fact_cliente_rfm_score, fact_producto_forecast...). Siguen siendo
--      silver: son reutilizables, pero ya no son "el dato tal cual llegó".
-- Gold (04_gold.sql) es un paso más: el corte exacto que reproduce cada uno
-- de los 13 datasets que hoy existen como CSV en projects/*/data/.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS silver;

-- -----------------------------------------------------------------------------
-- DIMENSIONES
-- -----------------------------------------------------------------------------

CREATE TABLE silver.dim_fecha (
    date_key                   DATE PRIMARY KEY,
    anio                SMALLINT NOT NULL,
    mes                 SMALLINT NOT NULL,
    nombre_mes                 TEXT NOT NULL,
    trimestre                  TEXT NOT NULL,
    numero_semana_iso   SMALLINT NOT NULL,
    dia_semana                 TEXT NOT NULL,
    es_fin_de_semana           BOOLEAN NOT NULL,
    es_feriado                 BOOLEAN NOT NULL DEFAULT false
);
COMMENT ON TABLE silver.dim_fecha IS 'Calendario canónico (1 fila/día), limpio a partir de bronze.calendario.';

CREATE TABLE silver.dim_semana (
    semana_key                 SERIAL PRIMARY KEY,
    anio                SMALLINT NOT NULL,
    numero_semana       SMALLINT NOT NULL,
    fecha_inicio               DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    fecha_fin                  DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    UNIQUE (anio, numero_semana)
);
COMMENT ON TABLE silver.dim_semana IS 'Grano semanal (funnel de oportunidades, precio/demanda).';

CREATE TABLE silver.dim_mes (
    mes_key                    SERIAL PRIMARY KEY,
    anio                SMALLINT NOT NULL,
    mes                 SMALLINT NOT NULL,
    nombre_mes                 TEXT NOT NULL,
    UNIQUE (anio, mes)
);
COMMENT ON TABLE silver.dim_mes IS 'Grano mensual (KPIs, marketing, ejecutivo, NPS, suscripciones).';

CREATE TABLE silver.dim_region (
    region_key                 SERIAL PRIMARY KEY,
    nombre_region              TEXT UNIQUE NOT NULL
);
COMMENT ON TABLE silver.dim_region IS 'Territorio comercial asignado por el CRM a cada cliente.';

CREATE TABLE silver.dim_cliente (
    cliente_key                SERIAL PRIMARY KEY,
    cliente_id_origen          TEXT UNIQUE NOT NULL,
    nombre_completo            TEXT,
    email                      TEXT,
    telefono                   TEXT,
    ciudad                     TEXT,
    region_key                 INTEGER REFERENCES silver.dim_region(region_key),
    segmento                   TEXT,
    fecha_alta                 DATE,
    tipo_contrato              TEXT,     -- Mensual / Anual / NULL
    plan                       TEXT,     -- Starter / Pro / NULL
    canal_adquisicion          TEXT
);
COMMENT ON TABLE silver.dim_cliente IS 'Cliente único de la empresa, deduplicado y tipado a partir de bronze.crm_cliente.';

CREATE TABLE silver.dim_producto (
    producto_key               SERIAL PRIMARY KEY,
    sku                        TEXT UNIQUE NOT NULL,
    nombre_producto            TEXT,
    categoria                  TEXT,
    subcategoria               TEXT,
    unidad_medida              TEXT,
    costo_unitario             NUMERIC(14,2),
    precio_unitario            NUMERIC(14,2),
    activo                     BOOLEAN
);
COMMENT ON TABLE silver.dim_producto IS 'Producto/SKU único, deduplicado y tipado a partir de bronze.producto.';

CREATE TABLE silver.dim_sucursal (
    sucursal_key               SERIAL PRIMARY KEY,
    nombre_normalizado         TEXT UNIQUE NOT NULL,   -- 'CDMX' / 'Guadalajara' / 'Monterrey'
    nombre_origen_raw          TEXT[]                  -- variantes vistas en bronze, ej. {'guadalajara','GDL ','Guadalajara'}
);
COMMENT ON TABLE silver.dim_sucursal IS 'Catálogo único de sucursal, normalizado a partir de las 3 variantes crudas de bronze.pedido_sucursal_*.';

CREATE TABLE silver.dim_equipo (
    equipo_key                 SERIAL PRIMARY KEY,
    nombre_equipo              TEXT UNIQUE NOT NULL
);
COMMENT ON TABLE silver.dim_equipo IS 'Equipo comercial.';

CREATE TABLE silver.dim_vendedor (
    vendedor_key               SERIAL PRIMARY KEY,
    codigo_vendedor            TEXT UNIQUE NOT NULL,
    equipo_key                 INTEGER NOT NULL REFERENCES silver.dim_equipo(equipo_key)
);
COMMENT ON TABLE silver.dim_vendedor IS 'Vendedor, asignado a un equipo.';

CREATE TABLE silver.dim_canal (
    canal_key                  SERIAL PRIMARY KEY,
    nombre_canal               TEXT UNIQUE NOT NULL,
    tipo_canal                 TEXT               -- 'venta' | 'marketing' | 'ambos'
);
COMMENT ON TABLE silver.dim_canal IS 'Canal, conforma canal_venta (pedidos/facturas) y canal de adquisición de marketing en un solo catálogo.';

CREATE TABLE silver.dim_kpi (
    kpi_key                    SERIAL PRIMARY KEY,
    nombre_kpi                 TEXT UNIQUE NOT NULL,
    area                       TEXT NOT NULL,
    responsable                TEXT,
    unidad                     TEXT,
    menor_es_mejor             BOOLEAN NOT NULL DEFAULT false
);
COMMENT ON TABLE silver.dim_kpi IS 'Catálogo de indicadores del scorecard, con o sin captura manual del resultado.';

-- -----------------------------------------------------------------------------
-- HECHOS OPERATIVOS
-- -----------------------------------------------------------------------------

CREATE TABLE silver.fact_pedido (
    linea_key             BIGSERIAL PRIMARY KEY,
    pedido_id                  TEXT NOT NULL,
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    cliente_key                INTEGER NOT NULL REFERENCES silver.dim_cliente(cliente_key),
    producto_key               INTEGER NOT NULL REFERENCES silver.dim_producto(producto_key),
    vendedor_key               INTEGER REFERENCES silver.dim_vendedor(vendedor_key),   -- NULL en venta self-service (e-commerce)
    canal_key                  INTEGER NOT NULL REFERENCES silver.dim_canal(canal_key),
    cantidad                   INTEGER NOT NULL,
    precio_unitario            NUMERIC(14,2) NOT NULL,
    descuento_pct              NUMERIC(5,4) NOT NULL DEFAULT 0,
    importe_neto               NUMERIC(14,2) NOT NULL
);
COMMENT ON TABLE silver.fact_pedido IS 'Línea de pedido del canal gestionado (equipo comercial / e-commerce / marketplace). Grano: 1 fila por SKU vendido. Alimenta 01, 05, 06, 07, 09 y 10.';

CREATE TABLE silver.fact_venta_sucursal (
    venta_sucursal_key         BIGSERIAL PRIMARY KEY,
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    sucursal_key               INTEGER NOT NULL REFERENCES silver.dim_sucursal(sucursal_key),
    monto_mxn                  NUMERIC(14,2) NOT NULL,
    es_duplicado_descartado    BOOLEAN NOT NULL DEFAULT false
);
COMMENT ON TABLE silver.fact_venta_sucursal IS 'Ventas de las 3 sucursales no integradas, consolidadas + deduplicadas ("fuente única"). Sin detalle de línea/SKU: alimenta 11 y el ingreso total de 03.';

CREATE TABLE silver.venta_sucursal_pendiente_revision (
    pendiente_key              BIGSERIAL PRIMARY KEY,
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    sucursal_key               INTEGER NOT NULL REFERENCES silver.dim_sucursal(sucursal_key),
    motivo                     TEXT NOT NULL DEFAULT 'monto_faltante'
);
COMMENT ON TABLE silver.venta_sucursal_pendiente_revision IS 'Cola de revisión manual: filas de sucursal sin monto que NO se imputan.';

CREATE TABLE silver.fact_meta_venta (
    equipo_key                 INTEGER PRIMARY KEY REFERENCES silver.dim_equipo(equipo_key),
    meta_mensual_mxn           NUMERIC(14,2) NOT NULL
);
COMMENT ON TABLE silver.fact_meta_venta IS 'Meta mensual vigente por equipo (insumo de planeación, tal cual bronze.crm_meta_venta).';

CREATE TABLE silver.fact_oportunidad_evento (
    evento_key             BIGSERIAL PRIMARY KEY,
    oportunidad_id             TEXT NOT NULL,
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    vendedor_key               INTEGER REFERENCES silver.dim_vendedor(vendedor_key),
    etapa                      TEXT NOT NULL   -- lead | contactado | calificado | propuesta | cierre
);
COMMENT ON TABLE silver.fact_oportunidad_evento IS 'Bitácora de cambios de etapa del pipeline. Grano: 1 fila por evento. Alimenta el funnel semanal (02).';

CREATE TABLE silver.fact_factura (
    factura_key              BIGSERIAL PRIMARY KEY,
    factura_id_origen          TEXT NOT NULL UNIQUE,
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    fecha_vencimiento          DATE NOT NULL,
    cliente_key                INTEGER NOT NULL REFERENCES silver.dim_cliente(cliente_key),
    producto_key               INTEGER NOT NULL REFERENCES silver.dim_producto(producto_key),
    canal_key                  INTEGER NOT NULL REFERENCES silver.dim_canal(canal_key),
    cantidad                   INTEGER NOT NULL,
    precio_unitario            NUMERIC(14,2) NOT NULL,
    total                      NUMERIC(14,2) NOT NULL   -- ya validado: total = cantidad * precio_unitario
);
COMMENT ON TABLE silver.fact_factura IS 'Línea de facturación ya limpia (integridad referencial y consistencia de cálculo resueltas). Alimenta 08 y 13.';

CREATE TABLE silver.fact_pago (
    pago_key                  BIGSERIAL PRIMARY KEY,
    factura_key                INTEGER NOT NULL REFERENCES silver.fact_factura(factura_key),
    fecha_pago                 DATE NOT NULL,
    monto_pagado               NUMERIC(14,2) NOT NULL,
    metodo_pago                TEXT
);
COMMENT ON TABLE silver.fact_pago IS 'Pagos aplicados a una factura. De aquí se deriva el estatus (Pagada/Pendiente/Vencida) que expone 08 — no es una columna capturada directamente.';

CREATE TABLE silver.fact_suscripcion_cargo (
    cliente_key                INTEGER NOT NULL REFERENCES silver.dim_cliente(cliente_key),
    mes_key                    INTEGER NOT NULL REFERENCES silver.dim_mes(mes_key),
    gasto_mensual_mxn          NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (cliente_key, mes_key)
);
COMMENT ON TABLE silver.fact_suscripcion_cargo IS 'Cargo recurrente mensual por cliente con plan de servicio.';

CREATE TABLE silver.fact_ticket_soporte (
    ticket_key                BIGSERIAL PRIMARY KEY,
    cliente_key                INTEGER NOT NULL REFERENCES silver.dim_cliente(cliente_key),
    fecha_apertura             DATE NOT NULL,
    fecha_cierre               DATE,
    categoria                  TEXT
);
COMMENT ON TABLE silver.fact_ticket_soporte IS 'Tickets de soporte por cliente.';

CREATE TABLE silver.fact_evento_actividad (
    evento_key                BIGSERIAL PRIMARY KEY,
    cliente_key                INTEGER NOT NULL REFERENCES silver.dim_cliente(cliente_key),
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    tipo_evento                TEXT NOT NULL,
    usage_points               NUMERIC(8,2) NOT NULL
);
COMMENT ON TABLE silver.fact_evento_actividad IS 'Log de actividad de producto/servicio por cliente.';

CREATE TABLE silver.fact_cancelacion (
    cliente_key                INTEGER PRIMARY KEY REFERENCES silver.dim_cliente(cliente_key),
    fecha_cancelacion          DATE NOT NULL,
    motivo                     TEXT
);
COMMENT ON TABLE silver.fact_cancelacion IS 'Baja de contrato/plan por cliente (si aplica).';

CREATE TABLE silver.fact_marketing_gasto (
    canal_key                  INTEGER NOT NULL REFERENCES silver.dim_canal(canal_key),
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    gasto_mxn                  NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (canal_key, date_key)
);
COMMENT ON TABLE silver.fact_marketing_gasto IS 'Gasto diario de pauta por canal.';

CREATE TABLE silver.fact_encuesta_nps (
    respuesta_key             BIGSERIAL PRIMARY KEY,
    respuesta_id_origen        TEXT NOT NULL UNIQUE,
    cliente_key                INTEGER REFERENCES silver.dim_cliente(cliente_key),
    date_key                   DATE NOT NULL REFERENCES silver.dim_fecha(date_key),
    score                                   SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 10),
    categoria                  TEXT NOT NULL,   -- Promotor(9-10) / Pasivo(7-8) / Detractor(0-6) — regla de negocio sobre score
    motivo_detractor           TEXT
);
COMMENT ON TABLE silver.fact_encuesta_nps IS 'Respuesta de encuesta ya tipada; categoria se deriva de score, no viene así de bronze.';

CREATE TABLE silver.fact_kpi_manual (
    kpi_key                    INTEGER NOT NULL REFERENCES silver.dim_kpi(kpi_key),
    mes_key                    INTEGER NOT NULL REFERENCES silver.dim_mes(mes_key),
    resultado                  NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (kpi_key, mes_key)
);
COMMENT ON TABLE silver.fact_kpi_manual IS 'Resultado mensual de los KPIs que no se pueden derivar de otro hecho operativo (capturados a mano).';

CREATE TABLE silver.fact_kpi_meta (
    kpi_key                    INTEGER PRIMARY KEY REFERENCES silver.dim_kpi(kpi_key),
    meta                       NUMERIC(14,2) NOT NULL
);
COMMENT ON TABLE silver.fact_kpi_meta IS 'Meta vigente por KPI (insumo de planeación, igual patrón que fact_meta_venta).';

CREATE TABLE silver.fact_inventario_snapshot (
    producto_key               INTEGER NOT NULL REFERENCES silver.dim_producto(producto_key),
    fecha_snapshot             DATE NOT NULL,
    stock_actual               INTEGER NOT NULL,
    lead_time_dias             INTEGER NOT NULL,
    PRIMARY KEY (producto_key, fecha_snapshot)
);
COMMENT ON TABLE silver.fact_inventario_snapshot IS 'Foto de inventario por SKU. margen_pct y segmento_demanda NO están aquí: se calculan en fact_producto_forecast.';

-- -----------------------------------------------------------------------------
-- HECHOS ENRIQUECIDOS — features y salidas de modelo/cálculo
-- Cada uno se computa a partir de los hechos operativos de arriba; el motor
-- de cálculo (regresión, RFM, forecast...) corre fuera de SQL puro (script
-- Python), pero su salida se conforma aquí para que gold solo tenga que leer.
-- -----------------------------------------------------------------------------

CREATE TABLE silver.fact_cliente_features_churn (
    cliente_key                INTEGER PRIMARY KEY REFERENCES silver.dim_cliente(cliente_key),
    fecha_snapshot             DATE NOT NULL,
    antiguedad_meses           NUMERIC(10,2) NOT NULL,             -- de dim_cliente.fecha_alta
    gasto_mensual_mxn          NUMERIC(14,2) NOT NULL,             -- de fact_suscripcion_cargo (últimos 30d)
    tickets_soporte_90d        INTEGER NOT NULL,                  -- de fact_ticket_soporte
    dias_desde_ultima_actividad NUMERIC(10,2) NOT NULL,           -- de fact_evento_actividad
    usage_score                NUMERIC(6,2) NOT NULL,           -- de fact_evento_actividad
    tipo_contrato              TEXT NOT NULL,                  -- de dim_cliente
    plan                       TEXT NOT NULL,                  -- de dim_cliente
    churn_historico            BOOLEAN NOT NULL                -- de fact_cancelacion
);
COMMENT ON TABLE silver.fact_cliente_features_churn IS 'Feature set de churn, calculado agregando suscripcion_cargo + ticket_soporte + evento_actividad + cancelacion + dim_cliente. Equivale exactamente a projects/04/data/clientes.csv.';

CREATE TABLE silver.fact_cliente_churn_score (
    cliente_key                INTEGER PRIMARY KEY REFERENCES silver.dim_cliente(cliente_key),
    fecha_scoring              DATE NOT NULL,
    probabilidad_churn         NUMERIC(5,4) NOT NULL,
    percentil_riesgo           NUMERIC(5,2) NOT NULL
);
COMMENT ON TABLE silver.fact_cliente_churn_score IS 'Salida del modelo de regresión logística entrenado sobre fact_cliente_features_churn.';

CREATE TABLE silver.fact_cliente_rfm_score (
    cliente_key                INTEGER PRIMARY KEY REFERENCES silver.dim_cliente(cliente_key),
    recencia_dias              INTEGER NOT NULL,
    frecuencia                 INTEGER NOT NULL,
    monto_total_12m            NUMERIC(14,2) NOT NULL,
    percentil_valor            NUMERIC(5,2) NOT NULL,
    segmento_rfm               TEXT NOT NULL   -- Campeones / En riesgo / Nuevos / Hibernando
);
COMMENT ON TABLE silver.fact_cliente_rfm_score IS 'Recencia/frecuencia/monto calculado sobre fact_pedido agregado por cliente. Equivale a projects/05/data/transacciones.csv ya resuelto por cliente.';

CREATE TABLE silver.fact_producto_elasticidad (
    producto_key               INTEGER PRIMARY KEY REFERENCES silver.dim_producto(producto_key),
    elasticidad                NUMERIC(10,4) NOT NULL,   -- pendiente de la regresión log-log sobre fact_pedido semanal
    r2                         NUMERIC(5,4) NOT NULL,
    ingreso_anual_actual       NUMERIC(16,2),
    impacto_proyectado_10pct   NUMERIC(16,2),
    accion_recomendada         TEXT
);
COMMENT ON TABLE silver.fact_producto_elasticidad IS 'Salida de la regresión de elasticidad, calculada sobre fact_pedido agregado por producto x semana.';

CREATE TABLE silver.fact_producto_forecast (
    producto_key               INTEGER NOT NULL REFERENCES silver.dim_producto(producto_key),
    fecha_forecast             DATE NOT NULL,
    segmento_demanda           TEXT NOT NULL,          -- alta/media/baja — calculado aquí, no en bronze
    demanda_pronosticada_28d   NUMERIC(14,2) NOT NULL,
    reorder_point              NUMERIC(14,2) NOT NULL,
    dias_cobertura             NUMERIC(10,2) NOT NULL,
    riesgo_quiebre             BOOLEAN NOT NULL,
    mape                       NUMERIC(6,4),
    mae                        NUMERIC(14,4),
    PRIMARY KEY (producto_key, fecha_forecast)
);
COMMENT ON TABLE silver.fact_producto_forecast IS 'Forecast de demanda (tendencia + estacionalidad DOW sobre fact_pedido) + punto de reorden combinando fact_inventario_snapshot.';

CREATE TABLE silver.fact_cliente_pago_segmento (
    cliente_key                INTEGER PRIMARY KEY REFERENCES silver.dim_cliente(cliente_key),
    dso_promedio_dias          NUMERIC(10,2) NOT NULL,
    segmento_pago              TEXT NOT NULL   -- Puntual / Lento / Moroso
);
COMMENT ON TABLE silver.fact_cliente_pago_segmento IS 'Días-promedio-de-pago calculado sobre fact_factura + fact_pago, y su segmento de riesgo.';

CREATE TABLE silver.fact_canal_roi (
    canal_key                  INTEGER NOT NULL REFERENCES silver.dim_canal(canal_key),
    mes_key                    INTEGER NOT NULL REFERENCES silver.dim_mes(mes_key),
    cac                        NUMERIC(14,2) NOT NULL,   -- fact_marketing_gasto / clientes_nuevos (dim_cliente.canal_adquisicion x fecha_alta)
    ltv                        NUMERIC(14,2) NOT NULL,   -- ticket promedio x margen x retención, de fact_pedido/fact_factura/fact_cancelacion
    ratio_ltv_cac              NUMERIC(8,2) NOT NULL,
    payback_meses              NUMERIC(6,2) NOT NULL,
    cuadrante                  TEXT NOT NULL,
    PRIMARY KEY (canal_key, mes_key)
);
COMMENT ON TABLE silver.fact_canal_roi IS 'CAC/LTV calculado combinando gasto de marketing, altas por canal y comportamiento de compra/retención de esos clientes.';

CREATE TABLE silver.fact_subcategoria_tendencia (
    categoria                  TEXT NOT NULL,
    subcategoria               TEXT NOT NULL,
    mes_key                    INTEGER NOT NULL REFERENCES silver.dim_mes(mes_key),
    variacion_yoy_pct          NUMERIC(6,2),
    pendiente_tendencia        NUMERIC(10,4),
    volatilidad                NUMERIC(10,4),
    z_score_anomalia           NUMERIC(6,2),
    segmento                   TEXT,     -- Motor de crecimiento / En riesgo / Alerta puntual / Estable
    PRIMARY KEY (categoria, subcategoria, mes_key)
);
COMMENT ON TABLE silver.fact_subcategoria_tendencia IS 'Tendencia/anomalía por categoría x subcategoría x mes, calculada sobre fact_pedido vía dim_producto.';
