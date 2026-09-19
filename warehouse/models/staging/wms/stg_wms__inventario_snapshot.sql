select
    sku,
    try_cast(fecha_snapshot as date) as fecha_snapshot,
    try_cast(stock_actual as int) as stock_actual,
    try_cast(lead_time_dias as int) as lead_time_dias
from {{ source('wms', 'inventario_snapshot') }}
