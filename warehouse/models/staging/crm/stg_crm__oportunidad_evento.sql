select
    evento_id,
    oportunidad_id,
    trim(etapa) as etapa,
    try_cast(fecha_evento as date) as fecha_evento,
    vendedor_id
from {{ source('crm', 'crm_oportunidad_evento') }}
