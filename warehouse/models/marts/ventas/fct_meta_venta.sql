select
    e.equipo_key,
    m.meta_mensual_mxn
from {{ ref('stg_crm__meta_venta') }} m
join {{ ref('dim_equipo') }} e on e.equipo_id = m.equipo_id
