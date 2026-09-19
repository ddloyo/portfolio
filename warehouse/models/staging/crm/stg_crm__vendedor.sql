select
    vendedor_id,
    trim(codigo_vendedor) as codigo_vendedor,
    equipo_id
from {{ source('crm', 'crm_vendedor') }}
