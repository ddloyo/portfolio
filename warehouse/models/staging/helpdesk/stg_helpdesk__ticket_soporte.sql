select
    ticket_id,
    cliente_id,
    try_cast(fecha_apertura as date) as fecha_apertura,
    try_cast(fecha_cierre as date) as fecha_cierre,
    trim(categoria) as categoria
from {{ source('helpdesk', 'ticket_soporte') }}
