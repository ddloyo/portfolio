select
    {{ dbt_utils.generate_surrogate_key(['e.evento_id']) }} as evento_key,
    e.evento_id,
    dc.cliente_key,
    e.fecha as date_key,
    e.tipo_evento,
    e.usage_points
from {{ ref('stg_producto_analytics__evento_actividad') }} e
join {{ ref('dim_cliente') }} dc on dc.cliente_id = e.cliente_id
where e.fecha is not null and e.usage_points is not null
