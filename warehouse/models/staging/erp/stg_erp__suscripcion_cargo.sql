select
    cliente_id,
    mes,
    try_cast(mes || '-01' as date) as mes_inicio,
    try_cast(gasto_mensual_mxn as decimal(14,2)) as gasto_mensual_mxn
from {{ source('erp', 'suscripcion_cargo') }}
