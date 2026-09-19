-- Dashboard 01 · projects/01-sales-performance-dashboard/data/metas_mensuales.csv
-- Meta mensual vigente por equipo (dato de planeación, no calculado).
select
    e.nombre_equipo as equipo,
    m.meta_mensual_mxn::bigint as meta_mensual_mxn
from {{ ref('fct_meta_venta') }} m
join {{ ref('dim_equipo') }} e on e.equipo_key = m.equipo_key
