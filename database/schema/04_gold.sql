-- =============================================================================
-- GOLD LAYER — los 13 datasets del portafolio, como consulta sobre silver
-- =============================================================================
-- Cada vista de aquí, al correrla, reproduce (en estructura) uno de los CSV
-- que hoy viven en projects/<NN>/data/*.csv. Antes esos CSV eran tratados
-- como si ya fueran datos limpios; en este diseño son el RESULTADO de
-- agregar/calcular sobre el operativo real de la empresa (silver) — no el
-- punto de partida. Por eso casi todas llevan GROUP BY, no son un simple
-- pass-through.
--
-- Lo que NO se resuelve en SQL puro (regresión logística de churn, RFM,
-- elasticidad, forecast, score de calidad) ya viene calculado en las tablas
-- silver.fact_*_score / *_forecast / *_elasticidad — esas corren en un job
-- de Python/ML por fuera de la base, y su salida se conforma en silver antes
-- de llegar aquí. Gold solo tiene que unir y dar el formato final.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS gold;

-- -----------------------------------------------------------------------------
-- 01 · sales-performance-dashboard  →  ventas_diarias.csv + metas_mensuales.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_01_ventas_diarias AS
SELECT
    p.date_key           AS fecha,
    eq.nombre_equipo      AS equipo,
    v.codigo_vendedor      AS vendedor,
    pr.categoria             AS linea_producto,
    SUM(p.importe_neto)        AS monto_mxn
FROM silver.fact_pedido p
JOIN silver.dim_vendedor v  ON v.vendedor_key = p.vendedor_key   -- ventas del canal gestionado (vendedor asignado)
JOIN silver.dim_equipo eq   ON eq.equipo_key = v.equipo_key
JOIN silver.dim_producto pr ON pr.producto_key = p.producto_key
GROUP BY p.date_key, eq.nombre_equipo, v.codigo_vendedor, pr.categoria;
COMMENT ON VIEW gold.rpt_01_ventas_diarias IS 'Agrega fact_pedido (solo líneas con vendedor asignado) por día x equipo x vendedor x categoría.';

CREATE VIEW gold.rpt_01_metas_mensuales AS
SELECT eq.nombre_equipo AS equipo, m.meta_mensual_mxn
FROM silver.fact_meta_venta m
JOIN silver.dim_equipo eq ON eq.equipo_key = m.equipo_key;
COMMENT ON VIEW gold.rpt_01_metas_mensuales IS 'Pass-through de la meta vigente por equipo (dato de planeación, no calculado).';

-- -----------------------------------------------------------------------------
-- 02 · funnel-fuga-ventas  →  funnel_semanal.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_02_funnel_semanal AS
SELECT
    f.anio, f.numero_semana_iso AS semana,
    COUNT(*) FILTER (WHERE e.etapa = 'lead')         AS leads,
    COUNT(*) FILTER (WHERE e.etapa = 'contactado')   AS contactados,
    COUNT(*) FILTER (WHERE e.etapa = 'calificado')   AS calificados,
    COUNT(*) FILTER (WHERE e.etapa = 'propuesta')    AS propuestas,
    COUNT(*) FILTER (WHERE e.etapa = 'cierre')       AS cierres
FROM silver.fact_oportunidad_evento e
JOIN silver.dim_fecha f ON f.date_key = e.date_key
GROUP BY f.anio, f.numero_semana_iso
ORDER BY f.anio, f.numero_semana_iso;
COMMENT ON VIEW gold.rpt_02_funnel_semanal IS 'Cuenta eventos de fact_oportunidad_evento (bitácora diaria del pipeline) por semana ISO x etapa.';

-- -----------------------------------------------------------------------------
-- 03 · scorecard-metas-vs-resultados  →  kpi_historico.csv + scorecard.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_03_kpi_historico AS
WITH fecha_mes AS (
    SELECT f.date_key, mm.mes_key
    FROM silver.dim_fecha f
    JOIN silver.dim_mes mm ON mm.anio = f.anio AND mm.mes = f.mes
),
-- KPI derivable #1: ingresos mensuales = pedidos del canal gestionado + ventas de sucursal
ingresos_mensuales AS (
    SELECT fm.mes_key, SUM(ingresos.monto) AS resultado
    FROM (
        SELECT p.date_key, p.importe_neto AS monto FROM silver.fact_pedido p
        UNION ALL
        SELECT vs.date_key, vs.monto_mxn FROM silver.fact_venta_sucursal vs WHERE NOT vs.es_duplicado_descartado
    ) ingresos
    JOIN fecha_mes fm ON fm.date_key = ingresos.date_key
    GROUP BY fm.mes_key
),
-- KPI derivable #2: nuevos clientes = altas del mes en dim_cliente
nuevos_clientes AS (
    SELECT mm.mes_key, COUNT(*) AS resultado
    FROM silver.dim_cliente c
    JOIN silver.dim_mes mm
      ON mm.anio = date_part('year', c.fecha_alta)::smallint
     AND mm.mes  = date_part('month', c.fecha_alta)::smallint
    GROUP BY mm.mes_key
),
-- KPI derivable #3: NPS = %promotores - %detractores del mes
nps_mensual AS (
    SELECT fm.mes_key,
           ROUND((COUNT(*) FILTER (WHERE n.categoria = 'Promotor')::numeric
                - COUNT(*) FILTER (WHERE n.categoria = 'Detractor')::numeric)
                / NULLIF(COUNT(*), 0) * 100, 1) AS resultado
    FROM silver.fact_encuesta_nps n
    JOIN fecha_mes fm ON fm.date_key = n.date_key
    GROUP BY fm.mes_key
)
-- El mismo patrón (agregar el hecho operativo correspondiente por mes) se
-- extiende a cualquier otro KPI derivable (ticket promedio, DSO, tasa de
-- cierre del funnel...) agregando más CTEs al UNION ALL.
SELECT to_char(make_date(mm.anio, mm.mes, 1), 'YYYY-MM') AS mes, 'Ingresos mensuales' AS kpi, 'Ventas' AS area, im.resultado
FROM ingresos_mensuales im JOIN silver.dim_mes mm ON mm.mes_key = im.mes_key
UNION ALL
SELECT to_char(make_date(mm.anio, mm.mes, 1), 'YYYY-MM'), 'Nuevos clientes', 'Ventas', nc.resultado
FROM nuevos_clientes nc JOIN silver.dim_mes mm ON mm.mes_key = nc.mes_key
UNION ALL
SELECT to_char(make_date(mm.anio, mm.mes, 1), 'YYYY-MM'), 'NPS', 'Experiencia de cliente', nps.resultado
FROM nps_mensual nps JOIN silver.dim_mes mm ON mm.mes_key = nps.mes_key
UNION ALL
-- KPIs sin fuente transaccional (capturados a mano en bronze.kpi_captura_manual)
SELECT to_char(make_date(mm.anio, mm.mes, 1), 'YYYY-MM'), k.nombre_kpi, k.area, fkm.resultado
FROM silver.fact_kpi_manual fkm
JOIN silver.dim_kpi k  ON k.kpi_key = fkm.kpi_key
JOIN silver.dim_mes mm ON mm.mes_key = fkm.mes_key;
COMMENT ON VIEW gold.rpt_03_kpi_historico IS 'Serie histórica mensual por KPI: unión de KPIs calculados sobre hechos operativos + KPIs de captura manual.';

CREATE VIEW gold.rpt_03_scorecard AS
WITH ultimo_mes AS (
    SELECT anio, mes FROM silver.dim_mes ORDER BY anio DESC, mes DESC LIMIT 1
)
SELECT
    h.kpi, h.area, k.responsable, k.unidad, k.menor_es_mejor,
    fm.meta, h.resultado
FROM gold.rpt_03_kpi_historico h
JOIN silver.dim_kpi k        ON k.nombre_kpi = h.kpi
JOIN silver.fact_kpi_meta fm ON fm.kpi_key = k.kpi_key
JOIN ultimo_mes um            ON h.mes = to_char(make_date(um.anio, um.mes, 1), 'YYYY-MM');
COMMENT ON VIEW gold.rpt_03_scorecard IS 'Snapshot del mes más reciente de rpt_03_kpi_historico, con meta vigente y metadatos del KPI.';

-- -----------------------------------------------------------------------------
-- 04 · prediccion-churn  →  clientes.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_04_clientes AS
SELECT
    c.cliente_id_origen AS cliente_id,
    f.antiguedad_meses, f.gasto_mensual_mxn, f.tickets_soporte_90d,
    f.dias_desde_ultima_actividad, f.usage_score, f.tipo_contrato, f.plan, f.churn_historico
FROM silver.fact_cliente_features_churn f
JOIN silver.dim_cliente c ON c.cliente_key = f.cliente_key;
COMMENT ON VIEW gold.rpt_04_clientes IS 'Pass-through del feature set (silver.fact_cliente_features_churn), ya agregado a partir de facturación/soporte/actividad/cancelación.';

-- -----------------------------------------------------------------------------
-- 05 · segmentacion-rfm  →  transacciones.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_05_transacciones AS
SELECT
    c.cliente_id_origen AS cliente_id,
    p.date_key             AS fecha,
    SUM(p.importe_neto)       AS monto_mxn
FROM silver.fact_pedido p
JOIN silver.dim_cliente c ON c.cliente_key = p.cliente_key
GROUP BY c.cliente_id_origen, p.date_key;
COMMENT ON VIEW gold.rpt_05_transacciones IS 'fact_pedido agregado a nivel cliente x día — insumo directo del cálculo RFM.';

-- -----------------------------------------------------------------------------
-- 06 · elasticidad-precios  →  precio_demanda.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_06_precio_demanda AS
SELECT
    pr.nombre_producto        AS producto,
    f.anio, f.numero_semana_iso AS semana,
    ROUND(AVG(p.precio_unitario), 2) AS precio_mxn,
    SUM(p.cantidad)                    AS unidades_vendidas
FROM silver.fact_pedido p
JOIN silver.dim_producto pr ON pr.producto_key = p.producto_key
JOIN silver.dim_fecha f     ON f.date_key = p.date_key
GROUP BY pr.nombre_producto, f.anio, f.numero_semana_iso;
COMMENT ON VIEW gold.rpt_06_precio_demanda IS 'fact_pedido agregado por producto x semana ISO — insumo directo de la regresión de elasticidad.';

-- -----------------------------------------------------------------------------
-- 07 · forecast-demanda-inventario  →  demanda_diaria.csv + inventario_actual.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_07_demanda_diaria AS
SELECT
    pr.sku, p.date_key AS fecha,
    SUM(p.cantidad)                    AS unidades_vendidas,
    pr.costo_unitario, pr.precio_unitario,
    SUM(p.importe_neto)                  AS ingreso,
    SUM(p.cantidad) * pr.costo_unitario    AS costo_total
FROM silver.fact_pedido p
JOIN silver.dim_producto pr ON pr.producto_key = p.producto_key
GROUP BY pr.sku, p.date_key, pr.costo_unitario, pr.precio_unitario;
COMMENT ON VIEW gold.rpt_07_demanda_diaria IS 'fact_pedido agregado por SKU x día — insumo directo del forecast de demanda.';

CREATE VIEW gold.rpt_07_inventario_actual AS
SELECT
    pr.sku, pr.categoria, fc.segmento_demanda, inv.lead_time_dias, inv.stock_actual,
    pr.costo_unitario, pr.precio_unitario,
    ROUND((pr.precio_unitario - pr.costo_unitario) / NULLIF(pr.precio_unitario, 0) * 100, 1) AS margen_pct
FROM silver.fact_inventario_snapshot inv
JOIN silver.dim_producto pr ON pr.producto_key = inv.producto_key
JOIN silver.fact_producto_forecast fc
     ON fc.producto_key = inv.producto_key AND fc.fecha_forecast = inv.fecha_snapshot;
COMMENT ON VIEW gold.rpt_07_inventario_actual IS 'Última foto de inventario + segmento de demanda calculado en fact_producto_forecast (no viene de bronze).';

-- -----------------------------------------------------------------------------
-- 08 · flujo-caja-cartera  →  facturas.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_08_facturas AS
SELECT
    fa.factura_id_origen AS factura_id,
    c.nombre_completo      AS cliente,
    fa.date_key              AS fecha_emision,
    fa.fecha_vencimiento,
    fa.total                   AS monto_mxn,
    CASE
        WHEN pagos.total_pagado >= fa.total       THEN 'Pagada'
        WHEN CURRENT_DATE > fa.fecha_vencimiento  THEN 'Vencida'
        ELSE 'Pendiente'
    END AS estatus,
    pagos.ultima_fecha_pago AS fecha_pago
FROM silver.fact_factura fa
JOIN silver.dim_cliente c ON c.cliente_key = fa.cliente_key
LEFT JOIN (
    SELECT factura_key, SUM(monto_pagado) AS total_pagado, MAX(fecha_pago) AS ultima_fecha_pago
    FROM silver.fact_pago
    GROUP BY factura_key
) pagos ON pagos.factura_key = fa.factura_key;
COMMENT ON VIEW gold.rpt_08_facturas IS 'Estatus y fecha_pago se DERIVAN de fact_pago (soporta pagos parciales), no son columnas capturadas en la factura.';

-- -----------------------------------------------------------------------------
-- 09 · roi-marketing-canal  →  marketing_canales.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_09_marketing_canales AS
WITH gasto AS (
    SELECT ca.nombre_canal AS canal, mm.mes_key, SUM(mg.gasto_mxn) AS gasto_mxn
    FROM silver.fact_marketing_gasto mg
    JOIN silver.dim_canal ca ON ca.canal_key = mg.canal_key
    JOIN silver.dim_fecha f  ON f.date_key = mg.date_key
    JOIN silver.dim_mes mm   ON mm.anio = f.anio AND mm.mes = f.mes
    GROUP BY ca.nombre_canal, mm.mes_key
),
altas AS (
    SELECT c.canal_adquisicion AS canal, mm.mes_key, COUNT(*) AS clientes_nuevos
    FROM silver.dim_cliente c
    JOIN silver.dim_mes mm
      ON mm.anio = date_part('year', c.fecha_alta)::smallint
     AND mm.mes  = date_part('month', c.fecha_alta)::smallint
    GROUP BY c.canal_adquisicion, mm.mes_key
),
-- ticket promedio y margen bruto: se calculan sobre el pedido completo
-- (todas las líneas), no por línea, agrupando fact_pedido por pedido_id primero
pedido_total AS (
    SELECT p.pedido_id, p.cliente_key, MIN(p.date_key) AS fecha_pedido,
           SUM(p.importe_neto)                   AS monto,
           SUM(p.cantidad * pr.costo_unitario)      AS costo_total
    FROM silver.fact_pedido p
    JOIN silver.dim_producto pr ON pr.producto_key = p.producto_key
    GROUP BY p.pedido_id, p.cliente_key
),
ticket AS (
    SELECT c.canal_adquisicion AS canal, mm.mes_key,
           AVG(pt.monto)                                                     AS ticket_promedio_mxn,
           AVG((pt.monto - pt.costo_total) / NULLIF(pt.monto, 0))              AS margen_bruto
    FROM pedido_total pt
    JOIN silver.dim_cliente c ON c.cliente_key = pt.cliente_key
    JOIN silver.dim_fecha f   ON f.date_key = pt.fecha_pedido
    JOIN silver.dim_mes mm    ON mm.anio = f.anio AND mm.mes = f.mes
    GROUP BY c.canal_adquisicion, mm.mes_key
),
-- retención promedio (meses): antigüedad de los clientes del canal, evaluada
-- al cierre de cada mes, hasta su cancelación si ya se dio
retencion AS (
    SELECT c.canal_adquisicion AS canal, mm.mes_key,
           AVG(
               (EXTRACT(YEAR  FROM COALESCE(can.fecha_cancelacion, make_date(mm.anio, mm.mes, 1))) - EXTRACT(YEAR  FROM c.fecha_alta)) * 12
             + (EXTRACT(MONTH FROM COALESCE(can.fecha_cancelacion, make_date(mm.anio, mm.mes, 1))) - EXTRACT(MONTH FROM c.fecha_alta))
           ) AS meses_retencion_prom
    FROM silver.dim_cliente c
    JOIN silver.dim_mes mm ON c.fecha_alta <= make_date(mm.anio, mm.mes, 1)
    LEFT JOIN silver.fact_cancelacion can ON can.cliente_key = c.cliente_key
    GROUP BY c.canal_adquisicion, mm.mes_key
)
SELECT
    g.canal, to_char(make_date(mm.anio, mm.mes, 1), 'YYYY-MM') AS mes,
    g.gasto_mxn, a.clientes_nuevos, t.ticket_promedio_mxn, r.meses_retencion_prom, t.margen_bruto
FROM gasto g
JOIN silver.dim_mes mm ON mm.mes_key = g.mes_key
LEFT JOIN altas a     ON a.canal = g.canal AND a.mes_key = g.mes_key
LEFT JOIN ticket t    ON t.canal = g.canal AND t.mes_key = g.mes_key
LEFT JOIN retencion r ON r.canal = g.canal AND r.mes_key = g.mes_key;
COMMENT ON VIEW gold.rpt_09_marketing_canales IS 'Combina gasto de pauta, altas por canal_adquisicion, ticket/margen del pedido completo y antigüedad hasta cancelación — 4 hechos distintos, un canal.';

-- -----------------------------------------------------------------------------
-- 10 · reporte-ejecutivo-mensual  →  transacciones.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_10_transacciones AS
SELECT
    to_char(make_date(mm.anio, mm.mes, 1), 'YYYY-MM') AS mes,
    r.nombre_region       AS region,
    c.cliente_id_origen      AS cliente_id,
    c.segmento                 AS perfil,
    pr.categoria, pr.subcategoria,
    SUM(p.importe_neto)           AS ingreso_mxn
FROM silver.fact_pedido p
JOIN silver.dim_cliente c   ON c.cliente_key = p.cliente_key
JOIN silver.dim_region r    ON r.region_key = c.region_key
JOIN silver.dim_producto pr ON pr.producto_key = p.producto_key
JOIN silver.dim_fecha f     ON f.date_key = p.date_key
JOIN silver.dim_mes mm      ON mm.anio = f.anio AND mm.mes = f.mes
GROUP BY mm.anio, mm.mes, r.nombre_region, c.cliente_id_origen, c.segmento, pr.categoria, pr.subcategoria;
COMMENT ON VIEW gold.rpt_10_transacciones IS 'fact_pedido agregado por mes x región x cliente x categoría/subcategoría — el mismo hecho que 05 y 06, cortado distinto.';

-- -----------------------------------------------------------------------------
-- 11 · consolidacion-fuente-verdad  →  fuente_unica.csv + revision_manual_monto_faltante.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_11_fuente_unica AS
SELECT
    v.date_key AS fecha,
    s.nombre_normalizado AS sucursal,
    v.monto_mxn,
    'export_' || lower(regexp_replace(s.nombre_normalizado, '\s+', '_', 'g')) || '.csv' AS fuente
FROM silver.fact_venta_sucursal v
JOIN silver.dim_sucursal s ON s.sucursal_key = v.sucursal_key
WHERE NOT v.es_duplicado_descartado;
COMMENT ON VIEW gold.rpt_11_fuente_unica IS 'Filas de las 3 sucursales ya unidas, normalizadas y sin duplicados — grano transaccional, igual que el CSV original.';

CREATE VIEW gold.rpt_11_revision_manual_monto_faltante AS
SELECT
    p.date_key AS fecha,
    s.nombre_normalizado AS sucursal,
    NULL::numeric AS monto_mxn,
    'export_' || lower(regexp_replace(s.nombre_normalizado, '\s+', '_', 'g')) || '.csv' AS fuente
FROM silver.venta_sucursal_pendiente_revision p
JOIN silver.dim_sucursal s ON s.sucursal_key = p.sucursal_key;
COMMENT ON VIEW gold.rpt_11_revision_manual_monto_faltante IS 'Cola de excepción: filas sin monto que nunca se imputan.';

-- -----------------------------------------------------------------------------
-- 12 · nps-causa-raiz  →  encuestas_nps.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_12_encuestas_nps AS
SELECT
    n.respuesta_id_origen AS respuesta_id,
    to_char(make_date(mm.anio, mm.mes, 1), 'YYYY-MM') AS mes,
    n.score, n.categoria, n.motivo_detractor
FROM silver.fact_encuesta_nps n
JOIN silver.dim_fecha f ON f.date_key = n.date_key
JOIN silver.dim_mes mm  ON mm.anio = f.anio AND mm.mes = f.mes;
COMMENT ON VIEW gold.rpt_12_encuestas_nps IS 'Pass-through de fact_encuesta_nps con el mes formateado; categoria ya viene calculada de score en silver.';

-- -----------------------------------------------------------------------------
-- 13 · data-health-check  →  scorecard_calidad_tablas.csv + reglas_validacion.csv + plan_remediacion.csv
-- -----------------------------------------------------------------------------
CREATE VIEW gold.rpt_13_scorecard_calidad_tablas AS
WITH ultimo_batch AS (
    SELECT batch_id FROM meta.batch_ingesta ORDER BY iniciado_en DESC LIMIT 1
)
SELECT sc.tabla, sc.score, sc.status, sc.status_label, sc.reglas_evaluadas, sc.reglas_con_hallazgo, sc.filas
FROM meta.dq_scorecard_tabla sc
JOIN ultimo_batch ub ON ub.batch_id = sc.batch_id;
COMMENT ON VIEW gold.rpt_13_scorecard_calidad_tablas IS 'meta.dq_scorecard_tabla de la corrida más reciente, evaluado contra bronze.crm_cliente, bronze.producto, bronze.calendario y bronze.factura_linea — el maestro real de la empresa.';

CREATE VIEW gold.rpt_13_reglas_validacion AS
WITH ultimo_batch AS (
    SELECT batch_id FROM meta.batch_ingesta ORDER BY iniciado_en DESC LIMIT 1
)
SELECT
    r.tabla, r.campo, r.tipo, r.tipo_label, r.severidad_label AS severidad,
    r.descripcion, res.n_filas, res.n_fallas, res.pct_fallas, res.impacto_pts
FROM meta.dq_resultado_regla res
JOIN meta.dq_regla r  ON r.regla_key = res.regla_key
JOIN ultimo_batch ub  ON ub.batch_id = res.batch_id;
COMMENT ON VIEW gold.rpt_13_reglas_validacion IS 'Catálogo de reglas con su resultado en la corrida más reciente.';

CREATE VIEW gold.rpt_13_plan_remediacion AS
WITH ultimo_batch AS (
    SELECT batch_id FROM meta.batch_ingesta ORDER BY iniciado_en DESC LIMIT 1
)
SELECT
    pr.prioridad, r.tabla, r.campo, r.tipo, r.severidad_label AS severidad,
    pr.filas_afectadas, pr.pct_filas, pr.impacto_pts, pr.accion_recomendada
FROM meta.dq_plan_remediacion pr
JOIN meta.dq_regla r ON r.regla_key = pr.regla_key
JOIN ultimo_batch ub ON ub.batch_id = pr.batch_id
WHERE NOT pr.resuelto
ORDER BY pr.prioridad;
COMMENT ON VIEW gold.rpt_13_plan_remediacion IS 'Issues pendientes de la corrida más reciente, ordenados por impacto — mismo criterio que projects/13.';
