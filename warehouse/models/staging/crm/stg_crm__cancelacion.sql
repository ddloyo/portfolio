select
    cliente_id,
    try_cast(fecha_cancelacion as date) as fecha_cancelacion,
    trim(motivo) as motivo
from {{ source('crm', 'cancelacion') }}
