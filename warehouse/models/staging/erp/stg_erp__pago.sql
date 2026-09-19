select
    pago_id,
    factura_id,
    try_cast(fecha_pago as date) as fecha_pago,
    try_cast(monto_pagado as decimal(14,2)) as monto_pagado,
    trim(metodo_pago) as metodo_pago
from {{ source('erp', 'pago') }}
