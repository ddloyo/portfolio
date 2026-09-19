select
    equipo_id,
    try_cast(meta_mensual_mxn as decimal(14,2)) as meta_mensual_mxn
from {{ source('crm', 'crm_meta_venta') }}
