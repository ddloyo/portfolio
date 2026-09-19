select
    {{ dbt_utils.generate_surrogate_key(['t.ticket_id']) }} as ticket_key,
    t.ticket_id,
    dc.cliente_key,
    t.fecha_apertura,
    t.fecha_cierre,   -- NULL = ticket abierto
    t.categoria
from {{ ref('stg_helpdesk__ticket_soporte') }} t
join {{ ref('dim_cliente') }} dc on dc.cliente_id = t.cliente_id
where t.fecha_apertura is not null
