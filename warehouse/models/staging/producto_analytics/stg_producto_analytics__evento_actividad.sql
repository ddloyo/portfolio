select
    evento_id,
    cliente_id,
    try_cast(fecha as date) as fecha,
    trim(tipo_evento) as tipo_evento,
    try_cast(usage_points as decimal(8,2)) as usage_points
from {{ source('producto_analytics', 'evento_actividad') }}
