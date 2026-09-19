-- Cola de revisión manual: filas de sucursal sin monto. Nunca se imputa un valor.
select
    {{ dbt_utils.generate_surrogate_key(['p.fecha', 'p.sucursal', 'p.fuente', 'p.rn']) }} as pendiente_key,
    p.fecha as date_key,
    s.sucursal_key,
    'monto_faltante' as motivo,
    p.fuente
from {{ ref('int_ventas_sucursal_pendiente') }} p
join {{ ref('dim_sucursal') }} s on s.nombre_normalizado = p.sucursal
