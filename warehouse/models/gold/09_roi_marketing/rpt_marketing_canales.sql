{% set ref_date = "cast('" ~ var('fecha_referencia') ~ "' as date)" %}

-- Dashboard 09 · projects/09-roi-marketing-canal/data/marketing_canales.csv
-- Insumos mensuales por canal con inversión: gasto, clientes nuevos, ticket
-- promedio, retención y margen. El dashboard calcula CAC, LTV y payback sobre
-- estas columnas (el warehouse ya los calcula en fct_canal_roi). Solo meses
-- completos. Un mes sin altas trae clientes_nuevos = 0 (CAC no definido).
select
    c.nombre_canal as canal,
    strftime(make_date(m.anio, m.mes, 1), '%Y-%m') as mes,
    x.gasto_mxn::double as gasto_mxn,
    x.clientes_nuevos::bigint as clientes_nuevos,
    x.ticket_promedio::double as ticket_promedio_mxn,
    x.meses_retencion::double as meses_retencion_prom,
    x.margen_bruto::double as margen_bruto
from {{ ref('int_canal_mes_metricas') }} x
join {{ ref('dim_canal') }} c on c.canal_key = x.canal_key
join {{ ref('dim_mes') }} m on m.mes_key = x.mes_key
where make_date(m.anio, m.mes, 1) < date_trunc('month', {{ ref_date }})
